import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import List
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from backend.models import ChatRequest, ChatResponse, ChatSession
from backend.agent import process_chat
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from datetime import datetime

app = FastAPI(title="Material Intelligence Agent")

MONGO_URI = "mongodb://localhost:27017"
client = AsyncIOMotorClient(MONGO_URI)
db = client.material_db
sessions_collection = db.sessions

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/sessions", response_model=List[ChatSession])
async def get_sessions():
    sessions = []
    async for session in sessions_collection.find().sort("created_at", -1):
        session["_id"] = str(session["_id"])
        sessions.append(session)
    return sessions

@app.post("/api/sessions", response_model=ChatSession)
async def create_session():
    new_session = {
        "title": "New Chat",
        "history": [],
        "created_at": datetime.now().isoformat()
    }
    result = await sessions_collection.insert_one(new_session)
    new_session["_id"] = str(result.inserted_id)
    return new_session

@app.get("/api/sessions/{session_id}", response_model=ChatSession)
async def get_session(session_id: str):
    try:
        session = await sessions_collection.find_one({"_id": ObjectId(session_id)})
        if session:
            session["_id"] = str(session["_id"])
            return session
        raise HTTPException(status_code=404, detail="Session not found")
    except:
        raise HTTPException(status_code=404, detail="Invalid Session ID")

@app.post("/api/chat/{session_id}", response_model=ChatResponse)
async def chat_endpoint(session_id: str, request: ChatRequest):
    try:
        session = await sessions_collection.find_one({"_id": ObjectId(session_id)})
        if not session:
             raise HTTPException(status_code=404, detail="Session not found")
    except:
        raise HTTPException(status_code=404, detail="Invalid Session ID")

    current_history = session.get("history", [])
    current_history.append({"role": "user", "content": request.message})
    
    update_fields = {"history": current_history}
    if len(current_history) == 1:
        update_fields["title"] = request.message[:30] + "..." if len(request.message) > 30 else request.message

    await sessions_collection.update_one(
        {"_id": ObjectId(session_id)},
        {"$set": update_fields}
    )

    response_text = await process_chat(request.message, current_history[:-1]) # Send history excluding current msg as agent might append it internally or we handle it here. 
    
    current_history.append({"role": "assistant", "content": response_text})
    await sessions_collection.update_one(
        {"_id": ObjectId(session_id)},
        {"$set": {"history": current_history}}
    )

    return ChatResponse(response=response_text)

frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="static")
else:
    print(f"Frontend directory not found at {frontend_path}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
