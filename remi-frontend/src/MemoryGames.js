import React, { useState, useEffect } from 'react';
import * as XLSX from 'xlsx'; // Import the xlsx library to parse the Excel file

const MemoryGame = () => {
    const [questions, setQuestions] = useState([]);
    const [isGameActive, setIsGameActive] = useState(false);
    const [score, setScore] = useState(0);
    const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0);
    const [userAnswer, setUserAnswer] = useState('');
    const [question, setQuestion] = useState('');
    const [answer, setAnswer] = useState('');

    useEffect(() => {
        // Load questions from the Excel file when the component mounts
        loadQuestionsFromFile();
    }, []);

    // Function to read and load questions from the Excel file
    const loadQuestionsFromFile = async () => {
        try {
            const response = await fetch('C:\\Users\\antoi\\Downloads\\Remi\\Remi_Memory_Questions.xlsx'); // Modify this path to serve your file
            const data = await response.arrayBuffer();
            const workbook = XLSX.read(data, { type: 'array' });

            // Assuming the sheet with questions is the first sheet
            const sheet = workbook.Sheets[workbook.SheetNames[0]];
            const json = XLSX.utils.sheet_to_json(sheet);

            // Set questions in state
            const formattedQuestions = json.map(item => ({
                question: item['Question Text'], // Adjust based on your Excel column name
                answer: item['Answer'], // Adjust based on your Excel column name
            }));

            setQuestions(formattedQuestions);
            console.log('Loaded questions:', formattedQuestions);

        } catch (error) {
            console.error('Error loading questions:', error);
        }
    };

    const startGame = () => {
        setIsGameActive(true);
        setScore(0);
        setCurrentQuestionIndex(0); // Reset to the first question
        generateNewQuestion();
    };

    const generateNewQuestion = () => {
        if (questions.length > 0) {
            const currentQuestion = questions[currentQuestionIndex];
            setQuestion(currentQuestion.question);
            setAnswer(currentQuestion.answer);
        }
    };

    const handleAnswerSubmit = () => {
        if (userAnswer.toLowerCase() === answer.toLowerCase()) {
            setScore(score + 1);
        } else {
            alert('Oops! Try again.');
        }

        // Move to next question
        if (currentQuestionIndex < questions.length - 1) {
            setCurrentQuestionIndex(currentQuestionIndex + 1);
            generateNewQuestion();
        } else {
            alert('Game Over! Your final score is ' + score);
            setIsGameActive(false); // End the game
        }
        setUserAnswer('');
    };

    return (
        <div className="memory-game">
            <h2>Memory Game</h2>

            {isGameActive ? (
                <div>
                    <p>{question}</p>
                    <input
                        type="text"
                        value={userAnswer}
                        onChange={(e) => setUserAnswer(e.target.value)}
                        placeholder="Your answer"
                    />
                    <button onClick={handleAnswerSubmit}>Submit Answer</button>
                    <p>Your Score: {score}</p>
                </div>
            ) : (
                <div>
                    <button onClick={startGame}>Start Memory Game</button>
                </div>
            )}
        </div>
    );
};

export default MemoryGame;
