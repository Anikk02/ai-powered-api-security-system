import api from './client/api';

const authService = {
  // ============================
  // 🔐 REGISTER
  // ============================
  async register(email, password, companyName) {
    return await api.post('/api/auth/register', {
      email,
      password,
      company_name: companyName || null,
    });
  },

  // ============================
  // 🔐 LOGIN
  // ============================
  async login(email, password) {
    const data = await api.post('/api/auth/login', {
      email,
      password,
    });

    if (data?.access_token) {
      localStorage.setItem('access_token', data.access_token);
      localStorage.setItem('refresh_token', data.refresh_token);
    }

    return data;
  },

  // ============================
  // 👤 GET PROFILE
  // ============================
  async getMe() {
    return await api.get('/api/auth/me');
  },

  // ============================
  // 🚪 LOGOUT
  // ============================
  async logout(refreshToken) {
    try {
      await api.post('/api/auth/logout', {
        refresh_token: refreshToken,
      });
    } finally {
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
    }
  },

  // ============================
  // 🔁 FORGOT PASSWORD
  // ============================
  async forgotPassword(email) {
    return await api.post('/api/auth/forgot-password', {
      email,
    });
  },

  // ============================
  // 🔁 RESET PASSWORD
  // ============================
  async resetPassword(token, newPassword) {
    return await api.post('/api/auth/reset-password', {
      token,
      new_password: newPassword,
    });
  },

  // ============================
  // 📧 CHANGE EMAIL
  // ============================
  async changeEmail(newEmail) {
    return await api.post('/api/auth/change-email', {
      new_email: newEmail,
    });
  },

  // ============================
  // ✅ CONFIRM EMAIL CHANGE
  // ============================
  async confirmEmail(token) {
    return await api.post('/api/auth/confirm-email', {
      token,
    });
  },
};

export default authService;