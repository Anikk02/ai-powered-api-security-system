import React, { useState, useEffect } from 'react';
import { FiBriefcase, FiMail, FiSave } from 'react-icons/fi';
import './ProfileSection.css';

const ProfileSection = ({ profile, loading, updateProfile }) => {
  const [formData, setFormData] = useState({
    companyName: '',
    email: ''
  });
  const [isEditing, setIsEditing] = useState(false);

  useEffect(() => {
    if (profile) {
      setFormData({
        companyName: profile.company_name || '',
        email: profile.email || ''
      });
    }
  }, [profile]);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    // Send company_name to backend (snake_case)
    const payload = {
      company_name: formData.companyName
    };
    await updateProfile(payload);
    setIsEditing(false);
  };

  return (
    <div className="profile-section">
      <h2 className="profile-title">Profile</h2>
      <p className="profile-subtitle">View and manage your profile information.</p>

      <form onSubmit={handleSubmit} className="profile-form">
        <div className="profile-form-group">
          <label className="profile-label">Company Name</label>
          <div className="profile-input-wrapper">
            <FiBriefcase className="profile-input-icon" />
            <input
              type="text"
              name="companyName"
              value={formData.companyName}
              onChange={handleChange}
              disabled={!isEditing}
              className={`profile-input ${isEditing ? 'enabled' : ''}`}
              placeholder="Enter your company name"
            />
          </div>
        </div>

        <div className="profile-form-group">
          <label className="profile-label">Email Address</label>
          <div className="profile-input-wrapper">
            <FiMail className="profile-input-icon" />
            <input
              type="email"
              name="email"
              value={formData.email}
              disabled={true}
              className="profile-input"
            />
          </div>
        </div>

        <div className="profile-actions">
          {isEditing ? (
            <>
              <button
                type="submit"
                disabled={loading}
                className="profile-btn profile-btn-primary"
              >
                <FiSave className="profile-btn-icon" />
                {loading ? 'Saving...' : 'Save Changes'}
              </button>
              <button
                type="button"
                onClick={() => setIsEditing(false)}
                className="profile-btn profile-btn-secondary"
              >
                Cancel
              </button>
            </>
          ) : (
            <button
              type="button"
              onClick={() => setIsEditing(true)}
              className="profile-btn profile-btn-primary"
            >
              Edit Profile
            </button>
          )}
        </div>
      </form>
    </div>
  );
};

export default ProfileSection;