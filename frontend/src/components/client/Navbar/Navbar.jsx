// frontend/src/components/client/Navbar/Navbar.jsx

import React, { useState, useEffect, useRef } from 'react';
import { Menu, Bell, User, Shield, Zap, LogOut } from 'lucide-react';
import { useAuth } from '../../../context/AuthContext';
import { dashboardService } from '../../../services/client/dashboardService';
import Notifications from '../Notifications/Notifications';
import './Navbar.css';

const Navbar = ({ onMenuClick, isSidebarOpen }) => {
  const { user, logout } = useAuth();
  const displayName = user?.company_name || user?.email || 'Account';
  
  // Notification state
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(false);
  // Track which alerts have been read (by ID)
  const [readAlertIds, setReadAlertIds] = useState(new Set());

  // Fetch alerts
  const fetchAlerts = async () => {
    try {
      setLoading(true);
      const alertsData = await dashboardService.getRecentAlerts(10);
      
      // Map alerts and preserve read status for existing alerts
      const alertsWithReadStatus = alertsData.map(alert => {
        // Check if this alert was already marked as read
        const isRead = readAlertIds.has(alert.id);
        return {
          ...alert,
          read: isRead,
          timestamp: alert.timestamp || new Date()
        };
      });
      
      setAlerts(alertsWithReadStatus);
    } catch (error) {
      console.error('Failed to fetch alerts:', error);
    } finally {
      setLoading(false);
    }
  };

  // Initial fetch
  useEffect(() => {
    fetchAlerts();
  }, []);

  // Poll for new alerts every 30 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      fetchAlerts();
    }, 30000);

    return () => clearInterval(interval);
  }, [readAlertIds]); // Re-run when readAlertIds changes

  // Handle marking a single notification as read
  const handleMarkAsRead = (alertId) => {
    setReadAlertIds(prev => {
      const newSet = new Set(prev);
      newSet.add(alertId);
      return newSet;
    });
    
    // Update the alerts state to reflect the change
    setAlerts(prevAlerts => 
      prevAlerts.map(alert => 
        alert.id === alertId ? { ...alert, read: true } : alert
      )
    );
  };

  // Handle marking all notifications as read
  const handleMarkAllAsRead = () => {
    // Add all alert IDs to the read set
    setReadAlertIds(prev => {
      const newSet = new Set(prev);
      alerts.forEach(alert => newSet.add(alert.id));
      return newSet;
    });
    
    // Update all alerts to read
    setAlerts(prevAlerts => 
      prevAlerts.map(alert => ({ ...alert, read: true }))
    );
  };

  // Handle view all alerts
  const handleViewAllAlerts = () => {
    console.log('View all alerts clicked');
    // Add navigation to alerts page here
  };

  // Calculate unread count
  const unreadCount = alerts.filter(alert => !alert.read).length;

  return (
    <nav className={`navbar ${isSidebarOpen ? 'navbar--sidebar-open' : 'navbar--sidebar-closed'}`}>
      <div className="navbar__left">
        <button className="navbar__menu-btn" onClick={onMenuClick}>
          <Menu size={24} />
        </button>
        <div className="navbar__logo">
          <Shield size={24} className="navbar__logo-icon" />
          <span className="navbar__logo-text">TriAnSec</span>
          <span className="navbar__badge">Behavior-based Middleware</span>
        </div>
      </div>
      <div className="navbar__right">
        <div className="navbar__status">
          <Zap size={16} />
          <span>Live</span>
        </div>
        
        {/* Use the Notifications component here */}
        <Notifications 
          alerts={alerts}
          unreadCount={unreadCount}
          onMarkAsRead={handleMarkAsRead}
          onMarkAllAsRead={handleMarkAllAsRead}
          onViewAll={handleViewAllAlerts}
        />

        <button className="navbar__user" title={displayName}>
          <User size={20} />
          <span className="navbar__user-name">{displayName}</span>
        </button>
        <button className="navbar__icon-btn" onClick={logout} title="Log out">
          <LogOut size={20} />
        </button>
      </div>
    </nav>
  );
};

export default Navbar;