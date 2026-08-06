import api from './api';

// Get user profile
export const getProfile = async () => {
  try {
    const response = await api.get('/api/settings/profile');
    return response;
  } catch (error) {
    console.error('Failed to fetch profile:', error);
    throw error;
  }
};

// Update user profile
export const updateProfile = async (profileData) => {
  try {
    const response = await api.put('/api/settings/profile', profileData);
    return response;
  } catch (error) {
    console.error('Failed to update profile:', error);
    throw error;
  }
};

// Change password
export const changePassword = async (passwordData) => {
  try {
    const response = await api.post('/api/settings/change-password', passwordData);
    return response;
  } catch (error) {
    console.error('Failed to change password:', error);
    throw error;
  }
};

// Request email change
export const requestEmailChange = async (emailData) => {
  try {
    // emailData should be { new_email: "email@example.com" }
    const response = await api.post('/api/settings/request-email-change', emailData);
    return response;
  } catch (error) {
    console.error('Failed to request email change:', error);
    throw error;
  }
};

// Confirm email change
export const confirmEmailChange = async (token) => {
  try {
    const response = await api.post('/api/settings/confirm-email-change', { token });
    return response;
  } catch (error) {
    console.error('Failed to confirm email change:', error);
    throw error;
  }
};

// Delete account
export const deleteAccount = async (password) => {
  try {
    const response = await api.delete('/api/settings/account', { 
      data: { password } 
    });
    return response;
  } catch (error) {
    console.error('Failed to delete account:', error);
    throw error;
  }
};

// Get current plan info
export const getPlanInfo = async () => {
  try {
    const response = await api.get('/api/settings/plan');
    return response;
  } catch (error) {
    console.error('Failed to fetch plan info:', error);
    throw error;
  }
};

// Logout from all devices
export const logoutAllDevices = async () => {
  try {
    const response = await api.post('/api/settings/logout-all');
    return response;
  } catch (error) {
    console.error('Logout all devices error:', error);
    throw error;
  }
};

// Logout (single device)
export const logout = async () => {
  try {
    await api.post('/api/auth/logout');
  } catch (error) {
    console.error('Logout error:', error);
  } finally {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('user');
    window.location.href = '/login';
  }
};