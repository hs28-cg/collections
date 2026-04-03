import os
from azure.cosmos.aio import CosmosClient
from azure.cosmos.exceptions import CosmosHttpResponseError
from dotenv import load_dotenv
from twilio.rest import Client
import datetime
import json

load_dotenv()

COSMOS_ENDPOINT = os.getenv("ENDPOINT")
COSMOS_KEY = os.getenv("KEY")
DATABASE_NAME = os.getenv("DATABASE_NAME", "user-data")
CONTAINER_NAME = os.getenv("CONTAINER_NAME", "user-statements")

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")

# This function retrieves live call metadata from Twilio and saves it alongside the conversation transcript.
# It bundles the Twilio data, the full chat history, and the user's entire original JSON payload 
# into a single comprehensive document and upserts it into the pre-configured Azure Cosmos DB container.
async def save_transcript_to_cosmos(call_sid: str, transcript: list, user_data: dict = None):
    if user_data is None:
        user_data = {}
    """
    Saves the full Pipecat conversation transcript alongside Twilio Call metadata and Postcall Analysis to Azure Cosmos DB.
    """
    if not COSMOS_ENDPOINT or not COSMOS_KEY:
        print("⚠️ Cosmos DB Endpoint or Key not found in .env. Skipping transcript save.")
        return

    # 1. Fetch live call details from Twilio using the SID
    call_metadata = {}
    if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
        try:
            twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
            call_details = twilio_client.calls(call_sid).fetch()
            
            # Extract ALL available metadata from the Twilio call object dynamically
            for key in dir(call_details):
                if not key.startswith('_') and not callable(getattr(call_details, key)):
                    call_metadata[key] = str(getattr(call_details, key))

        except Exception as e:
            print(f"⚠️ Could not fetch Twilio call details: {e}")

    # 2. Upload everything together to Cosmos DB
    try:
        # Initialize async Cosmos client
        async with CosmosClient(COSMOS_ENDPOINT, credential=COSMOS_KEY) as client:
            db = client.get_database_client(DATABASE_NAME)
            container = db.get_container_client(CONTAINER_NAME)
            
            # Prepare the JSON document
            document = user_data.copy()
            
            # Map Twilio call details directly to the user's expected nested `call_data` object
            if "status" in call_metadata:
                if "call_data" not in document:
                    document["call_data"] = {}
                document["call_data"]["call_status"] = call_metadata.get("status")
                document["call_data"]["call_start_at"] = call_metadata.get("start_time")
                document["call_data"]["call_end_at"] = call_metadata.get("end_time")

            document.update({
                "id": call_sid,
                "user_id": call_sid,  # Using call_sid as the partition key for this transcript
                "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
                "twilio_metadata": call_metadata,
                "transcript": transcript
            })
            
            # --- POSTCALL INTEGRATION ---
            # Same data is send to the postcall here in the document
            try:
                document["postcall_status"] = "started"
                print(f"Running postcall analysis for {call_sid}...", flush=True)
                # Eagerly save the transcript with the started status
                await container.upsert_item(document)
                # Entire data including the trasncript is updated to the cosmosdb 

                # Execute LLM to generate summary, action items, and categorization
                # NOTE : Right after updating the document to cosmos db it is send to the postcall agent as well to process it 
                from postcall.main import process_transcript_and_update_json
                document = await process_transcript_and_update_json(document)
                document["postcall_status"] = "completed"
                # Once the processing is finished the docuemnt is marked as completed
                    
            except Exception as e:
                document["postcall_status"] = "failed"
                print(f"Error running postcall logic: {e}", flush=True)
            # ---------------------------

            # Upsert (create or update) the transcript document
            await container.upsert_item(document)
            print(f"✅ Successfully saved transcript, metadata, and postcall analysis for call {call_sid} to Cosmos!")
            
    except CosmosHttpResponseError as e:
        print(f"❌ Failed to save transcript to Cosmos DB. Error: {e.message}")
    except Exception as e:
        print(f"❌ Unexpected Error saving to Cosmos: {e}")
        
        
        