import os
import json
from fastapi import APIRouter, HTTPException
from azure.cosmos.aio import CosmosClient
from azure.cosmos.exceptions import CosmosHttpResponseError
from dotenv import load_dotenv

load_dotenv()

router = APIRouter(tags=["Postcall Data API"])

ENDPOINT = os.getenv("ENDPOINT")
KEY = os.getenv("KEY")
DATABASE_NAME = os.getenv("DATABASE_NAME", "user-data")
CONTAINER_NAME = os.getenv("CONTAINER_NAME", "user-statements")

async def get_db_data(case_id: str):
    if not ENDPOINT or not KEY:
        print("Missing Cosmos DB credentials")
        return None
        
    try:
        async with CosmosClient(ENDPOINT, credential=KEY) as client:
            db = client.get_database_client(DATABASE_NAME)
            container = db.get_container_client(CONTAINER_NAME)
            
            # Order by built-in timestamp (_ts) descending to guarantee we fetch the LATEST run
            query = "SELECT * FROM c WHERE c.case_id = @case_id ORDER BY c._ts DESC"
            parameters = [{"name": "@case_id", "value": case_id}]
            
            # Since partition key is user_id = call_sid (unknown here), cross partition query is needed natively
            items = []
            async for item in container.query_items(
                query=query,
                parameters=parameters
            ):
                items.append(item)
                
            if items:
                return items[0]
            return None
    except CosmosHttpResponseError as e:
        print(f"Cosmos DB Error: {e.message}")
        return None
    except Exception as e:
        print(f"Unexpected error querying Cosmos DB: {e}")
        return None

# 1. API used to fetch the Conversation Transcript for the text box
@router.get("/api/users/{case_id}/transcript")
async def get_transcript(case_id: str):
    user = await get_db_data(case_id)
    if user:
        return {"transcript": user.get("transcript", "")}
    raise HTTPException(status_code=404, detail="User not found")

# 2. API used to fetch the generated Summary for the summary text box
@router.get("/api/users/{case_id}/summary")
async def get_summary(case_id: str):
    user = await get_db_data(case_id)
    if user:
        return {"summary": user.get("summary", "")}
    raise HTTPException(status_code=404, detail="User not found")

# 3. API used to fetch the extracted Action Items for the action items text box
@router.get("/api/users/{case_id}/action_items")
async def get_action_items(case_id: str):
    user = await get_db_data(case_id)
    if user:
        return {"action_items": user.get("action_items", {})}
    raise HTTPException(status_code=404, detail="User not found")

# 4. API used to fetch the Final Categorization for the categorization text box
@router.get("/api/users/{case_id}/categorization")
async def get_categorization(case_id: str):
    user = await get_db_data(case_id)
    if user:
        return {"categorization": user.get("categorization", "")}
    raise HTTPException(status_code=404, detail="User not found")

@router.get("/api/users/{case_id}/status")
async def get_status(case_id: str):
    user = await get_db_data(case_id)
    if user:
        return {"postcall_status": user.get("postcall_status", "unknown")}
    raise HTTPException(status_code=404, detail="User not found")
