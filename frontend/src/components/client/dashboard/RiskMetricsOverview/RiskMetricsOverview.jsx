// src/components/client/dashboard/RiskMetricsOverview/RiskMetricsOverview.jsx
import React from 'react';
import './RiskMetricsOverview.css';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';

const RiskMetricsOverview = ({ metrics }) => {
  if (!metrics) {
    return (
      <div className="metrics-container">
        <h3 className="metrics-title">Risk Metrics Overview</h3>
        <div className="no-data">No metrics data available</div>
      </div>
    );
  }

  const getTrendIcon = (trend) => {
    if (trend > 0) return <TrendingUp className="trend-up" size={14} />;
    if (trend < 0) return <TrendingDown className="trend-down" size={14} />;
    return <Minus className="trend-neutral" size={14} />;
  };

  const getTrendColor = (trend) => {
    if (trend > 0) return 'trend-up';
    if (trend < 0) return 'trend-down';
    return 'trend-neutral';
  };

  const getThreatScoreColor = (score) => {
    if (score >= 0.8) return '#ea4335';
    if (score >= 0.5) return '#fbbc04';
    return '#34a853';
  };

  const metricsData = [
    {
      label: 'Risk Score (avg)',
      value: metrics.avgRiskScore?.toFixed(2) || '0.00',
      trend: metrics.riskTrend || 0,
      color: getThreatScoreColor(metrics.avgRiskScore || 0)
    },
    {
      label: 'Active Users (15m)',
      value: metrics.activeUsers15m || 0,
      trend: metrics.activeUsersTrend || 0,
      color: '#029322'
    },
    {
      label: 'Total Requests (15m)',
      value: metrics.totalRequests?.toLocaleString() || 0,
      trend: metrics.totalRequestsTrend || 0,
      color: '#068b3b'
    },
    {
      label: 'Blocked (15m)',
      value: metrics.blockedCount || 0,
      trend: metrics.blockedTrend || 0,
      color: '#ea4335'
    },
    {
      label: 'Throttled (15m)',
      value: metrics.throttledCount || 0,
      trend: metrics.throttledTrend || 0,
      color: '#fbbc04'
    },
    {
      label: 'Avg Latency (15m)',
      value: metrics.avgLatency || '0 ms',
      trend: metrics.latencyTrend || 0,
      color: (metrics.latencyTrend || 0) > 0 ? '#ea4335' : '#34a853'
    }
  ];

  return (
    <div className="metrics-container">
      <h3 className="metrics-title">Metrics Overview</h3>
      <div className="metrics-grid">
        {metricsData.map((metric, index) => (
          <div key={index} className="metric-card">
            <div className="metric-header">
              <span className="metric-label">{metric.label}</span>
              <span className={`metric-trend ${getTrendColor(metric.trend)}`}>
                {getTrendIcon(metric.trend)}
                {metric.trend > 0 ? '+' : ''}{metric.trend}%
              </span>
            </div>
            <div className="metric-value" style={{ color: metric.color }}>
              {metric.value}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default RiskMetricsOverview;