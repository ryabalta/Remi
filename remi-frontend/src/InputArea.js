import React, { useState } from 'react';
import './InputArea.css';

function InputArea({ onSendMessage }) {
    const [message, setMessage] = useState('');

    const handleSubmit = (event) => {
        event.preventDefault();
        if (message.trim()) {
            onSendMessage(message);
            setMessage('');
        }
    };

    return (
        <form className="InputArea" onSubmit={handleSubmit}>
            <input
                type="text"
                placeholder="Type your message..."
                value={message}
                onChange={(e) => setMessage(e.target.value)}
            />
            <button type="submit">Send</button>
        </form>
    );
}

export default InputArea;