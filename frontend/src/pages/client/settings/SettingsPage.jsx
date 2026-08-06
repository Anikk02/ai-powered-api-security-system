import React, { useState, useEffect } from 'react';
import { useSettings } from '../../../hooks/client/useSettings';
import ProfileSection from '../../../components/client/settings/ProfileSection';
import PasswordSection from '../../../components/client/settings/PasswordSection';
import EmailSection from '../../../components/client/settings/EmailSection';
import DangerZone from '../../../components/client/settings/DangerZone';
import { FiCheckCircle, FiAlertCircle, FiLayers, FiCalendar } from 'react-icons/fi';
import './settingsPage.css';

const SettingsPage = () => {
  const [activeSection, setActiveSection] = useState('profile');
  const {
    profile,
    plan,
    loading,
    error,
    success,
    clearMessages,
    updateProfile,
    changePassword,
    requestEmailChange,
    deleteAccount,
    logout
  } = useSettings();

  // Clear messages when switching tabs
  const handleTabChange = (section) => {
    setActiveSection(section);
    clearMessages();
  };

  const renderSection = () => {
    switch (activeSection) {
      case 'profile':
        return (
          <ProfileSection 
            profile={profile} 
            loading={loading} 
            updateProfile={updateProfile} 
          />
        );
      case 'password':
        return (
          <PasswordSection 
            loading={loading} 
            changePassword={changePassword} 
          />
        );
      case 'email':
        return (
          <EmailSection 
            loading={loading} 
            requestEmailChange={requestEmailChange} 
          />
        );
      case 'danger':
        return (
          <DangerZone 
            loading={loading} 
            deleteAccount={deleteAccount} 
            logout={logout} 
          />
        );
      default:
        return null;
    }
  };

  return (
    <div className="settings-page">
      <div className="settings-content">
        <div className="settings-container">
          {/* Messages */}
          {error && (
            <div className="settings-message settings-message-error">
              <FiAlertCircle className="settings-message-icon settings-message-icon-error" />
              <div className="settings-message-text">
                <p className="settings-message-text-error">
                  {typeof error === 'string' ? error : JSON.stringify(error)}
                </p>
                <button
                  onClick={clearMessages}
                  className="settings-message-dismiss settings-message-dismiss-error"
                >
                  Dismiss
                </button>
              </div>
            </div>
          )}

          {success && (
            <div className="settings-message settings-message-success">
              <FiCheckCircle className="settings-message-icon settings-message-icon-success" />
              <div className="settings-message-text">
                <p className="settings-message-text-success">{success}</p>
                <button
                  onClick={clearMessages}
                  className="settings-message-dismiss settings-message-dismiss-success"
                >
                  Dismiss
                </button>
              </div>
            </div>
          )}

          {/* Plan Info (visible on all sections) */}
          {plan && activeSection !== 'danger' && (
            <div className="settings-plan-container">
              <div className="current-plan">
                <div className="current-plan-content">
                  <div className="current-plan-icon-wrapper">
                    <FiLayers className="current-plan-icon" />
                  </div>
                  <div className="current-plan-info">
                    <p className="current-plan-label">Current Plan</p>
                    <p className="current-plan-name">{plan.name || 'Growth'}</p>
                  </div>
                </div>
                {plan.next_renewal && (
                  <div className="current-plan-renewal">
                    <FiCalendar className="current-plan-renewal-icon" />
                    <span>
                      Next renewal: {new Date(plan.next_renewal).toLocaleDateString('en-US', { 
                        month: 'long', 
                        day: 'numeric', 
                        year: 'numeric' 
                      })}
                    </span>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Navigation Tabs */}
          <div className="settings-tabs">
            <button
              className={`settings-tab ${activeSection === 'profile' ? 'active' : ''}`}
              onClick={() => handleTabChange('profile')}
            >
              Profile
            </button>
            <button
              className={`settings-tab ${activeSection === 'password' ? 'active' : ''}`}
              onClick={() => handleTabChange('password')}
            >
              Password
            </button>
            <button
              className={`settings-tab ${activeSection === 'email' ? 'active' : ''}`}
              onClick={() => handleTabChange('email')}
            >
              Email
            </button>
            <button
              className={`settings-tab ${activeSection === 'danger' ? 'active' : ''}`}
              onClick={() => handleTabChange('danger')}
            >
              Danger Zone
            </button>
          </div>

          {/* Main Content */}
          <div className="settings-card">
            {renderSection()}
          </div>

          {/* Footer */}
          <div className="settings-footer">
            <p>TriAnSec v1.0.0 • Secure your API</p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SettingsPage;