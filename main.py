from fastapi import FastAPI, WebSocket, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import speech_recognition as sr
import pandas as pd
import google.generativeai as genai
from elevenlabs.client import ElevenLabs
import pygame
import os
from pydantic import BaseModel
import json
from typing import Optional
import uvicorn

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure API keys
GEMINI_API_KEY = "YOUR_GEMINI_API_KEY"
ELEVEN_API_KEY = "YOUR_ELEVENLABS_API_KEY"

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.0-flash")

# Initialize ElevenLabs client
eleven_labs = ElevenLabs(api_key=ELEVEN_API_KEY)

# Load questions from Excel
try:
    questions_df = pd.read_excel("Game_Questions.xlsx")
    questions_df.columns = [col.strip().lower() for col in questions_df.columns]
except Exception as e:
    questions_df = None
    print(f"Error loading questions: {e}")

class GameSession:
    def __init__(self):
        self.correct_answers = 0
        self.total_attempts = 0
        self.current_difficulty = "easy"
        self.user_name = None

    def get_difficulty(self):
        if self.correct_answers < 2:
            return "easy"
        elif self.correct_answers < 4:
            return "medium"
        else:
            return "hard"

class UserInput(BaseModel):
    audio_data: str
    session_id: str

class SessionResponse(BaseModel):
    session_id: str
    user_name: Optional[str] = None

# Store active sessions
sessions = {}

@app.post("/start_session")
async def start_session():
    session_id = str(len(sessions) + 1)
    sessions[session_id] = GameSession()
    return {"session_id": session_id, "message": "Session started"}

@app.post("/process_audio")
async def process_audio(user_input: UserInput):
    session = sessions.get(user_input.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Process audio input (in a real implementation, you'd handle the audio data)
    r = sr.Recognizer()
    try:
        # Here you would process the actual audio data
        # For demo, we'll assume text input
        text = "Sample response"  # Replace with actual speech recognition
        return {"text": text}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/get_question/{session_id}")
async def get_question(session_id: str):
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if not questions_df is not None:
        raise HTTPException(status_code=500, detail="Questions database not loaded")

    difficulty = session.get_difficulty()
    questions = questions_df[questions_df["difficulty level"].str.lower() == difficulty]
    
    if questions.empty:
        raise HTTPException(status_code=404, detail="No questions available")
    
    question = questions.sample(1).iloc[0]
    return {
        "question_text": question["question text"],
        "difficulty": difficulty,
        "progress": {
            "correct_answers": session.correct_answers,
            "total_attempts": session.total_attempts
        }
    }

@app.post("/check_answer/{session_id}")
async def check_answer(session_id: str, answer: str, question: str):
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Use Gemini to evaluate the answer
    prompt = f"Was the answer '{answer}' correct for the question '{question}'? Respond with 'correct' or 'incorrect'."
    response = model.generate_content(prompt)
    
    is_correct = "correct" in response.text.lower()
    
    if is_correct:
        session.correct_answers += 1
    session.total_attempts += 1

    return {
        "is_correct": is_correct,
        "progress": {
            "correct_answers": session.correct_answers,
            "total_attempts": session.total_attempts
        }
    }

@app.post("/generate_audio")
async def generate_audio(text: str):
    try:
        audio = eleven_labs.generate(
            text=text,
            voice="Rachel",
            model="eleven_multilingual_v2"
        )
        
        # In a real implementation, you'd handle the audio data appropriately
        # For demo, we'll just return success
        return {"status": "success", "message": "Audio generated"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()
    
    session = sessions.get(session_id)
    if not session:
        await websocket.close(code=4000)
        return

    try:
        while True:
            data = await websocket.receive_text()
            # Handle real-time communication
            await websocket.send_text(f"Message received: {data}")
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        await websocket.close()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
    

