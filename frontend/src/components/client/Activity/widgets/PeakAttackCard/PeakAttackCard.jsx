import React from "react";
import mockActivityData from "../../../../../utils/client/mockActivityData";
import "./PeakAttackCard.css";

function PeakAttackCard({ trend, compact = false }) {
  const safeTrend = trend && trend.length > 0
    ? trend
    : mockActivityData.trend;

  if (!safeTrend || safeTrend.length === 0) return null;

  const peak = safeTrend.reduce((a, b) =>
    a.blocked > b.blocked ? a : b
  );

  const avg = safeTrend.reduce((sum, d) => sum + d.blocked, 0) / safeTrend.length;
  const isSevere = peak.blocked > avg * 2;

  if (compact) {
    return (
      <div className="peak-attack-compact">
        <div className="peak-row">
          <span className="peak-time">{peak.time || '10:10'}</span>
          <span className="peak-count">{peak.blocked}</span>
        </div>
        <div className="peak-meta">
          <span>Blocked Requests</span>
          {isSevere && <span className="peak-badge">🚨 Severe</span>}
        </div>
      </div>
    );
  }

  return (
    <div className={`card peak-card ${isSevere ? "severe" : ""}`}>
      <h4>📈 Peak Attack</h4>

      <div className="peak-value">
        <span className="peak-time">{peak.time || '10:10'}</span>
        <span className="peak-count">{peak.blocked}</span>
      </div>

      <div className="peak-meta">
        <span>Blocked Requests</span>
        {isSevere && (
          <span className="peak-badge">🚨 Severe</span>
        )}
      </div>

      <p className="peak-sub">
        Highest blocked traffic observed in timeframe
      </p>
    </div>
  );
}

export default PeakAttackCard;