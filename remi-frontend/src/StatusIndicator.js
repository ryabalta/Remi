import React from 'react';
import './StatusIndicator.css';

function StatusIndicator({ status }) {
    return (
        <div className="StatusIndicator">
            Status: {status}
        </div>
    );
}

export default StatusIndicator;