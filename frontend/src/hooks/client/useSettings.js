import { useState, useEffect, useCallback, useRef } from 'react';
import * as settingsService from '../../services/client/settingsService';

export const useSettings = () => {
  const [profile, setProfile] = useState(null);
  const [plan, setPlan] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const timeoutRef = useRef(null);

  // Clear messages with optional auto-dismiss
  const clearMessages = useCallback(() => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
    setError(null);
    setSuccess(null);
  }, []);

  // Auto-dismiss messages after 5 seconds
  const autoDismiss = useCallback(() => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }
    timeoutRef.current = setTimeout(() => {
      clearMessages();
    }, 5000);
  }, [clearMessages]);

  // Clear timeout on unmount
  useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, []);

  const loadProfile = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await settingsService.getProfile();
      setProfile(data);
      return data;
    } catch (err) {
      const message = err.response?.data?.detail || err.message || 'Failed to load profile';
      setError(message);
      autoDismiss();
      throw err;
    } finally {
      setLoading(false);
    }
  }, [autoDismiss]);

  const loadPlan = useCallback(async () => {
    try {
      const data = await settingsService.getPlanInfo();
      setPlan(data);
      return data;
    } catch (err) {
      console.error('Failed to load plan:', err);
      setPlan({
        name: 'Growth',
        next_renewal: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString()
      });
      return null;
    }
  }, []);

  const updateProfile = useCallback(async (profileData) => {
    setLoading(true);
    setError(null);
    setSuccess(null);
    // Clear any existing timeout
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }
    try {
      const result = await settingsService.updateProfile(profileData);
      setProfile(prev => ({ ...prev, ...profileData }));
      setSuccess('Profile updated successfully');
      autoDismiss();
      return result;
    } catch (err) {
      const message = err.response?.data?.detail || err.message || 'Failed to update profile';
      setError(message);
      autoDismiss();
      throw err;
    } finally {
      setLoading(false);
    }
  }, [autoDismiss]);

  const changePassword = useCallback(async (passwordData) => {
    setLoading(true);
    setError(null);
    setSuccess(null);
    // Clear any existing timeout
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }
    try {
      const result = await settingsService.changePassword(passwordData);
      setSuccess('Password changed successfully');
      autoDismiss();
      return result;
    } catch (err) {
      let message = 'Failed to change password';
      
      if (err.response?.data) {
        const data = err.response.data;
        if (typeof data === 'string') {
          message = data;
        } else if (data.detail) {
          message = data.detail;
        } else if (data.message) {
          message = data.message;
        } else if (Array.isArray(data)) {
          message = data.map(err => err.msg || JSON.stringify(err)).join(', ');
        } else {
          message = JSON.stringify(data);
        }
      } else if (err.message) {
        message = err.message;
      }
      
      setError(message);
      autoDismiss();
      throw err;
    } finally {
      setLoading(false);
    }
  }, [autoDismiss]);

  const requestEmailChange = useCallback(async (emailData) => {
    setLoading(true);
    setError(null);
    setSuccess(null);
    // Clear any existing timeout
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }
    try {
      const result = await settingsService.requestEmailChange(emailData);
      setSuccess('Verification email sent to your new address');
      autoDismiss();
      return result;
    } catch (err) {
      let message = 'Failed to request email change';
      
      if (err.response?.data) {
        const data = err.response.data;
        if (typeof data === 'string') {
          message = data;
        } else if (data.detail) {
          message = data.detail;
        } else if (data.message) {
          message = data.message;
        } else if (Array.isArray(data)) {
          message = data.map(err => err.msg || JSON.stringify(err)).join(', ');
        } else {
          message = JSON.stringify(data);
        }
      } else if (err.message) {
        message = err.message;
      }
      
      setError(message);
      autoDismiss();
      throw err;
    } finally {
      setLoading(false);
    }
  }, [autoDismiss]);

  const confirmEmailChange = useCallback(async (token) => {
    setLoading(true);
    setError(null);
    setSuccess(null);
    // Clear any existing timeout
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }
    try {
      const result = await settingsService.confirmEmailChange(token);
      setSuccess('Email changed successfully');
      autoDismiss();
      return result;
    } catch (err) {
      let message = 'Failed to confirm email change';
      
      if (err.response?.data) {
        const data = err.response.data;
        if (typeof data === 'string') {
          message = data;
        } else if (data.detail) {
          message = data.detail;
        } else if (data.message) {
          message = data.message;
        } else if (Array.isArray(data)) {
          message = data.map(err => err.msg || JSON.stringify(err)).join(', ');
        } else {
          message = JSON.stringify(data);
        }
      } else if (err.message) {
        message = err.message;
      }
      
      setError(message);
      autoDismiss();
      throw err;
    } finally {
      setLoading(false);
    }
  }, [autoDismiss]);

  const deleteAccount = useCallback(async (password) => {
    setLoading(true);
    setError(null);
    setSuccess(null);
    // Clear any existing timeout
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }
    try {
      const result = await settingsService.deleteAccount(password);
      setSuccess('Account deleted successfully');
      autoDismiss();
      return result;
    } catch (err) {
      const message = err.response?.data?.detail || err.message || 'Failed to delete account';
      setError(message);
      autoDismiss();
      throw err;
    } finally {
      setLoading(false);
    }
  }, [autoDismiss]);

  const logout = useCallback(async () => {
    await settingsService.logout();
  }, []);

  useEffect(() => {
    const init = async () => {
      try {
        await loadProfile();
      } catch (err) {
        console.error('Failed to load profile:', err);
      }
      
      try {
        await loadPlan();
      } catch (err) {
        console.error('Failed to load plan:', err);
      }
    };
    init();
  }, [loadProfile, loadPlan]);

  return {
    profile,
    plan,
    loading,
    error,
    success,
    clearMessages,
    loadProfile,
    loadPlan,
    updateProfile,
    changePassword,
    requestEmailChange,
    confirmEmailChange,
    deleteAccount,
    logout
  };
};