import os
import random
import datetime
import pandas as pd
import matplotlib.pyplot as plt
import speech_recognition as sr
import pygame  # Pygame import to handle audio
import json
from elevenlabs.client import ElevenLabs
import google.generativeai as genai

# ============ SETUP ============

api_key = "AIzaSyAV1j1IsVCLbcuQHctjBPmXeQacQHGJ-78"

genai.configure(api_key=api_key)
model = genai.GenerativeModel("gemini-2.0-flash")

QUESTIONS_FILE = "Game_Questions.xlsx"
LOG_FILE = "Alzheimer_Log.xlsx"
PATIENT_FILE = "David_Lee_Info.xlsx"

ELEVEN_API_KEY = "sk_8fe5f11d548416473f8176d3b3e394ac2644f21f616f26c1"

# ============ HELPER FUNCTION FOR CORRECTNESS

def is_correct(response_text):
    positive_keywords = ["correct", "right", "exactly", "well done", "fantastic", "great job", "perfect"]
    negative_keywords = ["incorrect", "wrong", "not quite", "try again"]

    response_text_lower = response_text.lower()

    if any(keyword in response_text_lower for keyword in positive_keywords):
        if any(keyword in response_text_lower for keyword in negative_keywords):
            return None # Mixed result, can not evaluate!
        else:
            return True
    elif any(keyword in response_text_lower for keyword in negative_keywords):
        return False
    else:
        return None # Cannot evaluate, maybe prompt was not set up correctly!

# ============ AUDIO ============

def generate_audio(response_text):
    client = ElevenLabs(api_key=ELEVEN_API_KEY)
    audio = client.generate(
        text=response_text,
        voice="Rachel",  # Using Rachel's voice
        model="eleven_multilingual_v2",
        output_format="mp3_44100_128"
    )

    audio_bytes = b"".join([chunk for chunk in audio])

    # Delete the old file if it exists
    if os.path.exists("remi_reply.mp3"):
        os.remove("remi_reply.mp3")
    
    # Save the audio to a file
    with open("remi_reply.mp3", "wb") as f:
        f.write(audio_bytes)

    # Initialize pygame mixer and play the audio
    pygame.mixer.init()
    pygame.mixer.music.load("remi_reply.mp3")
    pygame.mixer.music.play()

    while pygame.mixer.music.get_busy():
        pygame.time.Clock().tick(10)

    # Ensure the music is stopped and the mixer is properly quit
    pygame.mixer.music.stop()
    pygame.mixer.quit()
    pygame.quit()

def speak(text):
    generate_audio(text)  # Use the generate_audio function to play the text

def listen():
    r = sr.Recognizer()
    with sr.Microphone() as source:
        print("\n🎤 Listening...")
        r.adjust_for_ambient_noise(source)
        audio = r.listen(source)
    try:
        user_input = r.recognize_google(audio)
        print(f"🗣 You said: {user_input}")
        return user_input
    except sr.UnknownValueError:
        print("❌ Could not understand.")
        return None  # Return None if no response is captured
    except sr.RequestError:
        print("❌ Speech recognition service error.")
        return None

# ============ GEMINI HELPERS ============

def check_answer_with_gemini(question_text, user_answer, patient_name, patient_hobbies):
    prompt = f"""You are Remi, a gentle and patient memory assistant for {patient_name} who suffers from Alzheimer's disease.  You know that {patient_name} enjoys {patient_hobbies}. Your goal is to encourage and support the patient while providing accurate and helpful feedback.
    The question the patient was asked is: '{question_text}'. The patient answered: '{user_answer}'.
    
    Instead of simply saying "yes" or "no," provide a dynamic and personalized response.
    
    Consider the following guidelines:
    * Be empathetic and understanding. Acknowledge the patient's effort, even if the answer isn't entirely correct.
    * Offer gentle corrections, focusing on what the patient did well and guiding them towards the correct answer.
    * Inject personality: Be warm, supportive, and encouraging. Use phrases like "That's a great try!", "You're getting close!", or "I appreciate your effort." Perhaps you could make a comparison between the answer and {patient_hobbies}!
    * If the answer is correct, offer enthusiastic praise and connect the answer to a related memory or idea to encourage further engagement.
    * Avoid being overly critical or negative. Focus on building confidence and creating a positive experience.
    * Keep your responses brief and easy to understand. Avoid complex language or jargon.
    
    Generate a dynamic and personalized response to the patient's answer. Remember, you are Remi, a kind and patient friend.
    """
    response = model.generate_content(prompt)
    return response.text

# ============ GET PATIENT ============

def get_patient_info():
    patient_name = "there"
    patient_hobbies = "nothing in particular"

    if os.path.exists(PATIENT_FILE):
        df = pd.read_excel(PATIENT_FILE)
        df.columns = [col.lower() for col in df.columns]
        if "name" in df.columns and not df.empty:
            patient_name = str(df.iloc[0]["name"])
        if "hobbies" in df.columns and not df.empty:
            patient_hobbies = str(df.iloc[0]["hobbies"])
    
    return patient_name, patient_hobbies

# ============ QUESTION MANAGER ============

class QuestionManager:
    def __init__(self):
        self.df = pd.read_excel(QUESTIONS_FILE)
        self.df.columns = [col.strip().lower() for col in self.df.columns]

        if "question text" not in self.df.columns or "difficulty level" not in self.df.columns:
            raise ValueError("Excel must have 'Question Text' and 'Difficulty Level' columns.")

        difficulty_map = {"e": "easy", "m": "medium", "h": "hard"}
        self.df["difficulty level"] = (
            self.df["difficulty level"].astype(str).str.strip().str.lower().map(difficulty_map)
        )

        self.df["question text"] = self.df["question text"].astype(str).str.strip()

        self.difficulty = "easy"
        self.correct_streak = 0
        self.incorrect_streak = 0

    def get_question(self):
        pool = self.df[self.df["difficulty level"] == self.difficulty]
        if pool.empty:
            print(f"⚠️ No questions for '{self.difficulty}'. Trying others...")
            for level in ["easy", "medium", "hard"]:
                fallback = self.df[self.df["difficulty level"] == level]
                if not fallback.empty:
                    self.difficulty = level
                    return fallback.sample(1).iloc[0]
            return None
        return pool.sample(1).iloc[0]

    def update_difficulty(self, correct):
        if correct:
            self.correct_streak += 1
            self.incorrect_streak = 0
        else:
            self.incorrect_streak += 1
            self.correct_streak = 0

        if self.correct_streak >= 3 and self.difficulty != "hard":
            self.difficulty = "medium" if self.difficulty == "easy" else "hard"
            self.correct_streak = 0
        elif self.incorrect_streak >= 2 and self.difficulty != "easy":
            self.difficulty = "medium" if self.difficulty == "hard" else "easy"
            self.incorrect_streak = 0

# ============ MAIN SESSION ============

def run_session():
    patient_name, patient_hobbies = get_patient_info()  # Get patient info
    speak(f"Hi {patient_name}, welcome back. Let's begin your memory session.")
    qm = QuestionManager()

    questions_asked = 0
    max_questions = 5

    while questions_asked < max_questions:
        q = qm.get_question()
        if q is None:
            speak("We are not going to work on more questions today.")
            break

        question_text = q["question text"]
        speak(f"Question {questions_asked + 1}: {question_text}")
        print(f"\n🧠 {question_text}")
        answer = listen()  # Get the answer immediately after Remi finishes speaking

        if answer is None:
            speak("You didn't answer anything. Let's try another question.")
            continue

        # Use Gemini to evaluate the answer dynamically
        response_text = check_answer_with_gemini(question_text, answer, patient_name, patient_hobbies)
        speak(response_text)  # Remi's dynamic response

        correct_value = is_correct(response_text)
        if correct_value == True:
            qm.update_difficulty(True)  # Answer was deemed correct
        elif correct_value == False:
            qm.update_difficulty(False)  # Answer was deemed incorrect
        # If it is "None" we can not tell, thus we simply continue!

        questions_asked += 1

    speak("Great job today. Let's check your progress.")

# ============ RUN ============

if __name__ == "__main__":
    run_session()