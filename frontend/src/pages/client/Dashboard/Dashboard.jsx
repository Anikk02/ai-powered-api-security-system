// src/pages/client/Dashboard/Dashboard.jsx

import React, { useState, useEffect, useCallback } from 'react';
import { Shield, RefreshCw, AlertTriangle, Activity } from 'lucide-react';
import StatsCards from '../../../components/client/dashboard/StatsCards/StatsCards';
import AttackActivityChart from '../../../components/client/dashboard/AttackActivityChart/AttackActivityChart';
import RiskBreakdown from '../../../components/client/dashboard/RiskBreakdown/RiskBreakdown';
import MostTriggeredPolicies from '../../../components/client/dashboard/MostTriggeredPolicies/MostTriggeredPolicies';
import SuspiciousUsers from '../../../components/client/dashboard/SuspiciousUsers/SuspiciousUsers';
import RecentDecisions from '../../../components/client/dashboard/RecentDecisions/RecentDecisions';
import RiskMetricsOverview from '../../../components/client/dashboard/RiskMetricsOverview/RiskMetricsOverview';
import HelpSection from '../../../components/client/dashboard/HelpSection/HelpSection';
import { dashboardService } from '../../../services/client/dashboardService';
import toast from 'react-hot-toast';
import './Dashboard.css';

const Dashboard = () => {
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [lastUpdated, setLastUpdated] = useState(new Date());
  const [stats, setStats] = useState(null);
  const [trafficData, setTrafficData] = useState([]);
  const [suspiciousUsers, setSuspiciousUsers] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [logs, setLogs] = useState([]);
  const [riskMetrics, setRiskMetrics] = useState(null);
  const [policies, setPolicies] = useState([]);
  const [timeframe, setTimeframe] = useState('15m');
  const [error, setError] = useState(null);

  // Single function to load all dashboard data
  const loadDashboardData = useCallback(async (silent = false) => {
    if (!silent) {
      setLoading(true);
    } else {
      setRefreshing(true);
    }
    setError(null);

    try {
      const [statsData, trafficData, usersData, alertsData, logsData, policiesData] = await Promise.all([
        dashboardService.getStats(),
        dashboardService.getTrafficData(timeframe),
        dashboardService.getSuspiciousUsers(5),
        dashboardService.getRecentAlerts(8),
        dashboardService.getDecisionLogs(1, 8),
        dashboardService.getTopPolicies(5)
      ]);

      setStats(statsData);
      setTrafficData(trafficData);
      setSuspiciousUsers(usersData);
      
      // Mark alerts as unread by default
      const alertsWithReadStatus = alertsData.map(alert => ({
        ...alert,
        read: false,
        timestamp: alert.timestamp || new Date()
      }));
      setAlerts(alertsWithReadStatus);
      
      setLogs(logsData);
      setPolicies(policiesData);

      // Use backend data directly instead of recalculating from traffic data
      setRiskMetrics({
        avgRiskScore: statsData.avgRiskScore,
        riskTrend: statsData.riskTrend,
        activeUsers15m: statsData.activeUsers15m,
        activeUsersTrend: statsData.activeUsersTrend,
        totalRequests: statsData.totalRequests,
        totalRequestsTrend: statsData.totalRequestsTrend,
        blockedCount: statsData.blockedCount,
        blockedTrend: statsData.blockedTrend,
        throttledCount: statsData.throttledCount,
        throttledTrend: statsData.throttledTrend,
        avgLatency: statsData.avgLatency,
        latencyTrend: statsData.latencyTrend
      });

      setLastUpdated(new Date());
    } catch (error) {
      console.error('Error fetching dashboard data:', error);
      setError('Failed to load dashboard data. Please try again.');
      toast.error('Failed to load dashboard data');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [timeframe]);

  // Handle marking notifications as read
  const handleMarkAsRead = useCallback(() => {
    setAlerts(prevAlerts => 
      prevAlerts.map(alert => ({ ...alert, read: true }))
    );
  }, []);

  // Handle view all alerts
  const handleViewAllAlerts = useCallback(() => {
    // Navigate to alerts page or open full alerts view
    console.log('View all alerts clicked');
    // You can add navigation logic here
  }, []);

  // Initial load
  useEffect(() => {
    loadDashboardData();
  }, [loadDashboardData]);

  // Polling every 30 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      loadDashboardData(true);
    }, 30000);

    return () => clearInterval(interval);
  }, [loadDashboardData]);

  const handleRefresh = () => {
    loadDashboardData(false);
  };

  const handleTimeframeChange = (newTimeframe) => {
    setTimeframe(newTimeframe);
  };

  const chartData = trafficData.map(point => ({
    time: point.time,
    requests: point.requests,
    anomalies: point.anomalies,
    blocked: point.blocked
  }));

  const riskBreakdownData = stats?.trafficComposition && stats.totalRequests ? [
    {
      name: 'Normal',
      value: Math.round(stats.totalRequests * (stats.trafficComposition.normal / 100)),
      color: '#34a853'
    },
    {
      name: 'Suspicious',
      value: Math.round(stats.totalRequests * (stats.trafficComposition.suspicious / 100)),
      color: '#fbbc04'
    },
    {
      name: 'High Risk',
      value: Math.round(stats.totalRequests * (stats.trafficComposition.high_risk / 100)),
      color: '#ea4335'
    }
  ] : [];

  if (loading) {
    return (
      <div className="loading-container">
        <div className="loading-spinner">
          <Shield size={48} className="loading-icon" />
        </div>
        <p className="loading-text">Loading security dashboard...</p>
      </div>
    );
  }

  return (
    <div className="dashboard">
      {/* Dashboard Header */}
      <div className="dashboard-header">
        <div className="header-left">
          <div className="header-icon">
            <Shield size={28} />
          </div>
          <div>
            <h1 className="dashboard-title">TriAnSec Security Dashboard</h1>
            <p className="dashboard-subtitle">Behavior-based Middleware - Real-time API security overview</p>
          </div>
        </div>
        <div className="header-right">
          <div className="header-status">
            <span className="status-indicator">
              <Activity size={16} />
              <span className="status-text">Live</span>
            </span>
            <span className="last-updated">
              Last updated: {lastUpdated.toLocaleTimeString()}
            </span>
          </div>
          <button
            className="refresh-btn"
            onClick={handleRefresh}
            disabled={refreshing}
          >
            <RefreshCw size={18} className={refreshing ? 'spinning' : ''} />
            {refreshing ? 'Refreshing...' : 'Refresh'}
          </button>
        </div>
      </div>

      {error && (
        <div className="error-banner">
          <AlertTriangle size={20} />
          <span>{error}</span>
          <button onClick={handleRefresh} className="error-retry-btn">
            Retry
          </button>
        </div>
      )}

      {/* Stats Cards */}
      {stats && <StatsCards stats={stats} />}

      {/* Main Grid */}
      <div className="dashboard-grid">
        <div className="grid-left">
          <AttackActivityChart
            data={chartData}
            loading={loading}
            timeframe={timeframe}
            onTimeframeChange={handleTimeframeChange}
          />
          <div className="two-column-grid">
            <RiskBreakdown data={riskBreakdownData} />
            <MostTriggeredPolicies policies={policies} />
          </div>
        </div>
        <div className="grid-right">
          <SuspiciousUsers users={suspiciousUsers} />
          <RecentDecisions logs={logs} />
        </div>
      </div>

      {/* Risk Metrics Overview */}
      {riskMetrics && <RiskMetricsOverview metrics={riskMetrics} />}

      {/* Help Section */}
      <HelpSection />
    </div>
  );
};

export default Dashboard;