'''
Post call script, this is the main script that is used by the postcall agent..

Tools inside the tool folder not user : Testing inline tools will later move to the tool call 
Testing inline tool call for speed 
Need to test tool call functionality for tool calling 
'''




import os
import json
from dotenv import load_dotenv
from langchain_openai import AzureChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

load_dotenv()
'''
Pydantic class for the data validation 
For postcall, we are considering only 
1. Sumamry
2. Action Item
3. agent_action_items
4. category

'''

class PostCallAnalysis(BaseModel):
    summary: str = Field(description="A 2-3 sentence summary of the call transcript. Focus on the main reason for the call, any payment agreements made, and customer sentiment.")
    user_action: str = Field(description="The action item that the USER (customer) needs to take based on the call.")
    agent_action_item: str = Field(description="The action item that the AGENT (caller/system) needs to take based on the call.")
    category: str = Field(description="Categorize the overall outcome of the call. You MUST classify the call exactly as ONE of the following: 'pending', 'cleared', or 'dispute'.")

async def process_transcript_and_update_json(call_data: dict):
    """
    Takes the JSON call data, uses Langchain + Azure OpenAI to extract summary, 
    action items, and categorization from the transcript, appends them back.
    """
    llm = AzureChatOpenAI(
        azure_endpoint=os.getenv("AZURE_ENDPOINT"),
        api_key=os.getenv("AZURE_API_KEY"),
        azure_deployment=os.getenv("AZURE_DEPLOYMENT", "gpt-4o"),
        api_version=os.getenv("AZURE_API_VERSION", "2025-01-01-preview"),
        temperature=0,
    )
    
    structured_llm = llm.with_structured_output(PostCallAnalysis)
    
    # System-State : Prompt.
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are an AI assistant processing post-call data. Analyze the transcript and extract the requested information."),
        ("human", "User: {user_name}\nTranscript:\n{transcript}")
    ])
    
    chain = prompt | structured_llm
    
    # Process transcript which might be a list or dict
    transcript = call_data.get("transcript", "")
    if isinstance(transcript, (dict, list)):
        transcript = json.dumps(transcript)
        
    try:
        # Execute ASYNCHRONOUSLY
        result = await chain.ainvoke({
            "user_name": call_data.get("user_name", "Unknown"),
            "transcript": transcript
        })
        
        # Append the results back to the original dictionary
        call_data['summary'] = result.summary
        call_data['action_items'] = {
            "user_action": result.user_action,
            "agent_action_item": result.agent_action_item
        }
        call_data['categorization'] = result.category
    except Exception as e:
        print(f"Error processing transcript: {e}")
        call_data['summary'] = "Error extracting summary."
        call_data['action_items'] = {"user_action": "", "agent_action_item": ""}
        call_data['categorization'] = "Unknown"
        
    return call_data
