import React, { useState } from 'react';
import { FiMail, FiSend } from 'react-icons/fi';
import './EmailSection.css';

const EmailSection = ({ loading, requestEmailChange }) => {
  const [newEmail, setNewEmail] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      // Send the email in the correct format
      await requestEmailChange({ new_email: newEmail });
      setNewEmail('');
    } catch (error) {
      // Error is handled by the hook
      console.error('Email change request failed:', error);
    }
  };

  return (
    <div className="email-section">
      <h2 className="email-title">Change Email Request</h2>
      <p className="email-subtitle">
        Request a change to your email address. A verification link will be sent to your new email.
      </p>

      <form onSubmit={handleSubmit} className="email-form">
        <div className="email-form-group">
          <label className="email-label">New Email Address</label>
          <div className="email-input-wrapper">
            <FiMail className="email-input-icon" />
            <input
              type="email"
              value={newEmail}
              onChange={(e) => setNewEmail(e.target.value)}
              required
              className="email-input"
              placeholder="Enter new email address"
            />
          </div>
        </div>

        <div className="email-info-box">
          <FiSend className="email-info-icon" />
          <p className="email-info-text">
            You will need to verify the new email address to complete the change.
          </p>
        </div>

        <button
          type="submit"
          disabled={loading}
          className="email-submit-btn"
        >
          <FiSend className="email-btn-icon" />
          {loading ? 'Sending...' : 'Request Change'}
        </button>
      </form>
    </div>
  );
};

export default EmailSection;