import React from "react";
import mockActivityData from "../../../../../utils/client/mockActivityData";
import "./SystemHealthCard.css";

function SystemHealthCard({ trend, compact = false }) {
  const safeTrend = trend && trend.length > 0
    ? trend
    : mockActivityData.trend;

  if (!safeTrend || safeTrend.length === 0) return null;

  let total = 0;
  let blocked = 0;

  safeTrend.forEach((d) => {
    total += d.total || (d.allowed + d.blocked);
    blocked += d.blocked;
  });

  const success = total - blocked;
  const healthScore = total > 0 ? Math.round((success / total) * 100) : 100;

  let status = "healthy";
  let label = "Healthy";

  if (healthScore < 70) {
    status = "critical";
    label = "Critical";
  } else if (healthScore < 90) {
    status = "degraded";
    label = "Degraded";
  }

  if (compact) {
    return (
      <div className="system-health-compact">
        <div className="health-row">
          <span className="health-score">{healthScore}%</span>
          <span className={`health-status ${status}`}>{label}</span>
        </div>
        <div className="health-bar">
          <div className={`health-fill ${status}`} style={{ width: `${healthScore}%` }} />
        </div>
        <div className="health-meta">
          <span>Allowed: {success}</span>
          <span>Blocked: {blocked}</span>
        </div>
      </div>
    );
  }

  return (
    <div className={`card health-card ${status}`}>
      <h4>🛡️ System Health</h4>
      <div className="health-header">
        <span className="health-icon">{status === 'healthy' ? '🟢' : status === 'degraded' ? '🟡' : '🔴'}</span>
        <span className="health-label">{label}</span>
      </div>
      <div className="health-score">{healthScore}%</div>
      <div className="health-bar">
        <div className={`health-fill ${status}`} style={{ width: `${healthScore}%` }} />
      </div>
      <div className="health-meta">
        <span>Allowed: {success}</span>
        <span>Blocked: {blocked}</span>
      </div>
      <p className="health-sub">Based on traffic success vs blocked ratio</p>
    </div>
  );
}

export default SystemHealthCard;