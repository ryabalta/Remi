

import os
import whisper
import sounddevice as sd
import numpy as np
import scipy.io.wavfile as wav
import tempfile
import google.generativeai as genai
import pygame
import json
import speech_recognition as sr
from elevenlabs.client import ElevenLabs
import datetime  # Import the datetime module
import io
import base64
from fastapi import FastAPI, WebSocket, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Recommended: load your API keys from a .env file for safety
# from dotenv import load_dotenv
# load_dotenv()

# If you're not using .env, define them here directly:

ELEVEN_API_KEY = "sk_a7645b78f9b7a5b0ac2e3df88f228bb88c3858cdc9e7517e"
GEMINI_API_KEY = "AIzaSyBIme458y1fI4BdfIr-diMqhGTHZ-j3yC4"

# Add ffmpeg path to system PATH
os.environ["PATH"] += os.pathsep + r"C:\\Users\\antoi\\Downloads\\ffmpeg-7.1.1-essentials_build\\bin"

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("models/gemini-1.5-pro-latest")
# embedding_model = genai.EmbeddingModel("models/embedding-001")  # Removed deprecated EmbeddingModel

# Load patient profile (replace with your actual patient profile loading)
PATIENT_FILE = "David_Lee_Info.xlsx"

def load_patient_profile(filename):
    #Dummy Data
    return {"preferred_tone": "gentle", "interests": "gardening, old movies", "level_of_formality": "informal"}

patient_profile = load_patient_profile(PATIENT_FILE)


# A simple memory management to store conversation context
def load_memory():
    if os.path.exists('conversation_memory.json'):
        with open('conversation_memory.json', 'r') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                print("Conversation memory is empty or malformed. Starting fresh.")
                return {"conversation": []}
    else:
        return {"conversation": []}

def save_to_memory(conversation_data):
    with open('conversation_memory.json', 'w') as f:
        json.dump(conversation_data, f)

# Record audio
def record_audio(duration=10, sample_rate=44100):
    print("🎤 Speak now...")
    recording = sd.rec(int(duration * sample_rate), samplerate=sample_rate, channels=1, dtype='int16')
    sd.wait()
    return recording

# Save audio to temp file
# def save_audio_to_temp_file(recording, sample_rate=44100):
#     with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
#         wav.write(f.name, sample_rate, recording)
#         return f.name

# Transcribe audio with Whisper
def transcribe_audio(audio_path):
    print("📝 Transcribing...")
    try:
        # Load model once and keep it in memory
        if not hasattr(transcribe_audio, 'model'):
            transcribe_audio.model = whisper.load_model("base")
        
        # Transcribe the audio file
        text = transcribe_audio.model.transcribe(audio_path,fp16=False)["text"]
        print(f"📣 You said: {text}")
        return text
    except Exception as e:
        print(f"Error in transcription: {str(e)}")
        return "I couldn't understand what you said. Could you please try again?"


def summarize_conversation(conversation_history):
    """Summarizes the conversation history for better context."""
    if not conversation_history:
        return ""

    prompt = f"""You are summarizing a conversation to help a memory assistant stay on track with their Alzheimer's patient.

    Here is the conversation:
    {conversation_history}

    Provide a short summary of the key topics and any important details mentioned. Keep it concise.
    """
    response = model.generate_content(prompt)
    return response.text

def generate_embedding(text):
    """Generates an embedding for the given text using the generative model and embedContent."""
    try:
        # Embed the text content
        result = model.embed_content(content=text)

        # Check if the 'embedding' key exists in the result
        if 'embedding' in result:
            return result['embedding']
        else:
            print("The 'embedding' key is missing from the result.")
            return None  # Handle the case where the key is missing

    except Exception as e:
        print(f"An error occurred during embedding: {e}")
        return None



# Ask Gemini and keep the conversation going
def ask_gemini(conversation_history, user_input, user_name="", first_turn=False):
    if first_turn:
        prompt = f"You are Remi, a gentle memory assistant for an Alzheimer's patient. You are beginning a conversation with a person named '{user_name}'. Greet {user_name} with a friendly and unique greeting. Ask how they are doing, but try to ask a different question each time. Do not make it more than one sentence!"
        response = model.generate_content(prompt)
        return response.text

    # Only summarize conversation if it's longer than 5 exchanges
    if len(conversation_history) > 5:
        conversation_summary = summarize_conversation(conversation_history)
    else:
        conversation_summary = "\n".join(conversation_history)

    tone_setting = patient_profile["preferred_tone"]
    formality_setting = patient_profile["level_of_formality"]
    prompt = f"""You are Remi, a gentle, patient, kind, encouraging, and empathetic memory assistant for an Alzheimer's patient.
    You know the patient enjoys {patient_profile['interests']}.  Respond with a {tone_setting} tone.  Speak to the patient with a {formality_setting} level of formality. Your goal is to support the patient, create a positive experience, and build their confidence. Respond clearly and kindly to the following: "{user_input}". Remember to be warm, understanding, and easy to follow. If appropriate, use a bit of gentle humor. Keep your response concise and direct."""

    # Combine the conversation history with the new prompt
    conversation_context = f"Conversation Summary: {conversation_summary}\n"
    full_prompt = conversation_context + "\n" + prompt

    print("🤖 Asking Remi...")
    response = model.generate_content(full_prompt)
    return response.text

# Generate and play audio using ElevenLabs
def generate_audio(response_text):
    client = ElevenLabs(api_key=ELEVEN_API_KEY)
    audio = client.generate(
        text=response_text,
        voice="Rachel",  # Other options: "Bella", "Ellie"
        model="eleven_multilingual_v2",
        output_format="mp3_44100_128"
    )

    audio_bytes = b"".join([chunk for chunk in audio])

    # Play directly from memory instead of saving to file
    audio_file = io.BytesIO(audio_bytes)
    
    # Initialize pygame mixer and play the audio
    pygame.mixer.init()
    pygame.mixer.music.load(audio_file)
    pygame.mixer.music.play()

    while pygame.mixer.music.get_busy():
        pygame.time.Clock().tick(10)

    # Cleanup
    pygame.mixer.music.stop()
    pygame.mixer.quit()
    pygame.quit()

# Function to listen to speech 
def listen_and_transcribe():
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        print("🎤 Remi is listening...") # Only notify if the program is listening.
        recognizer.adjust_for_ambient_noise(source)  # Adjust for background noise
        audio = recognizer.listen(source, phrase_time_limit=10)  # Capture audio, increased time
    try:
        user_input = recognizer.recognize_google(audio)  # Convert speech to text
        print(f"🗣 You said: {user_input}")
        return user_input.lower()  # Convert to lowercase for easier handling
    except sr.UnknownValueError:
        print("Sorry, I didn't understand that.")
        return None
    except sr.RequestError:
        print("Could not request results; check your network connection.")
        return None

# Main function to run the conversation
def main():
    conversation_memory = load_memory()
    conversation_history = conversation_memory.get("conversation", [])
    user_name = input("What's your name? ")

    print("Remi is getting ready...")

    # Generate and speak the initial greeting
    remi_greeting = ask_gemini(conversation_history, user_name, user_name, first_turn=True) #First, set first_turn True
    print(f"💬 Remi says: {remi_greeting}")
    generate_audio(remi_greeting) #Speak
    conversation_history.append(f"Remi: {remi_greeting}") #Append

    print("Remi is ready! Start speaking...")

    # Main loop
    while True:
        user_input = listen_and_transcribe()  # Listen and get the transcribed text
        if user_input:
            if "stop" in user_input:
                print("Goodbye!")
                break
                
            #Process normally if there is user input.
            conversation_history.append(f"User: {user_input}")
            response_text = ask_gemini(conversation_history, user_input, user_name) #Then, set first_turn to False

            #Add Remi to the conversation history
            conversation_history.append(f"Remi: {response_text}")

            #Create conversation data
            conversation_data = {
                "timestamp": datetime.datetime.now().isoformat(),  # Add timestamp
                "user_input": user_input,
                "remi_response": response_text,
                "conversation_summary": summarize_conversation(conversation_history), #Take a conversation summary
            }

            # Save conversation DATA
            with open("conversation_data.json", "a") as f:
                json.dump(conversation_data, f)
                f.write(os.linesep) # Add a new line between entries

            #Speak and save.
            print(f"💬 Remi says: {response_text}")
            generate_audio(response_text)

            #Save and loop
            conversation_memory["conversation"] = conversation_history
            save_to_memory(conversation_memory)

        else:
            print("Please say something...")

async def process_audio_file(audio_file: UploadFile = File(...)):
    try:
        # Create a temporary directory if it doesn't exist
        temp_dir = "temp_audio"
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir)
        
        # Create a temporary file with .wav extension instead of .webm
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.wav', dir=temp_dir)
        
        try:
            # Write the audio data to the temporary file
            print(audio_file)
            contents = await audio_file.read()
            print(contents)
            temp_file.write(contents)
            temp_file.close()
            
            # Now transcribe the saved file
            text = transcribe_audio(temp_file.name)
            
            return text
        finally:
            ...
            # Clean up: remove the temporary file
            # if os.path.exists(temp_file.name):
            #     os.remove(temp_file.name)
    except Exception as e:
        print(f"Error processing audio: {str(e)}")
        return "I couldn't understand what you said. Could you please try again?"

@app.post("/process-audio")
async def process_audio(audio: UploadFile = File(...), user_name: str = Form(...)):
    text = await process_audio_file(audio)
    return {"transcription": text}

@app.post("/process-name")
async def process_name(audio: UploadFile = File(...)):
    text = await process_audio_file(audio)
    # Clean up the transcribed text to get just the name
    name = text.strip().split()[0]  # Take the first word as the name
    return {"name": name}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print(f"Websocket:{websocket}")
    try:
        while True:
            message = await websocket.receive_json()
            
            if message["type"] == "ask_name":
                # Generate name asking prompt
                name_prompt = "Hi! I'm Remi, your memory assistant. Could you please tell me your name?"
                
                # Generate audio for name prompt
                client = ElevenLabs(api_key=ELEVEN_API_KEY)
                audio = client.generate(
                    text=name_prompt,
                    voice="Rachel",
                    model="eleven_multilingual_v2",
                    output_format="mp3_44100_128"
                )
                
                # Convert audio to base64
                audio_bytes = b"".join([chunk for chunk in audio])
                audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
                
                # Send prompt and audio
                await websocket.send_json({
                    "type": "remi_speaking",
                    "text": name_prompt
                })
                await websocket.send_json({
                    "type": "audio",
                    "audio_data": audio_base64
                })

            elif message["type"] == "start_conversation":
                # Generate initial greeting
                user_name = message.get("user_name", "")
                conversation_memory = load_memory()
                conversation_history = conversation_memory.get("conversation", [])
                greeting = ask_gemini(conversation_history, user_name, user_name, first_turn=True)
                
                # Generate audio for greeting
                client = ElevenLabs(api_key=ELEVEN_API_KEY)
                audio = client.generate(
                    text=greeting,
                    voice="Rachel",
                    model="eleven_multilingual_v2",
                    output_format="mp3_44100_128"
                )
                
                # Convert audio to base64
                audio_bytes = b"".join([chunk for chunk in audio])
                audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
                
                # Send greeting and audio
                await websocket.send_json({
                    "type": "remi_speaking",
                    "text": greeting
                })
                await websocket.send_json({
                    "type": "audio",
                    "audio_data": audio_base64
                })
                
            elif message["type"] == "user_input":
                # Process text input
                user_name = message.get("user_name", "")
                text = message.get("text", "")
                
                # Get Remi's response
                conversation_memory = load_memory()
                conversation_history = conversation_memory.get("conversation", [])
                response = ask_gemini(conversation_history, text, user_name)
                
                # Generate audio response
                client = ElevenLabs(api_key=ELEVEN_API_KEY)
                audio = client.generate(
                    text=response,
                    voice="Rachel",
                    model="eleven_multilingual_v2",
                    output_format="mp3_44100_128"
                )
                
                # Convert audio to base64
                audio_bytes = b"".join([chunk for chunk in audio])
                audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
                
                # Update conversation history
                conversation_history.append(f"User: {text}")
                conversation_history.append(f"Remi: {response}")
                conversation_memory["conversation"] = conversation_history
                save_to_memory(conversation_memory)
                
                # Send response and audio
                await websocket.send_json({
                    "type": "remi_speaking",
                    "text": response
                })
                await websocket.send_json({
                    "type": "audio",
                    "audio_data": audio_base64
                })

            elif message["type"] == "end_conversation":
                # Generate goodbye message
                user_name = message.get("user_name", "")
                goodbye_message = f"Goodbye {user_name}! It was wonderful talking with you. Take care, and I'll be here when you want to chat again."
                
                # Generate audio for goodbye
                client = ElevenLabs(api_key=ELEVEN_API_KEY)
                audio = client.generate(
                    text=goodbye_message,
                    voice="Rachel",
                    model="eleven_multilingual_v2",
                    output_format="mp3_44100_128"
                )
                
                # Convert audio to base64
                audio_bytes = b"".join([chunk for chunk in audio])
                audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
                
                # Send goodbye message and audio
                await websocket.send_json({
                    "type": "remi_speaking",
                    "text": goodbye_message
                })
                await websocket.send_json({
                    "type": "audio",
                    "audio_data": audio_base64
                })
                
                # Update conversation history with goodbye
                conversation_memory = load_memory()
                conversation_history = conversation_memory.get("conversation", [])
                conversation_history.append(f"Remi: {goodbye_message}")
                conversation_memory["conversation"] = conversation_history
                save_to_memory(conversation_memory)
                
                # Close the connection
                # await websocket.close()
                break

    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        await websocket.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)