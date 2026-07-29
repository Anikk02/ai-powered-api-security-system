// src/components/client/Notifications/Notifications.jsx

import React, { useState, useEffect, useRef } from 'react';
import { Bell, X, AlertTriangle, Shield, Clock, CheckCircle, Check } from 'lucide-react';
import './Notifications.css';

const Notifications = ({ 
  alerts, 
  unreadCount, 
  onMarkAsRead, 
  onMarkAllAsRead, 
  onViewAll 
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef(null);

  useEffect(() => {
    // Close dropdown when clicking outside
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const toggleDropdown = () => {
    setIsOpen(!isOpen);
    // Don't auto-mark all as read here anymore
  };

  const getAlertIcon = (severity) => {
    switch (severity?.toLowerCase()) {
      case 'critical':
      case 'high':
        return <AlertTriangle size={14} className="notification-icon critical" />;
      case 'medium':
        return <Shield size={14} className="notification-icon medium" />;
      case 'low':
        return <CheckCircle size={14} className="notification-icon low" />;
      default:
        return <Bell size={14} className="notification-icon info" />;
    }
  };

  const getSeverityClass = (severity) => {
    switch (severity?.toLowerCase()) {
      case 'critical':
      case 'high':
        return 'notification-item--critical';
      case 'medium':
        return 'notification-item--medium';
      case 'low':
        return 'notification-item--low';
      default:
        return 'notification-item--info';
    }
  };

  const formatTime = (timestamp) => {
    if (!timestamp) return 'Just now';
    
    let date;
    if (typeof timestamp === 'string') {
      if (timestamp.includes('Z') || timestamp.includes('+') || timestamp.includes('-')) {
        date = new Date(timestamp);
      } else {
        date = new Date(timestamp + 'Z');
      }
    } else if (timestamp instanceof Date) {
      date = timestamp;
    } else {
      return 'Just now';
    }
    
    if (isNaN(date.getTime())) {
      return 'Just now';
    }
    
    const diff = Date.now() - date.getTime();
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(minutes / 60);
    const days = Math.floor(hours / 24);

    if (minutes < 1) return 'Just now';
    if (minutes < 60) return `${minutes}m ago`;
    if (hours < 24) return `${hours}h ago`;
    return `${days}d ago`;
  };

  const handleNotificationClick = (alertId) => {
    if (onMarkAsRead) {
      onMarkAsRead(alertId);
    }
  };

  const handleMarkAllRead = () => {
    if (onMarkAllAsRead) {
      onMarkAllAsRead();
    }
  };

  return (
    <div className="notifications-container" ref={dropdownRef}>
      <button 
        className={`notifications-btn ${isOpen ? 'active' : ''}`}
        onClick={toggleDropdown}
        aria-label="Notifications"
      >
        <Bell size={20} />
        {unreadCount > 0 && (
          <span className="notifications-badge">{unreadCount}</span>
        )}
      </button>

      {isOpen && (
        <div className="notifications-dropdown">
          <div className="notifications-header">
            <span className="notifications-title">Notifications</span>
            <span className="notifications-count">
              {alerts.length} total
              {unreadCount > 0 && ` · ${unreadCount} unread`}
            </span>
            <div className="notifications-header-actions">
              {unreadCount > 0 && (
                <button 
                  className="notifications-mark-all-read"
                  onClick={handleMarkAllRead}
                  title="Mark all as read"
                >
                  <Check size={14} />
                  Mark all read
                </button>
              )}
              <button 
                className="notifications-close"
                onClick={() => setIsOpen(false)}
              >
                <X size={16} />
              </button>
            </div>
          </div>

          <div className="notifications-list">
            {alerts.length === 0 ? (
              <div className="notifications-empty">
                <Bell size={32} className="notifications-empty-icon" />
                <p>No notifications</p>
                <span>All clear! No alerts to show.</span>
              </div>
            ) : (
              alerts.slice(0, 10).map((alert) => (
                <div 
                  key={alert.id} 
                  className={`notification-item ${getSeverityClass(alert.type)} ${alert.read ? 'read' : 'unread'}`}
                  onClick={() => handleNotificationClick(alert.id)}
                >
                  <div className="notification-icon-wrapper">
                    {getAlertIcon(alert.type)}
                  </div>
                  <div className="notification-content">
                    <div className="notification-header">
                      <span className="notification-severity">
                        {alert.type || 'Info'}
                      </span>
                      <span className="notification-time">
                        <Clock size={12} />
                        {formatTime(alert.timestamp)}
                      </span>
                    </div>
                    <p className="notification-message">
                      {alert.ip && <span className="notification-ip">{alert.ip}</span>}
                      {alert.message || `Score: ${alert.score?.toFixed(2) || 'N/A'}`}
                    </p>
                    {alert.endpoint && (
                      <span className="notification-endpoint">{alert.endpoint}</span>
                    )}
                  </div>
                  {!alert.read && <span className="notification-unread-dot" />}
                </div>
              ))
            )}
          </div>

          {alerts.length > 0 && (
            <div className="notifications-footer">
              <button 
                className="notifications-view-all"
                onClick={() => {
                  setIsOpen(false);
                  onViewAll && onViewAll();
                }}
              >
                View All Alerts
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default Notifications;