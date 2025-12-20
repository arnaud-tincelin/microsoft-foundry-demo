#!/usr/bin/env python3
"""
Game Session Tracking API
REST API for tracking game sessions with conversation ID, number picked, and win/loss status
Stores data in Azure Cosmos DB
"""
import os
from datetime import datetime
from typing import List
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from azure.cosmos import CosmosClient
from azure.identity import DefaultAzureCredential

# Cosmos DB configuration from environment variables
COSMOS_ENDPOINT = os.getenv("COSMOS_ENDPOINT", "")
DATABASE_NAME = os.getenv("COSMOS_DATABASE_NAME", "game-sessions-db")
CONTAINER_NAME = os.getenv("COSMOS_CONTAINER_NAME", "sessions")

# Initialize Cosmos DB client
credential = DefaultAzureCredential()
client = CosmosClient(COSMOS_ENDPOINT, credential=credential)
database = client.get_database_client(DATABASE_NAME)
container = database.get_container_client(CONTAINER_NAME)

# Create FastAPI app
app = FastAPI(
    title="Game Session Tracker API",
    description="REST API for tracking 'Guess My Number' game sessions",
    version="1.0.0"
)

# Pydantic models
class GameSession(BaseModel):
    conversation_id: str = Field(..., description="Unique identifier for the conversation/game session")
    number_picked: int = Field(..., ge=1, description="The number that was picked in the game (minimum: 1)")
    status: str = Field(..., pattern="^(won|lost)$", description="Whether the player won or lost the game (must be 'won' or 'lost')")

class GameSessionResponse(BaseModel):
    id: str
    timestamp: str
    conversation_id: str
    number_picked: int
    status: str

@app.post("/sessions", response_model=dict, summary="Record a completed game session")
def record_game_session(session: GameSession) -> dict:
    """
    Record a completed game session with the conversation ID, number picked, and outcome.

    - **conversation_id**: Unique identifier for the conversation/game session
    - **number_picked**: The number that was picked in the game (minimum: 1)
    - **status**: Whether the player won or lost the game (must be 'won' or 'lost')
    """
    # Create new session record
    new_session = {
        "id": f"{session.conversation_id}_{datetime.now().isoformat()}",
        "timestamp": datetime.now().isoformat(),
        "conversation_id": session.conversation_id,
        "number_picked": session.number_picked,
        "status": session.status
    }

    # Save to Cosmos DB
    container.create_item(body=new_session)

    return {
        "message": f"Game session recorded: {session.status} (number: {session.number_picked}, conversation: {session.conversation_id})",
        "session_id": new_session["id"]
    }

@app.get("/sessions", response_model=List[GameSessionResponse], summary="Retrieve recent game sessions")
def get_recent_sessions(limit: int = 10) -> List[GameSessionResponse]:
    """
    Retrieve the last N game sessions with all details.

    - **limit**: Maximum number of sessions to retrieve (default: 10, max: 100)
    """
    if limit < 1 or limit > 100:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 100")

    # Query Cosmos DB for recent sessions, ordered by timestamp descending
    query = f"SELECT * FROM c ORDER BY c.timestamp DESC OFFSET 0 LIMIT {limit}"
    sessions = list(container.query_items(
        query=query,
        enable_cross_partition_query=True
    ))

    return sessions

@app.get("/sessions/last", response_model=GameSessionResponse, summary="Get the most recent game session")
def get_last_game_outcome() -> GameSessionResponse:
    """
    Check if the player won or lost their most recent game.

    Returns details of the last game session including outcome, number picked, and timestamp.
    """
    # Query Cosmos DB for the most recent session
    query = "SELECT TOP 1 * FROM c ORDER BY c.timestamp DESC"
    sessions = list(container.query_items(
        query=query,
        enable_cross_partition_query=True
    ))

    if not sessions:
        raise HTTPException(status_code=404, detail="No game sessions found. Player has not played any games yet.")

    return sessions[0]

@app.get("/health", summary="Health check endpoint")
def health_check() -> dict:
    """Health check endpoint to verify API is running."""
    return {"status": "healthy"}
