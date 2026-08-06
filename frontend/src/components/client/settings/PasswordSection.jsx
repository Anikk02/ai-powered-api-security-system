import React, { useState } from 'react';
import { FiLock, FiEye, FiEyeOff, FiSave } from 'react-icons/fi';
import './PasswordSection.css';

const PasswordSection = ({ loading, changePassword }) => {
  const [showPassword, setShowPassword] = useState({
    current: false,
    new: false,
    confirm: false
  });
  const [formData, setFormData] = useState({
    currentPassword: '',
    newPassword: '',
    confirmPassword: ''
  });

  const togglePasswordVisibility = (field) => {
    setShowPassword(prev => ({
      ...prev,
      [field]: !prev[field]
    }));
  };

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (formData.newPassword !== formData.confirmPassword) {
      alert('New passwords do not match');
      return;
    }

    // Send the data with snake_case field names as expected by the backend
    await changePassword({
      current_password: formData.currentPassword,
      new_password: formData.newPassword
    });

    setFormData({
      currentPassword: '',
      newPassword: '',
      confirmPassword: ''
    });
  };

  return (
    <div className="password-section">
      <h2 className="password-title">Password</h2>
      <p className="password-subtitle">
        Update your password to keep your account secure.
      </p>

      <form onSubmit={handleSubmit} className="password-form">
        <div className="password-form-group">
          <label className="password-label">Current Password</label>
          <div className="password-input-wrapper">
            <FiLock className="password-input-icon" />
            <input
              type={showPassword.current ? 'text' : 'password'}
              name="currentPassword"
              value={formData.currentPassword}
              onChange={handleChange}
              required
              className="password-input"
              placeholder="Enter current password"
            />
            <button
              type="button"
              onClick={() => togglePasswordVisibility('current')}
              className="password-toggle-btn"
            >
              {showPassword.current ? <FiEyeOff className="password-toggle-icon" /> : <FiEye className="password-toggle-icon" />}
            </button>
          </div>
        </div>

        <div className="password-form-group">
          <label className="password-label">New Password</label>
          <div className="password-input-wrapper">
            <FiLock className="password-input-icon" />
            <input
              type={showPassword.new ? 'text' : 'password'}
              name="newPassword"
              value={formData.newPassword}
              onChange={handleChange}
              required
              minLength={8}
              className="password-input"
              placeholder="Enter new password"
            />
            <button
              type="button"
              onClick={() => togglePasswordVisibility('new')}
              className="password-toggle-btn"
            >
              {showPassword.new ? <FiEyeOff className="password-toggle-icon" /> : <FiEye className="password-toggle-icon" />}
            </button>
          </div>
        </div>

        <div className="password-form-group">
          <label className="password-label">Confirm New Password</label>
          <div className="password-input-wrapper">
            <FiLock className="password-input-icon" />
            <input
              type={showPassword.confirm ? 'text' : 'password'}
              name="confirmPassword"
              value={formData.confirmPassword}
              onChange={handleChange}
              required
              className="password-input"
              placeholder="Confirm new password"
            />
            <button
              type="button"
              onClick={() => togglePasswordVisibility('confirm')}
              className="password-toggle-btn"
            >
              {showPassword.confirm ? <FiEyeOff className="password-toggle-icon" /> : <FiEye className="password-toggle-icon" />}
            </button>
          </div>
        </div>

        <button
          type="submit"
          disabled={loading}
          className="password-submit-btn"
        >
          <FiSave className="password-btn-icon" />
          {loading ? 'Updating...' : 'Update Password'}
        </button>
      </form>
    </div>
  );
};

export default PasswordSection;