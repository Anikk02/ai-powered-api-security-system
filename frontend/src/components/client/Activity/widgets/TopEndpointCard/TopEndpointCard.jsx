import React from "react";
import mockActivityData from "../../../../../utils/client/mockActivityData";
import "./TopEndpointCard.css";

function TopEndpointCard({ endpoints, onClick, compact = false }) {
  // ============================
  // 🧠 Fallback Logic
  // ============================
  const safeEndpoints =
    endpoints && endpoints.length > 0
      ? endpoints
      : mockActivityData.endpoints;

  if (!safeEndpoints || safeEndpoints.length === 0) return null;

  // ============================
  // 📊 Find Top Endpoint
  // ============================
  const top = safeEndpoints.reduce((a, b) =>
    a.requests > b.requests ? a : b
  );

  const totalRequests = safeEndpoints.reduce(
    (sum, e) => sum + e.requests,
    0
  );

  const percentage = totalRequests > 0
    ? Math.round((top.requests / totalRequests) * 100)
    : 0;

  // Severity logic
  const isCritical = percentage > 50;

  // ============================
  // 🎨 Compact UI
  // ============================
  if (compact) {
    return (
      <div 
        className="top-endpoint-compact"
        onClick={() => onClick && onClick(top.endpoint)}
      >
        <div className="endpoint-name">{top.endpoint}</div>
        <div className="endpoint-stats">
          <span className="endpoint-requests">{top.requests} req</span>
          <span className="endpoint-percentage">{percentage}%</span>
        </div>
        <div className="endpoint-bar">
          <div 
            className={`endpoint-fill ${isCritical ? "critical" : ""}`}
            style={{ width: `${percentage}%` }} 
          />
        </div>
        <div className="endpoint-meta">Most targeted endpoint</div>
      </div>
    );
  }

  // ============================
  // 🎨 Full UI
  // ============================
  return (
    <div
      className={`card top-endpoint-card ${
        isCritical ? "critical" : ""
      }`}
      onClick={() => onClick && onClick(top.endpoint)}
    >
      <h4>🎯 Top Endpoint</h4>

      <div className="endpoint-name">
        {top.endpoint}
      </div>

      <div className="endpoint-stats">
        <span className="endpoint-requests">
          {top.requests} req
        </span>
        <span className="endpoint-percentage">
          {percentage}%
        </span>
      </div>

      <div className="endpoint-bar">
        <div
          className={`endpoint-fill ${
            isCritical ? "critical" : ""
          }`}
          style={{ width: `${percentage}%` }}
        />
      </div>

      <div className="endpoint-meta">
        <span>Most targeted endpoint</span>
        {isCritical && (
          <span className="endpoint-badge">
            🚨 High Target
          </span>
        )}
      </div>
    </div>
  );
}

export default TopEndpointCard;