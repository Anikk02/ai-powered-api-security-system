// src/components/client/dashboard/AttackActivityChart/AttackActivityChart.jsx
import React, { useState } from 'react';
import './AttackActivityChart.css';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer
} from 'recharts';

const AttackActivityChart = ({ data, loading, timeframe, onTimeframeChange }) => {
  const timeframes = [
    { label: '15m', value: '15m' },
    { label: '1h', value: '1h' },
    { label: '6h', value: '6h' },
    { label: '24h', value: '24h' }
  ];

  const formatXAxis = (timestamp) => {
    const date = new Date(timestamp);
    return date.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      return (
        <div className="tooltip">
          <p className="tooltip-time">{formatXAxis(label)}</p>
          {payload.map((entry, index) => (
            <p key={index} className="tooltip-item">
              <span className="tooltip-dot" style={{ backgroundColor: entry.color }} />
              {entry.name}: {entry.value.toLocaleString()}
            </p>
          ))}
        </div>
      );
    }
    return null;
  };

  return (
    <div className="chart-container">
      <div className="chart-header">
        <h3 className="chart-title">Traffic Activity (Last {timeframe})</h3>
        <div className="timeframe-selector">
          {timeframes.map((tf) => (
            <button
              key={tf.value}
              className={`timeframe-btn ${timeframe === tf.value ? 'active' : ''}`}
              onClick={() => onTimeframeChange(tf.value)}
            >
              {tf.label}
            </button>
          ))}
        </div>
      </div>
      <div className="legend-container">
        <span className="legend-item">
          <span className="legend-dot blocked" />
          Blocked
        </span>
        <span className="legend-item">
          <span className="legend-dot anomalies" />
          Anomalies
        </span>
        <span className="legend-item">
          <span className="legend-dot requests" />
          Requests
        </span>
      </div>
      <div className="chart-wrapper">
        {loading ? (
          <div className="loading">Loading chart data...</div>
        ) : data.length === 0 ? (
          <div className="no-data">No data available</div>
        ) : (
          <ResponsiveContainer width="100%" height={300}>
            <AreaChart data={data} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="blockedGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#ea4335" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#ea4335" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="anomaliesGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#fbbc04" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#fbbc04" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="requestsGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#34a853" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#34a853" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis
                dataKey="time"
                tickFormatter={formatXAxis}
                stroke="#9aa0a6"
                fontSize={12}
              />
              <YAxis stroke="#9aa0a6" fontSize={12} />
              <Tooltip content={<CustomTooltip />} />
              <Area
                type="monotone"
                dataKey="blocked"
                stroke="#ea4335"
                strokeWidth={2}
                fill="url(#blockedGradient)"
                name="Blocked"
              />
              <Area
                type="monotone"
                dataKey="anomalies"
                stroke="#fbbc04"
                strokeWidth={2}
                fill="url(#anomaliesGradient)"
                name="Anomalies"
              />
              <Area
                type="monotone"
                dataKey="requests"
                stroke="#34a853"
                strokeWidth={2}
                fill="url(#requestsGradient)"
                name="Requests"
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
};

export default AttackActivityChart;