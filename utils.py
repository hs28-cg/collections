import datetime
import io
import os
import wave
import json

import aiofiles
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import HTMLResponse
import uvicorn
from twilio.rest import Client
from typing import Dict, Any

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
from pipecat.processors.audio.audio_buffer_processor import AudioBufferProcessor
from pipecat.serializers.twilio import TwilioFrameSerializer
from pipecat.services.azure.llm import AzureLLMService
from pipecat.services.azure.stt import AzureSTTService
from pipecat.services.azure.tts import AzureTTSService
from pipecat.transports.network.fastapi_websocket import (
    FastAPIWebsocketParams,
    FastAPIWebsocketTransport,
)
from prompt.call_one import get_prompt as get_prompt_one
from prompt.call_two import get_prompt as get_prompt_two

load_dotenv()


# This function asynchronously writes buffered audio frames to a local WAV file.
async def save_audio(
    server_name: str, audio: bytes, sample_rate: int, num_channels: int
):
    if audio:
        now = datetime.datetime.now()
        timestamp = now.strftime("%Y/%m/%d_%H:%M:%S")
        wav_name = f"{server_name}_recording_{timestamp}.wav"
        buffer = io.BytesIO()
        with wave.open(buffer, mode="wb") as wav_file:
            wav_file.setsampwidth(2)
            wav_file.setnchannels(num_channels)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(audio)
        buffer.seek(0)
        async with aiofiles.open(wav_name, mode="wb") as out_file:
            await out_file.write(buffer.read())
        print(f"Audio file saved at {wav_name}")
    else:
        print("No audio data to save")


# This function handles the core conversational AI pipeline for the active Twilio phone call.
async def handle_voice_agent(
    websocket_client: WebSocket,
    stream_sid: str,
    call_sid: str,
    user_data: dict = None
):
    if user_data is None:
        user_data = {}
    transport = FastAPIWebsocketTransport(
        websocket=websocket_client,
        params=FastAPIWebsocketParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            add_wav_header=False,
            vad_enabled=True,
            vad_analyzer=SileroVADAnalyzer(),
            vad_audio_passthrough=True,
            serializer=TwilioFrameSerializer(stream_sid),
        ),
    )

    llm = AzureLLMService(
        api_key=os.getenv("AZURE_API_KEY"),
        model=os.getenv('AZURE_DEPLOYMENT'),
        api_version=os.getenv('AZURE_API_VERSION'),
        endpoint=os.getenv('AZURE_ENDPOINT'),
    )

    stt = AzureSTTService(
        api_key=os.getenv("AZURE_SPEECH_API_KEY"),
        region=os.getenv("AZURE_SPEECH_REGION"),
        language="en-US",
    )

    tts = AzureTTSService(
        api_key=os.getenv("AZURE_SPEECH_API_KEY"),
        region=os.getenv("AZURE_SPEECH_REGION"),
    )

    call_type = user_data.get("call_type")
    if call_type == 1:
        system_prompt = get_prompt_one(user_data)
    else:
        system_prompt = get_prompt_two(user_data)

    messages = [
        {
            "role": "system",
            "content": system_prompt,
        },
    ]

    context = OpenAILLMContext(messages)
    context_aggregator = llm.create_context_aggregator(context)

    audiobuffer = AudioBufferProcessor()

    pipeline = Pipeline(
        [
            transport.input(),
            stt,
            context_aggregator.user(),
            llm,
            tts,
            transport.output(),
            audiobuffer,
            context_aggregator.assistant(),
        ]
    )

    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            audio_in_sample_rate=8000,
            audio_out_sample_rate=8000,
            allow_interruptions=True,
        ),
    )

    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        await audiobuffer.start_recording()
        messages.append(
            {"role": "system", "content": "Please introduce yourself to the user."}
        )
        await task.queue_frames([context_aggregator.user().get_context_frame()])

    @audiobuffer.event_handler("on_audio_data")
    async def on_audio_data(buffer, audio, sample_rate, num_channels):
        server_name = f"server_{websocket_client.client.port}"
        await save_audio(server_name, audio, sample_rate, num_channels)

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        await task.cancel()

    runner = PipelineRunner(handle_sigint=False, force_gc=True)
    await runner.run(task)

    # NOTE : Important Here the context (temp-memory-conversation) is appended to the cosmos right after the call is ended
    
    # Save transcript to Cosmos DB after runner finishes and unblocks. 
    # This prevents the async database operations (and postcall AI) from being cancelled
    # mid-flight when the websocket is torn down by FastAPI.
    try:
        from db import save_transcript_to_cosmos
        full_transcript = context.get_messages()
        await save_transcript_to_cosmos(call_sid, full_transcript, user_data)
    except Exception as e:
        print(f"⚠️ Error preparing transcript save: {e}")


# --- FastAPI Application Setup ---

active_calls = {}

app = FastAPI(
    title="Pipecat Azure outbound call handler",
    description="Caller Agnet to make outbound calls",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Connect the postcall API routes
from api.main import router as api_router
app.include_router(api_router)

'''
The init_call endpoint returns a TwiML XML response that instructs Twilio to open a bidirectional media stream over WebSocket. 
It converts the webhook’s HTTPS URL into a WSS URL and embeds it in a <Stream> tag. 
When Twilio receives this response, it connects the ongoing phone call to your WebSocket endpoint (/ws).

'''



@app.post("/")
async def init_call():
    webhook_url = os.getenv("WEBHOOK_URL", "https://your-ngrok-url.ngrok-free.app")
    ws_url = webhook_url.replace("https://", "wss://").replace("http://", "ws://")
    
    content = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="{ws_url}/ws" />
    </Connect>
</Response>"""
    
    return HTMLResponse(content=content, media_type="application/xml")

'''
The make_call function uses Twilio to initiate an outbound phone call to the provided user_phone number. 
It sends call instructions via a webhook URL and stores the call’s SID in active_calls for tracking. 
It returns a confirmation message with the generated call_sid.
'''


@app.post("/call")
async def make_call(request: Dict[str, Any]):
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    from_number = os.getenv("TWILIO_PHONE_NUMBER")
    webhook_url = os.getenv("WEBHOOK_URL")

    client = Client(account_sid, auth_token)

    user_phone = request.get("user_phone")
    if not user_phone:
        return {"error": "user_phone is required"}

    call = client.calls.create(
        from_=from_number,
        to=user_phone,
        url=f"{webhook_url}/"
    )

    active_calls[call.sid] = request

    return {"status": "Call initiated", "call_sid": call.sid}

'''
The websocket_endpoint establishes a WebSocket connection and waits for initial Twilio media stream data. 
It extracts the streamSid and callSid from the incoming messages, retrieves any stored call-related metadata, 
and then hands control over to handle_voice_agent to process real‑time audio and agent interactions.

'''

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    init_data = websocket.iter_text()
    await init_data.__anext__()
    call_data = json.loads(await init_data.__anext__())
    print(call_data, flush=True)
    
    stream_sid = call_data["start"]["streamSid"]
    call_sid = call_data["start"]["callSid"]
    
    print(f"WebSocket connected to the call: {stream_sid}")
    
    user_data = active_calls.get(call_sid, {})
    await handle_voice_agent(websocket, stream_sid, call_sid, user_data)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)