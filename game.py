# Remi - Memory Game with Emotion Detection and Voice-Only Interaction

import os
import random
import datetime
import time
import pandas as pd
import matplotlib.pyplot as plt
import speech_recognition as sr
import pygame
import json
import requests
from dotenv import load_dotenv
from google.cloud import speech_v1p1beta1 as speech
from google.oauth2 import service_account

# Load environment variables
load_dotenv()

# API Keys
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
ELEVENLABS_API_KEY = os.getenv('ELEVENLABS_API_KEY')

# File paths
QUESTIONS_FILE = "Game_Questions.xlsx"
LOG_FILE = "Alzheimer_Log.xlsx"
PATIENT_FILE = "David_Lee_Info.xlsx"

# ============ AUDIO ============

def speak(text):
    try:
        url = "https://api.elevenlabs.io/v1/text-to-speech/21m00Tcm4TlvDq8ikWAM"
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": ELEVENLABS_API_KEY
        }
        data = {
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {
                "stability": 0.3,
                "similarity_boost": 0.8
            }
        }
        response = requests.post(url, json=data, headers=headers)

        if response.status_code == 200:
            with open("temp_audio.mp3", "wb") as f:
                f.write(response.content)
            pygame.mixer.init()
            pygame.mixer.music.load("temp_audio.mp3")
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)
            pygame.mixer.quit()
            os.remove("temp_audio.mp3")
        else:
            print(f"Error generating speech: {response.status_code}")
            print(text)
    except Exception as e:
        print(f"Speech generation error: {e}")
        print(text)

def listen():
    r = sr.Recognizer()
    with sr.Microphone() as source:
        print("Listening...")
        r.adjust_for_ambient_noise(source)
        audio = r.listen(source)
    try:
        user_input = r.recognize_google(audio)
        print(f"You said: {user_input}")
        user_answer = ''.join(c for c in user_input if c.isalnum() or c.isspace())
        return user_answer.lower().strip()
    except sr.UnknownValueError:
        print("Could not understand.")
        return None
    except sr.RequestError:
        print("Speech recognition error.")
        return None

# ============ EMOTION (Mocked) ============

def detect_emotion(text):
    sad_keywords = ["sad", "upset", "tired", "bad", "not good"]
    for word in sad_keywords:
        if word in text:
            return "sad"
    return "neutral"

# ============ PATIENT INFO ============

def get_patient_info():
    name = "Friend"
    if os.path.exists(PATIENT_FILE):
        df = pd.read_excel(PATIENT_FILE)
        if not df.empty and 'name' in df.columns:
            name = df.iloc[0]['name']
    return name

# ============ QUESTIONS ============

class QuestionManager:
    def __init__(self):
        self.correct_count = 0
        self.attempt_count = 0
        self.level_order = ['E', 'M', 'H']
        self.level_progress = {'E': 0, 'M': 0, 'H': 0}
        self.current_level = 'E'
        self.questions = {
            'E': [
                {"question": "What is your favorite color?", "answer": "red"},
                {"question": "What animal says 'meow'?", "answer": "cat"}
            ],
            'M': [
                {"question": "What did you have for lunch yesterday?", "answer": "lasagna"},
                {"question": "What's the name of your doctor?", "answer": "georges"}
            ],
            'H': [
                {"question": "What did you do last weekend with your family?", "answer": "went to the park"},
                {"question": "What medications did you take this morning?", "answer": "aspirin"}
            ]
        }
        self.used_indices = {'E': set(), 'M': set(), 'H': set()}
        self.wrong_attempts = 0

    def get_next_question(self):
        available = [i for i in range(len(self.questions[self.current_level])) if i not in self.used_indices[self.current_level]]
        if not available:
            return None
        index = random.choice(available)
        self.used_indices[self.current_level].add(index)
        return self.questions[self.current_level][index]

    def update_progress(self, correct):
        self.attempt_count += 1
        if correct:
            self.correct_count += 1
            self.level_progress[self.current_level] += 1
            if self.current_level == 'E' and self.level_progress['E'] >= 2:
                self.current_level = 'M'
            elif self.current_level == 'M' and self.level_progress['M'] >= 2:
                self.current_level = 'H'
        # no change if incorrect

# ============ MAIN GAME FLOW ============

class RemiGame:
    def __init__(self):
        self.name = get_patient_info()
        self.qm = QuestionManager()
        self.wrong_attempts = 0

    def run(self):
        # Greeting
        while True:
            speak("Hi, I'm Remi, your memory friend. Are you ready for today's memory game?")
            response = listen()
            if response:
                mood = detect_emotion(response)
                if mood == "sad":
                    speak("Is something wrong? Want me to cheer you up?")
                    continue
                elif "yes" in response:
                    break
                else:
                    speak("Please say yes when you're ready.")
            else:
                speak("I didn't hear you. Can you try again?")

        speak(f"Welcome back, {self.name}! Let's start your daily memory check. Say 'yes' to start, or tell me if something is wrong.")

        while True:
            confirm = listen()
            if confirm:
                if detect_emotion(confirm) == "sad":
                    speak("I'm here for you. Let's play when you're ready.")
                    continue
                elif "yes" in confirm:
                    break
                else:
                    speak("Say yes to start, or let me know if something's wrong.")
            else:
                speak("Didn't catch that, please try again.")

        # Questions
        while self.qm.correct_count < 5:
            q = self.qm.get_next_question()
            if not q:
                speak("I'm out of questions for now. Let's end today's session.")
                return
            speak(q['question'])
            answer = listen()
            if not answer:
                speak("Could you repeat that?")
                continue
            correct = q['answer'].lower() in answer
            self.qm.update_progress(correct)
            if correct:
                speak("That's correct! Well done!")
            else:
                speak(f"Not quite right. The correct answer was {q['answer']}")
            self.wrong_attempts += 1
            if self.wrong_attempts >= 3:
                speak("You've reached the maximum number of attempts. Let's move to the next question.")
                self.wrong_attempts = 0

        speak(f"Great job today! I'm saving your improvement data. Have a good day, {self.name}!")
        self.save_progress()

    def save_progress(self):
        data = {
            'Date': datetime.date.today(),
            'Name': self.name,
            'Correct Answers': self.qm.correct_count,
            'Total Attempts': self.qm.attempt_count
        }
        df = pd.DataFrame([data])
        if os.path.exists(LOG_FILE):
            df_existing = pd.read_excel(LOG_FILE)
            df = pd.concat([df_existing, df], ignore_index=True)
        df.to_excel(LOG_FILE, index=False)
        self.show_progress(df)

    def show_progress(self, df):
        plt.figure(figsize=(6, 4))
        plt.plot(df['Date'], df['Correct Answers'], marker='o')
        plt.title('Progress Over Time')
        plt.xlabel('Date')
        plt.ylabel('Correct Answers')
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.show()

# ============ RUN ============

if __name__ == "__main__":
    game = RemiGame()
    game.run()
