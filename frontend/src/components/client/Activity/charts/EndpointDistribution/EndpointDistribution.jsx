import React from "react";
import { useNavigate } from "react-router-dom";
import "./EndpointDistribution.css";

function EndpointDistribution({ data = [], compact = false }) {
  const navigate = useNavigate();

  if (!data.length) {
    if (compact) {
      return (
        <div className="endpoint-distribution-compact">
          <p className="no-endpoints">No endpoint activity available</p>
        </div>
      );
    }
    return (
      <div className="endpoint-card">
        <h2 className="endpoint-title">🎯 Endpoint Hotspots</h2>
        <p className="endpoint-empty">No endpoint activity available</p>
      </div>
    );
  }

  const maxRequests = Math.max(...data.map(d => d.requests));

  const handleClick = (endpoint) => {
    navigate(`/logs?endpoint=${encodeURIComponent(endpoint)}`);
  };

  if (compact) {
    const displayData = data.slice(0, 4);
    return (
      <div className="endpoint-distribution-compact">
        {displayData.map((item, index) => {
          const isTop = item.requests === maxRequests;
          return (
            <div
              key={index}
              className="endpoint-row"
              onClick={() => handleClick(item.endpoint)}
            >
              <div className="endpoint-header">
                <span className="endpoint-name">{item.endpoint}</span>
                <div className="endpoint-stats">
                  <span className="endpoint-percent">{item.percentage}%</span>
                  <span className="endpoint-count">{item.requests} req</span>
                </div>
              </div>
              <div className="endpoint-bar">
                <div
                  className={`endpoint-fill ${getSeverityClass(item)}`}
                  style={{ width: `${Math.min(item.percentage, 100)}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>
    );
  }

  return (
    <div className="endpoint-card">
      <h2 className="endpoint-title">🎯 Endpoint Hotspots</h2>
      <div className="endpoint-list">
        {data.map((item, index) => {
          const isTop = item.requests === maxRequests;
          return (
            <div
              key={index}
              className="endpoint-row"
              onClick={() => handleClick(item.endpoint)}
            >
              <div className="endpoint-header">
                <div className="endpoint-left">
                  <span className="endpoint-name">{item.endpoint}</span>
                  {isTop && (
                    <span className="badge top-badge">MOST TARGETED</span>
                  )}
                </div>
                <div className="endpoint-right">
                  <span className="endpoint-percent">{item.percentage}%</span>
                  <span className="endpoint-count">{item.requests} req</span>
                </div>
              </div>
              <div className="endpoint-bar">
                <div
                  className={`endpoint-fill ${getSeverityClass(item)}`}
                  style={{ width: `${Math.min(item.percentage, 100)}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default EndpointDistribution;

function getSeverityClass(item) {
  if (item.percentage > 60) return "critical";
  if (item.percentage > 40) return "high";
  if (item.percentage > 20) return "medium";
  return "low";
}