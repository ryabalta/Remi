import React from 'react';
import './Conversation.css'; // Create this file

function Conversation({ conversation }) {
    return (
        <div className="Conversation">
            {conversation.map((message, index) => (
                <div key={index} className={`message ${message.sender}`}>
                    {message.text}
                </div>
            ))}
        </div>
    );
}

export default Conversation;