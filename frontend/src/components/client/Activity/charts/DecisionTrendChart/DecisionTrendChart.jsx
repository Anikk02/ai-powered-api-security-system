import React from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  Legend,
  ReferenceDot,
} from "recharts";
import { useNavigate } from "react-router-dom";
import "./DecisionTrendChart.css";

function DecisionTrendChart({ initialData = [], compact = false }) {
  const navigate = useNavigate();
  const data = initialData;

  // ================================
  // 🧠 Smart Anomaly Detection
  // ================================
  const avgBlocked =
    data.reduce((sum, d) => sum + d.blocked, 0) /
    (data.length || 1);

  const anomalies = data.filter(
    (d) => d.blocked > avgBlocked * 2
  );

  const isUnderAttack = anomalies.length > 0;

  // ================================
  // 🎯 Click → Correlate with Logs
  // ================================
  const handleSpikeClick = (point) => {
    navigate(
      `/logs?time=${encodeURIComponent(point.time)}&type=attack`
    );
  };

  // Compact mode for dashboard embedding
  if (compact) {
    return (
      <div className="chart-compact">
        {data.length === 0 ? (
          <p className="decision-empty">No activity data available</p>
        ) : (
          <>
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={data}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                <XAxis dataKey="time" stroke="var(--text-tertiary)" fontSize={10} tickLine={false} />
                <YAxis stroke="var(--text-tertiary)" fontSize={10} tickLine={false} width={30} />
                <Tooltip
                  contentStyle={{
                    background: "var(--bg-secondary)",
                    border: "1px solid var(--border-color)",
                    borderRadius: "6px",
                    fontSize: "12px",
                  }}
                />
                <Line type="monotone" dataKey="allowed" stroke="var(--accent-success)" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="blocked" stroke="var(--accent-danger)" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="throttled" stroke="var(--accent-warning)" strokeWidth={2} dot={false} />
                {anomalies.map((a, i) => (
                  <ReferenceDot
                    key={i}
                    x={a.time}
                    y={a.blocked}
                    r={5}
                    fill="#ef4444"
                    stroke="#fff"
                    onClick={() => handleSpikeClick(a)}
                    style={{ cursor: "pointer" }}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
            <div className="chart-legend">
              <span className="legend-item">
                <span className="legend-dot allowed" /> Allowed
              </span>
              <span className="legend-item">
                <span className="legend-dot blocked" /> Blocked
              </span>
              <span className="legend-item">
                <span className="legend-dot throttled" /> Throttled
              </span>
            </div>
          </>
        )}
      </div>
    );
  }

  // Full version
  return (
    <div
      className={`decision-card ${
        isUnderAttack ? "attack-mode" : ""
      }`}
    >
      <h2 className="decision-title">
        📈 Decision Trends{" "}
        {isUnderAttack && (
          <span className="attack-badge">⚠️ ATTACK DETECTED</span>
        )}
      </h2>

      {data.length === 0 ? (
        <p className="decision-empty">
          No activity data available
        </p>
      ) : (
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="#2a2a2a" />
            <XAxis dataKey="time" stroke="#a0a0a0" />
            <YAxis stroke="#a0a0a0" />
            <Tooltip
              contentStyle={{
                background: "#1e1e1e",
                border: "1px solid #2a2a2a",
                color: "#fff",
              }}
            />
            <Legend />
            <Line type="monotone" dataKey="allowed" stroke="#10b981" strokeWidth={2} dot={false} />
            <Line type="monotone" dataKey="throttled" stroke="#f59e0b" strokeWidth={2} dot={false} />
            <Line type="monotone" dataKey="blocked" stroke="#ef4444" strokeWidth={2} dot={false} />
            {anomalies.map((a, i) => (
              <ReferenceDot
                key={i}
                x={a.time}
                y={a.blocked}
                r={6}
                fill="#ef4444"
                stroke="#fff"
                onClick={() => handleSpikeClick(a)}
                style={{ cursor: "pointer" }}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}

export default DecisionTrendChart;