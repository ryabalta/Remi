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
from fastapi import UploadFile, File
from fastapi import WebSocket
from fastapi import WebSocketDisconnect

# Recommended: load your API keys from a .env file for safety
# from dotenv import load_dotenv
# load_dotenv()

# If you're not using .env, define them here directly:

from fastapi import FastAPI

app = FastAPI()

ELEVEN_API_KEY = #API KEY
GEMINI_API_KEY =  #API KEY

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
conversation_memory = load_memory()
conversation_history = conversation_memory.get("conversation", [])

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
def save_audio_to_temp_file(recording, sample_rate=44100):
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        wav.write(f.name, sample_rate, recording)
        return f.name

# Transcribe audio with Whisper
def transcribe_audio(audio_path):
    print("📝 Transcribing...")
    text = whisper.load_model("base").transcribe(audio_path)["text"]
    print(f"📣 You said: {text}")
    return text


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
    conversation_summary = "" #Define this before we call it.
    if first_turn:
        prompt = f"You are Remi, a gentle memory assistant for an Alzheimer's patient. You are beginning a conversation with a person named '{user_name}'. Greet {user_name} with a friendly and unique greeting. Ask how they are doing, but try to ask a different question each time. Do not make it more than one sentence!"
    else:
        conversation_summary = summarize_conversation(conversation_history) # Summarize the conversation

        tone_setting = patient_profile["preferred_tone"]
        formality_setting = patient_profile["level_of_formality"]
        prompt = f"""You are Remi, a gentle, patient, kind, encouraging, and empathetic memory assistant for an Alzheimer's patient.
        You know the patient enjoys {patient_profile['interests']}.  Respond with a {tone_setting} tone.  Speak to the patient with a {formality_setting} level of formality. Your goal is to support the patient, create a positive experience, and build their confidence. Respond clearly and kindly to the following: "{user_input}". Remember to be warm, understanding, and easy to follow. If appropriate, use a bit of gentle humor. Summarize everything that has been discussed so far. """

    # Combine the conversation history with the new prompt
    conversation_context = f"Conversation Summary: {conversation_summary}\n" + "\n".join(conversation_history[-5:])  # limit to the last 5 exchanges
    full_prompt = conversation_context + "\n" + prompt if conversation_history else prompt

    print("🤖 Asking Remi...")
    response = model.generate_content(prompt)
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

# Function to listen to speech 
@app.post("/listen-and-transcribe")
async def listen_and_transcribe_endpoint(audio: UploadFile = File(...)):
    try:
        # Create a temporary directory if it doesn't exist
        temp_dir = "temp_audio"
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir)
        
        # Save the uploaded audio file
        
        temp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False, dir=temp_dir)
        contents = await audio.read()
        temp_file.write(contents)
        temp_file.close()

        # Convert to PCM WAV using ffmpeg
        output_file = temp_file.name.replace('.wav', '_pcm.wav')
        import subprocess
        subprocess.run([
            'ffmpeg',
            '-i', temp_file.name,  # input file
            '-acodec', 'pcm_s16le',  # PCM 16-bit encoding
            '-ar', '16000',          # 16kHz sample rate
            '-ac', '1',              # mono audio
            output_file             # output file
        ], check=True)

        # Now use speech recognition on the saved file
        recognizer = sr.Recognizer()
        print(type(temp_file))
        with sr.AudioFile(output_file) as source:
            print("🎤 Processing audio file...")
            audio_data = recognizer.record(source)  # Load the saved file into audio data
            try:
                user_input = recognizer.recognize_google(audio_data)  # Transcribe using Google
                print(f"🗣 Transcribed text: {user_input}")
                answer = await main(user_input)
                return answer
                # return {"transcription": user_input.lower()}
            except sr.UnknownValueError:
                print("Sorry, I didn't understand that.")
                return {"transcription": None, "error": "Speech not recognized"}
            except sr.RequestError:
                print("Could not request results; check your network connection.")
                return {"transcription": None, "error": "Network error"}

            return answer

    except Exception as e:
        print(f"Error processing audio: {str(e)}")
        return {"transcription": None, "error": str(e)}

# Main function to run the conversation

async def main(user_input):
    
    print("Remi is getting ready...")

    # Generate and speak the initial greeting
    remi_greeting = ask_gemini(conversation_history, "Antoine", first_turn=True) #First, set first_turn True
    print(f"💬 Remi says: {remi_greeting}")
    generate_audio(remi_greeting) #Speak
    conversation_history.append(f"Remi: {remi_greeting}") #Append

    print("Remi is ready! Start speaking...")

    # Main loop
        # user_input = listen_and_transcribe()  # Listen and get the transcribed text
    if user_input:
        if "stop" in user_input:
            print("Goodbye!")
            return {"transcription": "Goodbye!"	}
            
        #Process normally if there is user input.
        conversation_history.append(f"User: {user_input}")
        response_text = ask_gemini(conversation_history, user_input) #Then, set first_turn to False

        #Add Remi to the conversation history
        conversation_history.append(f"Remi: {response_text}")

        #Speak and save.
        print(f"💬 Remi says: {response_text}")
        generate_audio(response_text)

        #Save and loop
        conversation_memory["conversation"] = conversation_history
        save_to_memory(conversation_memory)

    else:
        print("Please say something...")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message["type"] == "ask_name":
                # Generate audio asking for name
                name_prompt = "Hello! I'm Remi, your memory assistant. Could you please tell me your name?"
                audio_data = generate_audio(name_prompt)
                await websocket.send_json({
                    "type": "name_prompt",
                    "audio": audio_data
                })
                
            elif message["type"] == "start_conversation":
                # Generate initial greeting
                greeting = ask_gemini(conversation_history, "", message.get("user_name", ""), first_turn=True)
                audio_data = generate_audio(greeting)
                await websocket.send_json({
                    "type": "greeting",
                    "text": greeting,
                    "audio": audio_data
                })
                
            elif message["type"] == "user_input":
                # Process user input and generate response
                user_input = message.get("text", "")
                response = ask_gemini(conversation_history, user_input, message.get("user_name", ""))
                audio_data = generate_audio(response)
                
                # Update conversation history
                conversation_history.append(f"User: {user_input}")
                conversation_history.append(f"Remi: {response}")
                conversation_memory["conversation"] = conversation_history
                save_to_memory(conversation_memory)
                
                await websocket.send_json({
                    "type": "response",
                    "text": response,
                    "audio": audio_data
                })
                
            elif message["type"] == "end_conversation":
                # Handle conversation end
                farewell = "Goodbye! Have a wonderful day!"
                audio_data = generate_audio(farewell)
                await websocket.send_json({
                    "type": "farewell",
                    "text": farewell,
                    "audio": audio_data
                })
                break
                
    except WebSocketDisconnect:
        print("Client disconnected")
    except Exception as e:
        print(f"Error: {str(e)}")
        await websocket.close()

import uvicorn

if __name__ == "__main__":
    uvicorn.run(app, port=8000)
