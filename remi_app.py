import sys
import os
import random
import pygame
import json
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
import speech_recognition as sr
from gtts import gTTS
import sounddevice as sd
import soundfile as sf
import numpy as np
import queue
import threading
import tempfile
from datetime import datetime
import google.generativeai as genai
import pandas as pd

# Configure Gemini
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', "AIzaSyBIme458y1fI4BdfIr-diMqhGTHZ-j3yC4")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("models/gemini-1.5-pro-latest")

def safe_gemini_call(prompt):
    """Safely call Gemini API with fallback"""
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"Gemini error: {e}")
        return None

class AudioManager:
    def __init__(self):
        self.audio_queue = queue.Queue()
        self.is_listening = False
        self.recognizer = sr.Recognizer()
        self.is_speaking = False
        
        # Configure recognizer for better performance
        self.recognizer.energy_threshold = 300
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.pause_threshold = 0.8
        self.recognizer.phrase_threshold = 0.3
        self.recognizer.non_speaking_duration = 0.5
        
    def speak(self, text):
        """Generate and play speech using gTTS"""
        try:
            self.is_speaking = True
            
            # Create temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as temp_file:
                temp_path = temp_file.name
                
            # Generate speech with better quality
            tts = gTTS(text=text, lang='en-us', slow=False)
            tts.save(temp_path)
            
            # Play audio with better settings
            pygame.mixer.init()
            pygame.mixer.music.load(temp_path)
            pygame.mixer.music.play()
            
            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)
            
            # Cleanup
            pygame.mixer.music.stop()
            pygame.mixer.quit()
            os.unlink(temp_path)
            
            # Wait a moment after speaking before allowing new input
            QThread.msleep(1000)
            self.is_speaking = False
            
        except Exception as e:
            print(f"Speech error: {e}")
            print(text)  # Fallback to print
            self.is_speaking = False

    def start_listening(self):
        """Start listening in a separate thread"""
        # Wait a moment after any previous speech
        QThread.msleep(1000)
        self.is_listening = True
        threading.Thread(target=self._listen_loop, daemon=True).start()

    def stop_listening(self):
        """Stop the listening loop"""
        self.is_listening = False

    def _listen_loop(self):
        """Continuous listening loop with improved recognition"""
        while self.is_listening:
            try:
                # Skip if we're currently speaking
                if self.is_speaking:
                    QThread.msleep(100)
                    continue
                    
                with sr.Microphone(sample_rate=16000) as source:
                    # Better calibration
                    self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                    
                    # Listen for audio with better settings
                    audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=5)
                    
                    try:
                        # Try Google Speech Recognition
                        text = self.recognizer.recognize_google(audio, language='en-US', show_all=True)
                        if text and isinstance(text, dict) and 'alternative' in text:
                            best_result = text['alternative'][0]['transcript'].lower().strip()
                            if best_result:
                                # Only add to queue if we're not speaking
                                if not self.is_speaking:
                                    self.audio_queue.put(best_result)
                    except sr.UnknownValueError:
                        continue
                    except sr.RequestError:
                        continue
            except Exception:
                continue

    def get_audio_input(self, timeout=5):
        """Get audio input from the queue"""
        try:
            return self.audio_queue.get(timeout=timeout)
        except queue.Empty:
            return None

class MemoryGame:
    def __init__(self):
        self.questions = []
        self.current_index = 0
        self.score = 0
        self.consecutive_correct = 0
        self.conversation_history = []
        self.difficulty_progression = ['easy', 'easy', 'medium', 'medium', 'hard']
        self.current_difficulty_index = 0
        
        # Load questions from Excel file
        try:
            df = pd.read_excel('Remi_Memory_Questions.xlsx')
            
            # Group questions by difficulty
            questions_by_difficulty = {
                'easy': [],
                'medium': [],
                'hard': []
            }
            
            # Convert DataFrame to question format and group by difficulty
            for _, row in df.iterrows():
                try:
                    question_text = str(row['Question'])
                    difficulty = str(row['Difficulty']).lower()
                    
                    # Generate appropriate answers based on the question type
                    answers = self._generate_answers(question_text)
                    
                    question = {
                        "question": question_text,
                        "answers": answers,
                        "difficulty": difficulty
                    }
                    
                    if difficulty in questions_by_difficulty:
                        questions_by_difficulty[difficulty].append(question)
                except Exception as e:
                    print(f"Error processing row: {e}")
                    continue
            
            # Shuffle questions within each difficulty
            for difficulty in questions_by_difficulty:
                random.shuffle(questions_by_difficulty[difficulty])
            
            # Select questions based on difficulty progression
            for target_difficulty in self.difficulty_progression:
                if questions_by_difficulty[target_difficulty]:
                    self.questions.append(questions_by_difficulty[target_difficulty].pop(0))
            
            print(f"Loaded {len(self.questions)} questions from Remi_Memory_Questions.xlsx")
            
        except Exception as e:
            print(f"Error loading questions: {e}")
            print("Please make sure Remi_Memory_Questions.xlsx exists and has the correct format")
            sys.exit(1)
            
    def _generate_answers(self, question):
        """Generate appropriate answers based on the question type"""
        question = question.lower()
        
        # Time-related questions
        if "time" in question or "clock" in question:
            return ["time", "the time", "what time", "current time", "now", "present time", 
                   "it's time", "the current time", "what's the time", "tell me the time"]
            
        # Date-related questions
        if "date" in question or "day" in question:
            return ["date", "the date", "today's date", "current date", "today", "present date",
                   "what's the date", "tell me the date", "what day is it", "the current date"]
            
        # Location questions
        if "where" in question or "location" in question:
            return ["here", "this place", "current location", "my location", "present location", 
                   "where I am", "I am here", "this is where I am", "my current location", 
                   "where we are", "this location"]
            
        # Name questions
        if "name" in question:
            return ["name", "my name", "your name", "the name", "what's my name", "who am I",
                   "my name is", "I am", "this is", "it's", "that's my name", "my name would be"]
            
        # Memory questions
        if "remember" in question or "memory" in question:
            return ["yes", "I remember", "I recall", "I know", "I can remember", "I do remember",
                   "yes I remember", "I can recall", "I do recall", "I remember that", "yes I do"]
            
        # Yes/No questions
        if question.startswith(("are you", "is it", "do you", "have you", "can you")):
            return ["yes", "no", "maybe", "I think so", "I don't think so", "not sure", 
                   "I'm not sure", "I don't know", "possibly", "probably", "definitely"]
            
        # Default answers for unknown question types
        return ["yes", "no", "maybe", "I don't know", "I'm not sure", "I think so", 
                "I don't think so", "possibly", "probably", "definitely", "not sure"]
        
    def check_answer(self, user_answer, correct_answers):
        """Check if the answer is correct using semantic understanding"""
        if not user_answer:
            return False
            
        # Clean and normalize the user's answer
        user_answer = user_answer.lower().strip()
        # Remove commas and other punctuation
        user_answer = ''.join(c for c in user_answer if c.isalnum() or c.isspace())
        
        # Normalize all correct answers to lowercase and remove punctuation
        correct_answers = [''.join(c for c in answer.lower().strip() if c.isalnum() or c.isspace()) 
                         for answer in correct_answers]
        
        # First try exact match
        if user_answer in correct_answers:
            return True
            
        # Special handling for breakfast answers
        if any('breakfast' in answer.lower() for answer in correct_answers):
            # Check if the answer is a valid breakfast food
            breakfast_foods = {
                'eggs', 'toast', 'cereal', 'oatmeal', 'pancakes', 'waffles',
                'bacon', 'sausage', 'fruit', 'yogurt', 'coffee', 'tea',
                'juice', 'milk', 'bagel', 'muffin', 'granola', 'smoothie'
            }
            if user_answer in breakfast_foods:
                return True
            
            # Check for plural forms
            if user_answer.endswith('s') and user_answer[:-1] in breakfast_foods:
                return True
            
            # Check for common variations
            breakfast_variations = {
                'egg': 'eggs',
                'toasted': 'toast',
                'cereals': 'cereal',
                'oat': 'oatmeal',
                'pancake': 'pancakes',
                'waffle': 'waffles',
                'fruits': 'fruit',
                'yoghurt': 'yogurt',
                'coffees': 'coffee',
                'teas': 'tea',
                'juices': 'juice',
                'milks': 'milk',
                'bagels': 'bagel',
                'muffins': 'muffin',
                'smoothies': 'smoothie'
            }
            if user_answer in breakfast_variations:
                return True
        
        # Create a detailed prompt for Gemini to analyze the answer semantically
        prompt = f"""Analyze if the user's answer is semantically correct based on the expected answers.
        Consider key concepts, synonyms, and related terms, not just exact word matches.
        Ignore capitalization differences and punctuation.
        
        User's answer: "{user_answer}"
        Expected answers: {correct_answers}
        
        Consider:
        1. Key concepts and main ideas
        2. Synonyms and related terms
        3. Context and meaning
        4. Common variations of the answer
        5. Semantic equivalence
        6. Natural language variations
        7. Informal expressions
        8. Ignore punctuation and spacing differences
        9. Consider singular/plural forms as equivalent
        
        Return only 'true' if the answer is semantically correct, or 'false' if it's not.
        Be lenient with exact wording but strict with meaning."""
        
        # Try Gemini first
        result = safe_gemini_call(prompt)
        if result:
            result = result.lower().strip()
            
            # If Gemini returns a clear true/false, use that
            if result in ['true', 'false']:
                return result == 'true'
                
            # If Gemini returns a more detailed response, analyze it
            if 'correct' in result or 'right' in result or 'valid' in result:
                return True
            if 'incorrect' in result or 'wrong' in result or 'invalid' in result:
                return False
        
        # Fallback to semantic matching using word analysis
        user_words = set(user_answer.split())
        for answer in correct_answers:
            answer_words = set(answer.split())  # Already lowercase and punctuation-free
            
            # Check for significant word overlap
            overlap = len(user_words.intersection(answer_words))
            if overlap >= len(answer_words) * 0.7:
                return True
                
            # Check for key word presence
            key_words = [word for word in answer_words if len(word) > 3]  # Ignore short words
            if all(word in user_words for word in key_words):
                return True
                
            # Check for similar words using character matching
            for user_word in user_words:
                for answer_word in answer_words:
                    if len(user_word) > 3 and len(answer_word) > 3:  # Only compare longer words
                        # Check if words are similar (80% character match)
                        if self._similar_words(user_word, answer_word):
                            return True
                
        return False
        
    def _similar_words(self, word1, word2):
        """Check if two words are similar using character matching"""
        if len(word1) < 4 or len(word2) < 4:
            return False
            
        # Calculate character overlap
        overlap = sum(1 for a, b in zip(word1, word2) if a == b)
        return overlap / max(len(word1), len(word2)) >= 0.8

    def get_current_question(self):
        """Get the current question"""
        if self.current_index < len(self.questions):
            return self.questions[self.current_index]
        return None

    def get_current_difficulty(self):
        """Get the current difficulty level"""
        if self.current_index < len(self.difficulty_progression):
            return self.difficulty_progression[self.current_index]
        return None

    def add_to_history(self, question, answer, is_correct):
        """Add interaction to conversation history"""
        self.conversation_history.append({
            "timestamp": datetime.now().isoformat(),
            "question": question,
            "answer": answer,
            "is_correct": is_correct
        })

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Memory Check")
        self.setGeometry(100, 100, 800, 600)
        self.setStyleSheet("background-color: #2C3E50;")
        
        # Initialize components
        self.audio_manager = AudioManager()
        
        # Setup UI
        self.setup_ui()
        
        # Initialize counters
        self.wrong_attempts = 0
        self.correct_count = 0
        self.current_question = 0
        
    def setup_ui(self):
        # Main widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setSpacing(20)
        layout.setContentsMargins(50, 50, 50, 50)

        # Title
        title = QLabel("Daily Check")
        title.setStyleSheet("""
            QLabel {
                color: #3498DB;
                font-size: 48px;
                font-weight: bold;
            }
        """)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Progress circle
        self.progress_circle = QLabel("0%")
        self.progress_circle.setStyleSheet("""
            QLabel {
                color: white;
                background-color: #34495E;
                border: 3px solid #34495E;
                border-radius: 100px;
                font-size: 36px;
                font-weight: bold;
            }
        """)
        self.progress_circle.setFixedSize(200, 200)
        self.progress_circle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.progress_circle, alignment=Qt.AlignmentFlag.AlignCenter)

        # Small circles container
        circles_widget = QWidget()
        circles_layout = QHBoxLayout(circles_widget)
        circles_layout.setSpacing(10)
        self.circles = []
        
        for _ in range(5):
            circle = QFrame()
            circle.setFixedSize(30, 30)
            circle.setStyleSheet("""
                QFrame {
                    background-color: #34495E;
                    border: 2px solid #34495E;
                    border-radius: 15px;
                }
            """)
            circles_layout.addWidget(circle)
            self.circles.append(circle)
        
        layout.addWidget(circles_widget, alignment=Qt.AlignmentFlag.AlignCenter)

        # Question display
        self.question_label = QLabel("Welcome! I'm Remi, your memory friend. Let's start today's memory check.")
        self.question_label.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 24px;
                padding: 20px;
                background-color: #34495E;
                border-radius: 10px;
            }
        """)
        self.question_label.setWordWrap(True)
        self.question_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.question_label)

        # User answer display
        self.answer_label = QLabel("")
        self.answer_label.setStyleSheet("""
            QLabel {
                color: #3498DB;
                font-size: 20px;
                padding: 10px;
                background-color: #34495E;
                border-radius: 10px;
            }
        """)
        self.answer_label.setWordWrap(True)
        self.answer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.answer_label)

        # Status label
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("""
            QLabel {
                color: #E74C3C;
                font-size: 16px;
                padding: 10px;
            }
        """)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)

        # Start button
        self.start_button = QPushButton("Start")
        self.start_button.setStyleSheet("""
            QPushButton {
                background-color: #3498DB;
                color: white;
                border: none;
                border-radius: 20px;
                padding: 15px 32px;
                font-size: 20px;
                min-width: 200px;
            }
            QPushButton:hover {
                background-color: #2980B9;
            }
            QPushButton:disabled {
                background-color: #95A5A6;
            }
        """)
        self.start_button.clicked.connect(self.start_game)
        layout.addWidget(self.start_button, alignment=Qt.AlignmentFlag.AlignCenter)

    def start_game(self):
        self.start_button.setEnabled(False)
        # Create a new game instance
        self.game = MemoryGame()
        self.correct_count = 0
        self.current_question = 0
        self.wrong_attempts = 0
        self.status_label.setText("")
        self.answer_label.setText("")
        
        # Reset circles and progress circle
        for circle in self.circles:
            circle.setStyleSheet("""
                QFrame {
                    background-color: #34495E;
                    border: 2px solid #34495E;
                    border-radius: 15px;
                }
            """)
            
        self.progress_circle.setStyleSheet("""
            QLabel {
                color: white;
                background-color: #34495E;
                border: 3px solid #34495E;
                border-radius: 100px;
                font-size: 36px;
                font-weight: bold;
            }
        """)
        
        # Generate personalized greeting using Gemini
        prompt = f"""Generate a friendly greeting for a memory check session. 
        The greeting should be warm, encouraging, and brief (1-2 sentences).
        Include the name 'Remi' and mention that we're starting today's memory check."""
        
        try:
            greeting = model.generate_content(prompt).text
        except:
            greeting = "Welcome! I'm Remi, your memory friend. Let's start today's memory check."
        
        # Show greeting first, then speak
        self.question_label.setText(greeting)
        QTimer.singleShot(500, lambda: self.audio_manager.speak(greeting))
        QTimer.singleShot(2500, self.ask_question)  # Increased delay to 2.5 seconds
        
    def ask_question(self):
        question = self.game.get_current_question()
        if question:
            # Show question first
            self.question_label.setText(question["question"])
            self.status_label.setText("Listening...")
            self.answer_label.setText("")
            
            # Speak after a short delay
            QTimer.singleShot(500, lambda: self.audio_manager.speak(question["question"]))
            
            # Start listening for answer after speech is complete
            QTimer.singleShot(1500, lambda: self.audio_manager.start_listening())
            QTimer.singleShot(1600, self.check_for_answer)
        else:
            self.game_over()
            
    def check_for_answer(self):
        answer = self.audio_manager.get_audio_input()
        if answer:
            self.audio_manager.stop_listening()
            question = self.game.get_current_question()
            
            # Show user's answer
            self.answer_label.setText(f"You said: {answer}")
            
            is_correct = self.game.check_answer(answer, question["answers"])
            self.game.add_to_history(question["question"], answer, is_correct)
            
            if is_correct:
                self.correct_answer()
            else:
                self.wrong_answer()
        else:
            # Continue checking for answer
            QTimer.singleShot(100, self.check_for_answer)
            
    def correct_answer(self):
        self.correct_count += 1
        
        # Update progress circle with difficulty-based color
        progress = (self.correct_count / 5) * 100
        self.progress_circle.setText(f"{int(progress)}%")
        
        # Get current difficulty and set color
        current_difficulty = self.game.get_current_difficulty()
        if current_difficulty == 'easy':
            color = "#FFD700"  # Yellow
        elif current_difficulty == 'medium':
            color = "#FFA500"  # Orange
        else:
            color = "#FF4444"  # Red
            
        self.progress_circle.setStyleSheet(f"""
            QLabel {{
                color: white;
                background-color: {color};
                border: 3px solid {color};
                border-radius: 100px;
                font-size: 36px;
                font-weight: bold;
            }}
        """)
        
        self.status_label.setText("Correct! Well done!")
        
        # Update circle with animation
        circle = self.circles[self.correct_count - 1]
        circle.setStyleSheet(f"""
            QFrame {{
                background-color: {color};
                border: 2px solid {color};
                border-radius: 15px;
            }}
        """)
        
        # Move to next question
        self.game.current_index += 1
        self.game.consecutive_correct += 1
        
        if self.correct_count >= 5:
            self.game_over()
        else:
            # Generate personalized response using Gemini
            prompt = f"""Generate a brief, encouraging response for a correct answer in a memory check.
            The response should be positive and motivating (1 sentence).
            Current progress: {self.correct_count}/5 questions correct.
            Current difficulty: {current_difficulty}."""
            
            try:
                response = model.generate_content(prompt).text
            except:
                response = random.choice([
                    "Excellent! That's correct!",
                    "Perfect! Well done!",
                    "Great job! Keep going!",
                    "That's right! You're doing great!",
                    "Wonderful! Next question!"
                ])
            
            # Show response first, then speak
            self.status_label.setText(response)
            QTimer.singleShot(500, lambda: self.audio_manager.speak(response))
            QTimer.singleShot(2500, self.ask_question)
            
    def wrong_answer(self):
        self.game.consecutive_correct = 0
        self.wrong_attempts += 1  # Increment wrong attempts counter
        
        if self.wrong_attempts >= 3:
            # Skip the question after 3 wrong attempts
            self.status_label.setText("Let's move on to the next question.")
            
            # Generate response for skipping question
            prompt = """Generate a gentle message for when we're moving on to the next question after multiple attempts.
            The message should be encouraging and supportive (1 sentence)."""
            
            try:
                response = model.generate_content(prompt).text
            except:
                response = "Let's move on to the next question. You're doing great!"
            
            # Show response first, then speak
            self.status_label.setText(response)
            QTimer.singleShot(500, lambda: self.audio_manager.speak(response))
            
            # Reset wrong attempts counter and move to next question
            self.wrong_attempts = 0
            self.game.current_index += 1
            QTimer.singleShot(2500, self.ask_question)
        else:
            # Normal wrong answer handling
            self.status_label.setText(f"Let's try again! (Attempt {self.wrong_attempts}/3)")
            
            # Generate encouraging response using Gemini
            prompt = f"""Generate a gentle, encouraging response for an incorrect answer in a memory check.
            The response should be supportive and motivate the user to try again (1 sentence).
            Keep it positive and kind. This is attempt {self.wrong_attempts} out of 3."""
            
            try:
                response = model.generate_content(prompt).text
            except:
                response = f"That's not quite right, but you're doing great! Let's try again. (Attempt {self.wrong_attempts}/3)"
            
            # Show response first, then speak
            self.status_label.setText(response)
            QTimer.singleShot(500, lambda: self.audio_manager.speak(response))
            QTimer.singleShot(2500, self.ask_question)
        
    def game_over(self):
        self.audio_manager.stop_listening()
        self.start_button.setEnabled(True)
        
        if self.correct_count >= 5:
            # Generate congratulatory message using Gemini
            prompt = """Generate a congratulatory message for completing all memory check questions successfully.
            The message should be warm and encouraging (1-2 sentences)."""
            
            try:
                message = model.generate_content(prompt).text
            except:
                message = "Great job! You've completed all questions successfully!"
            
            self.status_label.setText("Congratulations! You've completed all questions!")
        else:
            # Generate encouraging message using Gemini
            prompt = """Generate an encouraging message for when the memory check session ends before completion.
            The message should be supportive and motivate the user to try again (1-2 sentences)."""
            
            try:
                message = model.generate_content(prompt).text
            except:
                message = "Let's try again another time."
            
            self.status_label.setText("Keep practicing! You're doing great!")
        
        # Show message first, then speak
        self.question_label.setText(message)
        QTimer.singleShot(500, lambda: self.audio_manager.speak(message))
        
        # Save conversation history
        try:
            with open("conversation_data.json", "a") as f:
                json.dump({
                    "timestamp": datetime.now().isoformat(),
                    "session_summary": self.game.conversation_history,
                    "final_score": self.correct_count
                }, f)
                f.write(os.linesep)
        except Exception as e:
            print(f"Error saving conversation data: {e}")

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main() 