import React from "react";
import mockActivityData from "../../../../../utils/client/mockActivityData";
import "./SpikeCorrelation.css";

function SpikeCorrelation({ trend, endpoints, compact = false }) {
  const safeTrend = trend && trend.length > 0
    ? trend
    : mockActivityData.trend;

  const safeEndpoints = endpoints && endpoints.length > 0
    ? endpoints
    : mockActivityData.endpoints;

  if (!safeTrend.length) return null;

  const peak = safeTrend.reduce((a, b) =>
    a.blocked > b.blocked ? a : b
  );

  const topEndpoint = safeEndpoints.reduce((a, b) =>
    a.requests > b.requests ? a : b
  );

  if (compact) {
    return (
      <div className="spike-correlation-compact">
        <div className="correlation-row">
          <span>Peak Time</span>
          <strong>{peak.time}</strong>
        </div>
        <div className="correlation-row">
          <span>Blocked</span>
          <strong>{peak.blocked}</strong>
        </div>
        <div className="correlation-row">
          <span>Likely Target</span>
          <strong>{topEndpoint.endpoint}</strong>
        </div>
      </div>
    );
  }

  return (
    <div className="card spike-correlation">
      <h3>🔗 Spike Correlation</h3>
      <div className="correlation-row">
        <span>Peak Time</span>
        <strong>{peak.time}</strong>
      </div>
      <div className="correlation-row">
        <span>Blocked</span>
        <strong>{peak.blocked}</strong>
      </div>
      <div className="correlation-row">
        <span>Likely Target</span>
        <strong>{topEndpoint.endpoint}</strong>
      </div>
      <p className="correlation-sub">Correlates traffic spikes with endpoint targeting</p>
    </div>
  );
}

export default SpikeCorrelation;