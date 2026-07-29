import React, { useState, useEffect, useCallback } from 'react';
import { Search, Shield, AlertTriangle, Clock, Ban, RefreshCw, Copy, ChevronRight, Activity, List } from 'lucide-react';
import { dashboardService } from '../../../services/client/dashboardService';
import { userService } from '../../../services/client/userService';
import toast from 'react-hot-toast';
import './User.css';

const getRiskLevel = (score) => {
  if (score >= 0.7) return { label: 'HIGH RISK', cls: 'high' };
  if (score >= 0.4) return { label: 'MEDIUM RISK', cls: 'medium' };
  return { label: 'LOW RISK', cls: 'low' };
};

const getShieldColor = (cls) => {
  if (cls === 'high') return '#ef4444';
  if (cls === 'medium') return '#f59e0b';
  return '#22c55e';
};

const getActionConfig = (action) => {
  switch (action?.toLowerCase()) {
    case 'allow':   return { color: '#22c55e', icon: '✓', bg: 'rgba(34,197,94,0.15)' };
    case 'block':   return { color: '#ef4444', icon: '✕', bg: 'rgba(239,68,68,0.15)' };
    case 'throttle':return { color: '#f59e0b', icon: '⏱', bg: 'rgba(245,158,11,0.15)' };
    case 'detect':  return { color: '#f59e0b', icon: '⚠', bg: 'rgba(245,158,11,0.15)' };
    default:        return { color: '#94a3b8', icon: '?', bg: 'rgba(148,163,184,0.15)' };
  }
};

const getSmartFallback = (action) => {
  switch (action?.action?.toLowerCase()) {
    case 'allow':    return 'Request allowed';
    case 'block':    return 'User blocked due to repeated violations';
    case 'throttle': return 'Request rate exceeded threshold';
    case 'detect':   return 'Suspicious pattern detected';
    default:         return 'Suspicious activity detected';
  }
};

const formatAction = (action) =>
  action ? action.charAt(0).toUpperCase() + action.slice(1) : 'Unknown';

const isUserBlocked = (user) => user?.isBlocked === true;

const User = () => {
  const [selectedUser, setSelectedUser] = useState(null);
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [lastUpdated, setLastUpdated] = useState(new Date());
  const [blockingInProgress, setBlockingInProgress] = useState(false);
  const [activityFilter, setActivityFilter] = useState('All Actions');

  const fetchUsers = useCallback(async () => {
    try {
      setLoading(true);
      const data = await dashboardService.getSuspiciousUsers(20);
      setUsers(data);
      setLastUpdated(new Date());
    } catch (error) {
      console.error(error);
      toast.error('Failed to load user data');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchUsers(); }, [fetchUsers]);
  useEffect(() => {
    const interval = setInterval(fetchUsers, 15000);
    return () => clearInterval(interval);
  }, [fetchUsers]);

  // Keep the OPEN detail panel in sync too. `users` (the list) already
  // polls every 15s, but `selectedUser` was previously a one-time snapshot
  // taken at click time - it never learned about block/unblock changes
  // that happened outside this UI (policy engine auto-block, manual Redis
  // edits, another admin tab, etc), so the "Status" card could go stale
  // and silently disagree with the actual Redis-backed block state.
  useEffect(() => {
    if (!selectedUser?.id) return;

    const interval = setInterval(async () => {
      try {
        const details = await userService.getUserDetails(selectedUser.id);
        setSelectedUser(prev =>
          prev && prev.id === selectedUser.id ? { ...prev, ...details } : prev
        );
      } catch (error) {
        console.error('Failed to refresh selected user details:', error);
      }
    }, 15000);

    return () => clearInterval(interval);
  }, [selectedUser?.id]);

  const filteredUsers = users.filter(user =>
    user.id.toLowerCase().includes(searchTerm.toLowerCase()) ||
    user.ip.includes(searchTerm)
  );

  const handleUserSelect = async (user) => {
    try {
      const details = await userService.getUserDetails(user.id);
      
      // Use currentRiskScore (MAX for 15 min) as the source of truth
      setSelectedUser({
        ...user,
        ...details,
        // Ensure threatScore matches currentRiskScore for consistency
        threatScore: details.currentRiskScore || user.threatScore,
        currentRiskScore: details.currentRiskScore || user.threatScore,
        // Preserve the original threat score from list for component if needed
        listThreatScore: user.threatScore
      });
    } catch (error) {
      console.error('Failed to load user details:', error);
      toast.error('Failed to load user details');
    }
  };

  const handleBlockUser = async (user) => {
    if (blockingInProgress) return;
    const toastId = toast.loading(`Blocking ${user.id}...`);
    setBlockingInProgress(true);
    try {
      const result = await userService.blockUser(user.id, 3600);
      if (result.success) {
        toast.success(`${user.id} blocked`, { id: toastId });
        await fetchUsers();
        setSelectedUser(prev => ({ ...prev, isBlocked: true }));
      } else { toast.error(result.error, { id: toastId }); }
    } catch { toast.error('Block failed', { id: toastId }); }
    finally { setBlockingInProgress(false); }
  };

  const handleUnblockUser = async (user) => {
    if (blockingInProgress) return;
    const toastId = toast.loading(`Unblocking ${user.id}...`);
    setBlockingInProgress(true);
    try {
      const result = await userService.unblockUser(user.id);
      if (result.success) {
        toast.success(`${user.id} unblocked`, { id: toastId });
        await fetchUsers();
        setSelectedUser(prev => ({ ...prev, isBlocked: false }));
      } else { toast.error(result.error, { id: toastId }); }
    } catch { toast.error('Unblock failed', { id: toastId }); }
    finally { setBlockingInProgress(false); }
  };

  const handleSendWarning = async (user) => {
    const toastId = toast.loading(`Sending warning...`);
    try {
      const result = await userService.sendWarning(user.id, 'Suspicious API usage detected');
      if (result.success) { toast.success('Warning sent', { id: toastId }); }
      else { toast.error(result.error, { id: toastId }); }
    } catch { toast.error('Warning failed', { id: toastId }); }
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    toast.success('Copied!');
  };

  const filteredActions = selectedUser?.recentActions?.filter(a => {
    if (activityFilter === 'All Actions') return true;
    return a.action?.toLowerCase() === activityFilter.toLowerCase();
  }) || [];

  return (
    <div className="up">

      {/* LEFT PANEL */}
      <div className="up__left">
        <div className="up__search-wrap">
          <Search size={15} className="up__search-icon" />
          <input
            className="up__search"
            placeholder="Search users by ID or IP..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>

        <div className="up__list">
          {loading ? (
            <div className="up__loading">
              <div className="up__spinner" />
              <span>Loading users...</span>
            </div>
          ) : filteredUsers.length === 0 ? (
            <div className="up__empty">No users found</div>
          ) : (
            filteredUsers.map((user) => {
              const score = user.threatScore || 0;
              const risk = getRiskLevel(score);
              const isSelected = selectedUser?.id === user.id;

              return (
                <div
                  key={user.id}
                  className={`uc ${isSelected ? 'uc--active' : ''} ${user.isBlocked ? 'uc--blocked': ''}`}
                  onClick={async () => {
                    try {
                      const details = await userService.getUserDetails(user.id);
                      setSelectedUser({ ...user, ...details });
                    } catch { toast.error('Failed to load user'); }
                  }}
                >
                  <div className="uc__left">
                    <div className={`uc__shield uc__shield--${risk.cls}`}>
                      <Shield size={20} color={getShieldColor(risk.cls)} />
                    </div>
                    <div className="uc__info">
                      <div className="uc__id">
                        {user.id}
                        {user.isBlocked && (
                          <span className="uc__blocked-badge">BLOCKED</span>
                        )}
                      </div>
                      
                      <div className="uc__ip">
                        {user.ip}
                        <button className="uc__copy" onClick={(e) => { e.stopPropagation(); copyToClipboard(user.ip); }}>
                          <Copy size={11} />
                        </button>
                      </div>
                      <div className={`uc__badge uc__badge--${risk.cls}`}>{risk.label}</div>
                    </div>
                  </div>

                  <div className="uc__right">
                    <div className="uc__stat">
                      <AlertTriangle size={13} className={`uc__stat-icon uc__stat-icon--${risk.cls}`} />
                      <span className={`uc__violations uc__violations--${risk.cls}`}>{user.violations} violations</span>
                    </div>
                    <div className="uc__stat">
                      <span className="uc__score-label">Risk Score</span>
                      <span className={`uc__score uc__score--${risk.cls}`}>
                        {(score * 100).toFixed(0)}%
                      </span>
                    </div>
                    <div className="uc__stat uc__stat--time">
                      <Clock size={12} />
                      <span>Last seen: {user.lastSeen ? new Date(user.lastSeen).toLocaleTimeString() : 'N/A'}</span>
                    </div>
                  </div>

                  <ChevronRight size={16} className="uc__arrow" />
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* RIGHT PANEL */}
      {selectedUser ? (() => {
        // Use currentRiskScore (MAX for 15min) as primary source
        //Fallback to threatScore for consistency
        const score = selectedUser.currentRiskScore || selectedUser.threatScore || 0;
        const risk = getRiskLevel(score);
        const hasScoreMismatch = selectedUser.listThreatScore && Math.abs(selectedUser.listThreatScore - score) > 0.01;

        return (
          <div className="ud">
            {/* Header */}
            <div className="ud__header">
              <h2 className="ud__title">User Details</h2>
              <div className={`ud__risk-badge ud__risk-badge--${risk.cls}`}>
                <span className="ud__risk-dot" />
                {risk.label}
              </div>
            </div>

            {/* User identity */}
            <div className="ud__identity">
              <div className={`ud__avatar ud__avatar--${risk.cls}`}>
                <Shield size={28} color={getShieldColor(risk.cls)} />
              </div>
              <div className="ud__identity-info">
                <div className="ud__user-id">{selectedUser.id}</div>
                <div className="ud__user-ip">
                  {selectedUser.ip}
                  <button className="uc__copy" onClick={() => copyToClipboard(selectedUser.ip)}>
                    <Copy size={12} />
                  </button>
                </div>
              </div>
              <div className="ud__first-seen">
                <span className="ud__fs-label">First seen</span>
                <span className="ud__fs-value">
                  {selectedUser.firstSeen
                    ? new Date(selectedUser.firstSeen).toLocaleString()
                    : 'Today, ' + new Date().toLocaleTimeString()}
                </span>
              </div>
            </div>

            {/* Stats grid */}
            <div className="ud__stats">
              <div className="ud__stat-card">
                <div className="ud__stat-label">Total Requests</div>
                <div className="ud__stat-value">{(selectedUser.totalRequests || 0).toLocaleString()}</div>
              </div>
              <div className="ud__stat-card">
                <div className="ud__stat-label">Violations (15min)</div>
                <div className="ud__stat-value">{selectedUser.violations || 0}</div>
                <div className="ud__stat-sub">High risk requests</div>
              </div>
              <div className="ud__stat-card">
                <div className="ud__stat-label">
                  Risk Score (15min Peak)
                  <span className="ud__tooltip-icon" title="Highest risk score detected in the last 15 minutes">ⓘ</span>
                </div>

                <div className={`ud__stat-value ud__stat-value--${risk.cls}`}>{(score * 100).toFixed(0)}%</div>
                {selectedUser.avgRiskScore && (
                  <div className="ud__stat-sub">
                    Avg: {(selectedUser.avgRiskScore * 100).toFixed(0)}%
                  </div>
                )}
                {hasScoreMismatch && (
                  <div className="ud__stat-warning">
                    ⚠️ List: {(selectedUser.listThreatScore * 100).toFixed(0)}%
                  </div>
                )}
                <div className="ud__risk-bar-track">
                  <div className={`ud__risk-bar-fill ud__risk-bar-fill--${risk.cls}`} style={{ width: `${score * 100}%` }} />
                </div>
              </div>
              <div className="ud__stat-card">
                <div className="ud__stat-label">Status</div>
                <div className={`ud__status ud__status--${selectedUser.isBlocked ? 'blocked': (selectedUser.status || 'active').toLowerCase()}`}>
                  {selectedUser.isBlocked ? 'Blocked' : (selectedUser.status || 'Suspicious')}
                </div>
              </div>
            </div>

            {/* Action buttons */}
            <div className="ud__actions">
              <button
                className="ud__btn ud__btn--warn"
                onClick={() => handleSendWarning(selectedUser)}
                disabled={blockingInProgress}
              >
                <AlertTriangle size={15} />
                Send Warning
              </button>

              {selectedUser.isBlocked ? (
                <button
                  className="ud__btn ud__btn--unblock"
                  onClick={() => handleUnblockUser(selectedUser)}
                  disabled={blockingInProgress}
                >
                  <Ban size={15} />
                  Unblock User
                </button>
              ) : (
                <button
                  className="ud__btn ud__btn--block"
                  onClick={() => handleBlockUser(selectedUser)}
                  disabled={blockingInProgress}
                >
                  <Ban size={15} />
                  Block User
                </button>
              )}
            </div>

            {/* Recent Activity */}
            {selectedUser.recentActions?.length > 0 && (
              <div className="ud__activity">
                <div className="ud__activity-header">
                  <h3 className="ud__activity-title">Recent Activity</h3>
                  <div className="ud__activity-filter">
                    <select
                      value={activityFilter}
                      onChange={(e) => setActivityFilter(e.target.value)}
                      className="ud__filter-select"
                    >
                      <option>All Actions</option>
                      <option>Allow</option>
                      <option>Block</option>
                      <option>Throttle</option>
                      <option>Detect</option>
                    </select>
                  </div>
                </div>

                <div className="ud__timeline">
                  {filteredActions.slice(0, 6).map((action, i, actionsArray) => {
                    const cfg = getActionConfig(action.action);
                    const currentRisk = action.risk_score || action.riskScore || 0;
                    //Calculate risk change compared to previous action
                    const previousAction = actionsArray[i + 1]; //next item in arrary (more recent is first)
                    const previousRisk = previousAction?.risk_score || previousAction?.riskScore || 0;

                    const riskChange = currentRisk - previousRisk;
                    const isRiskIncreasing = riskChange > 0.01; // Only show if increase > 5%
                    const isRiskDecreasing = riskChange < -0.01;
                    
                    // Format risk delta with + or - sign
                    const riskDelta = riskChange !== 0
                      ? `${riskChange > 0 ? '+' : ''}${(riskChange * 100).toFixed(0)}%`
                      : null;
                    
                      const deltaColor = riskChange > 0 ? '#ef4444' : (riskChange < 0 ? '#22c55e' : '#94a3b9');

                    return (
                      <div key={i} className="ud__tl-row">
                        {/* Time */}
                        <div className="ud__tl-time">
                          {new Date(action.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </div>

                        {/* Icon */}
                        <div className="ud__tl-icon-wrap">
                          <div className="ud__tl-line" />
                          <div className="ud__tl-icon" style={{ background: cfg.bg, border: `1px solid ${cfg.color}` }}>
                            {action.action?.toLowerCase() === 'allow' ? (
                              <Shield size={14} color={cfg.color} />
                            ) : (
                              <AlertTriangle size={14} color={cfg.color} />
                            )}
                          </div>
                        </div>

                        {/* Content */}
                        <div className="ud__tl-content">
                          <div className="ud__tl-top">
                            <span className="ud__tl-action" style={{ color: cfg.color }}>
                              {formatAction(action.action)}
                            </span>
                            {/* Only show RISK INCREASED when actually increasing */}
                            {isRiskIncreasing && (
                              <span className="ud__tl-risk-tag ud__tl-risk-tag--increase">RISK INCREASED</span>
                            )}
                            
                            {/* Show RISK DECREASED when decreasing */}
                            {isRiskDecreasing && (
                              <span className="ud__tl-risk-tag ud__tl-risk-tag--decrease">RISK DECREASED</span>
                            )}
                            {/* Show delta value */}
                            {riskDelta && (
                              <span className="ud__tl-delta" style={{color: deltaColor}}>
                                {riskDelta}
                              </span>
                            )}
                          </div>

                          <div className="ud__tl-summary">
                            {action.explanation?.summary || getSmartFallback(action)}
                          </div>

                          {(action.explanation?.details || action.endpoint) && (
                            <div className="ud__tl-meta">
                              {action.endpoint && <span>Endpoint: {action.endpoint}</span>}
                              {action.method && <><span className="ud__dot">•</span><span>Method: {action.method}</span></>}
                              {action.statusCode && <><span className="ud__dot">•</span><span>Status: {action.statusCode}</span></>}
                              {action.explanation?.details?.pattern && (
                                <>
                                  <span>Pattern: {action.explanation.details.pattern}</span>
                                  {action.explanation.details.confidence && (
                                    <><span className="ud__dot">•</span><span>Confidence: {action.explanation.details.confidence}</span></>
                                  )}
                                </>
                              )}
                            </div>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>

                <button className="ud__view-log">
                  <List size={14} />
                  View Full Activity Log
                </button>
              </div>
            )}

          </div>
        );
      })() : (
        <div className="ud ud--empty">
          <Shield size={48} opacity={0.2} />
          <p>Select a user to view details</p>
        </div>
      )}
    </div>
  );
};

export default User;