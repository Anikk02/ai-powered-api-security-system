import React, { useState } from 'react';
import { FiAlertTriangle, FiTrash2, FiX } from 'react-icons/fi';
import './DangerZone.css';

const DangerZone = ({ loading, deleteAccount, logout }) => {
  const [showConfirm, setShowConfirm] = useState(false);
  const [password, setPassword] = useState('');

  const handleDelete = async () => {
    await deleteAccount(password);
    logout();
  };

  if (!showConfirm) {
    return (
      <div className="danger-zone">
        <div className="danger-zone-header">
          <FiAlertTriangle className="danger-zone-icon" />
          <h2 className="danger-zone-title">Danger Zone</h2>
        </div>
        <p className="danger-zone-subtitle">
          Irreversible and destructive actions for your account.
        </p>

        <div className="danger-zone-card">
          <div className="danger-zone-card-content">
            <h3 className="danger-zone-card-title">Delete Account</h3>
            <p className="danger-zone-card-description">
              Permanently delete your account and all associated data.
            </p>
          </div>
          <button
            onClick={() => setShowConfirm(true)}
            className="danger-zone-delete-btn"
          >
            <FiTrash2 className="danger-btn-icon" />
            Delete Account
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="danger-zone">
      <div className="danger-zone-confirm-header">
        <div className="danger-zone-confirm-title">
          <FiAlertTriangle className="danger-zone-icon" />
          <h2 className="danger-zone-confirm-title-text">Confirm Account Deletion</h2>
        </div>
        <button
          onClick={() => {
            setShowConfirm(false);
            setPassword('');
          }}
          className="danger-zone-close-btn"
        >
          <FiX className="danger-zone-close-icon" />
        </button>
      </div>

      <p className="danger-zone-warning">
        This action is irreversible. Please enter your password to confirm.
      </p>

      <form onSubmit={handleDelete} className="danger-zone-form">
        <div className="danger-zone-form-group">
          <label className="danger-zone-form-label">Enter Password</label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            className="danger-zone-form-input"
            placeholder="Enter your password"
          />
        </div>

        <div className="danger-zone-actions">
          <button
            type="submit"
            disabled={loading}
            className="danger-zone-confirm-btn"
          >
            <FiTrash2 className="danger-btn-icon" />
            {loading ? 'Deleting...' : 'Confirm Delete'}
          </button>
          <button
            type="button"
            onClick={() => {
              setShowConfirm(false);
              setPassword('');
            }}
            className="danger-zone-cancel-btn"
          >
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
};

export default DangerZone;