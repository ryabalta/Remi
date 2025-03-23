import React, { useState, useEffect, useRef } from 'react';
import './App.css';
import logo from './assets/remi-logo.png';

function App() {
  const [showSplash, setShowSplash] = useState(true);
  const [showContent, setShowContent] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [userName, setUserName] = useState('');
  const [isRemiSpeaking, setIsRemiSpeaking] = useState(false);
  const [remiText, setRemiText] = useState('');
  const wsRef = useRef(null);

  const playAudio = (audioData) => {
    setIsRemiSpeaking(true);
    const audio = new Audio(`data:audio/mp3;base64,${audioData}`);
    audio.onended = () => {
      setIsRemiSpeaking(false);
      if (!isRecording) {
        startRecording();
      }
    };
    audio.play().catch(error => {
      console.error('Error playing audio:', error);
      audio.onended();
    });
  };

  useEffect(() => {
    // Initialize WebSocket connection
    wsRef.current = new WebSocket('ws://localhost:8000/ws');

    wsRef.current.onmessage = (event) => {
      const data = JSON.parse(event.data);

      switch (data.type) {
        case 'name_prompt':
          // Handle name prompt
          playAudio(data.audio);
          break;
        case 'greeting':
          // Handle greeting
          setRemiText(data.text);
          playAudio(data.audio);
          break;
        case 'response':
          // Handle response
          setRemiText(data.text);
          playAudio(data.audio);
          break;
        case 'farewell':
          // Handle farewell
          setRemiText(data.text);
          playAudio(data.audio);
          break;
        default:
          console.log('Unknown message type:', data.type);
      }
    };

    wsRef.current.onopen = () => {
      // Start conversation by asking for name
      wsRef.current.send(JSON.stringify({ type: 'ask_name' }));
    };

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);

  useEffect(() => {
    // Start fade out after 2 seconds
    const splashTimer = setTimeout(() => {
      setShowSplash(false);
    }, 2000);

    // Show content after splash fades (3 seconds total)
    const contentTimer = setTimeout(() => {
      setShowContent(true);
    }, 3000);

    return () => {
      clearTimeout(splashTimer);
      clearTimeout(contentTimer);
    };
  }, []);

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream);
      const audioChunks = [];

      mediaRecorder.ondataavailable = (event) => {
        audioChunks.push(event.data);
      };

      mediaRecorder.onstop = async () => {
        const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
        const formData = new FormData();
        formData.append('audio', audioBlob);

        try {
          const response = await fetch('http://localhost:8000/listen-and-transcribe', {
            method: 'POST',
            body: formData
          });
          const data = await response.json();

          if (data.transcription) {
            if (!userName) {
              // If no name is set, this is the name recording
              setUserName(data.transcription);
              wsRef.current.send(JSON.stringify({
                type: 'start_conversation',
                user_name: data.transcription
              }));
            } else {
              // This is a regular conversation message
              wsRef.current.send(JSON.stringify({
                type: 'user_input',
                text: data.transcription,
                user_name: userName
              }));
            }
          }
        } catch (error) {
          console.error('Error sending audio:', error);
        }
      };

      mediaRecorder.start();
      setIsRecording(true);

      // Stop recording after 10 seconds
      setTimeout(() => {
        mediaRecorder.stop();
        setIsRecording(false);
      }, 10000);
    } catch (error) {
      console.error('Error accessing microphone:', error);
    }
  };

  const stopRecording = () => {
    setIsRecording(false);
    if (wsRef.current) {
      wsRef.current.send(JSON.stringify({ type: 'end_conversation' }));
    }
  };

  return (
    <div className="App">
      {showSplash && (
        <div className={`splash-screen ${!showSplash ? 'fade-out' : ''}`}>
          <img
            src={logo}
            alt="REMI - A friend that remembers"
            className="splash-logo"
          />
        </div>
      )}

      <div className={`content ${showContent ? 'fade-in' : ''}`}>
        <button className="daily-check-button">
          DAILY CHECK {'\u{1F9E0}'}
        </button>

        {remiText && <div className="greeting">{remiText}</div>}

        <button
          className={`mic-button ${isRemiSpeaking ? 'remi-speaking' : ''} ${isRecording ? 'recording' : ''}`}
          onClick={isRecording ? stopRecording : startRecording}
        >
          <div className="mic-icon"></div>
        </button>

        <div className="app-name">REMI {'\u{1F9E0}'}</div>
      </div>
    </div>
  );
}

export default App;