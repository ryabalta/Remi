# Remi - AI Memory Assistant

Remi is an interactive AI memory assistant designed to help users maintain and improve their cognitive abilities through engaging conversations and memory exercises.

## Features

- Voice-based interaction
- Dynamic difficulty adjustment
- Visual progress tracking
- Personalized feedback
- Progress visualization

## Requirements

- Python 3.8 or higher
- Microphone
- Speakers or headphones
- Internet connection (for speech recognition and AI features)

## Installation

1. Clone this repository or download the source code
2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

1. Run the application:
   ```bash
   python remi_app.py
   ```

2. When the application starts:
   - Remi will greet you and ask for your name
   - Speak your name clearly into your microphone
   - Confirm that you want to start the memory check by saying "yes"
   - Answer the questions that Remi asks
   - Watch your progress on the circular progress indicator and answer slots
   - Complete 5 correct answers to finish the session

## File Structure

- `remi_app.py`: Main application file with GUI implementation
- `game.py`: Core game logic and AI integration
- `Game_Questions.xlsx`: Question database
- `requirements.txt`: Python package dependencies

## Notes

- Make sure your microphone is properly connected and configured
- Speak clearly and in a quiet environment for best speech recognition
- The application requires an internet connection for speech recognition and AI features 