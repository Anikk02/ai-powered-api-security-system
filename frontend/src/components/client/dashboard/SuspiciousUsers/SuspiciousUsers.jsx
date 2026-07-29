// src/components/client/dashboard/SuspiciousUsers/SuspiciousUsers.jsx

import React, { useState } from 'react';
import './SuspiciousUsers.css';
import { Shield, AlertCircle, Eye, Ban, ChevronDown, ChevronUp } from 'lucide-react';

const SuspiciousUsers = ({ users }) => {
  const [expanded, setExpanded] = useState(false);
  
  if (!users || users.length === 0) {
    return (
      <div className="users-container">
        <div className="users-header">
          <h3 className="users-title">Suspicious Users</h3>
        </div>
        <div className="no-data">No suspicious users detected</div>
      </div>
    );
  }

  const displayUsers = expanded ? users : users.slice(0, 5);

  const getStatusBadge = (status) => {
    const configs = {
      // Actual enforcement states
      'blocked': { color: '#d93025', bg: '#fce8e6', label: 'Blocked' },
      'throttled': { color: '#fbbc04', bg: '#fef7e0', label: 'Throttled' },
      // Risk levels
      'critical': { color: '#d93025', bg: '#fce8e6', label: 'Critical' },
      'high_risk': { color: '#ea4335', bg: '#fce8e6', label: 'High Risk' },
      'elevated': { color: '#fbbc04', bg: '#fef7e0', label: 'Elevated' },
      'low': { color: '#34a853', bg: '#e6f4ea', label: 'Low Risk' }
    };

    const config = configs[status] || configs['low'];
    
    return (
      <span className="status-badge" style={{ 
        background: config.bg, 
        color: config.color 
      }}>
        {config.label}
      </span>
    );
  };

  const getThreatScoreColor = (score) => {
    if (score >= 0.8) return 'critical';
    if (score >= 0.6) return 'high';
    if (score >= 0.4) return 'medium';
    return 'low';
  };

  const getActionLabel = (isBlocked, isThrottled, status) => {
    if (isBlocked) return 'Blocked';
    if (isThrottled) return 'Throttled';
    if (status === 'critical' || status === 'high_risk') return 'Challenge';
    return 'Monitor';
  };

  return (
    <div className="users-container">
      <div className="users-header">
        <h3 className="users-title">Suspicious Users</h3>
        {users.length > 5 && (
          <button 
            className="view-all-btn"
            onClick={() => setExpanded(!expanded)}
          >
            {expanded ? (
              <>
                <ChevronUp size={16} /> Show Less
              </>
            ) : (
              <>
                <ChevronDown size={16} /> View All ({users.length})
              </>
            )}
          </button>
        )}
      </div>
      <div className="table-wrapper">
        <table className="users-table">
          <thead>
            <tr>
              <th>User ID</th>
              <th>Violations</th>
              <th>Threat Score</th>
              <th>Status</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {displayUsers.map((user) => {
              // Determine if the user is actually blocked or throttled
              const isActuallyBlocked = user.isBlocked || user.status === 'blocked';
              const isActuallyThrottled = user.status === 'throttled';
              
              return (
                <tr key={user.id}>
                  <td>
                    <div className="user-info">
                      <span className="user-id">{user.id}</span>
                      <span className="user-ip">{user.ip}</span>
                    </div>
                  </td>
                  <td>{user.violations}</td>
                  <td>
                    <div className="threat-score">
                      <div className="score-bar">
                        <div
                          className={`score-fill ${getThreatScoreColor(user.threatScore)}`}
                          style={{ width: `${Math.min(user.threatScore * 100, 100)}%` }}
                        />
                      </div>
                      <span className="score-value">{user.threatScore.toFixed(2)}</span>
                    </div>
                  </td>
                  <td>{getStatusBadge(user.status)}</td>
                  <td>
                    <span className={`action-badge ${isActuallyBlocked ? 'blocked' : 'monitor'}`}>
                      {isActuallyBlocked ? (
                        <>
                          <Ban size={14} /> Blocked
                        </>
                      ) : isActuallyThrottled ? (
                        <>
                          <AlertCircle size={14} /> Throttled
                        </>
                      ) : (
                        <>
                          <Eye size={14} /> {getActionLabel(isActuallyBlocked, isActuallyThrottled, user.status)}
                        </>
                      )}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default SuspiciousUsers;