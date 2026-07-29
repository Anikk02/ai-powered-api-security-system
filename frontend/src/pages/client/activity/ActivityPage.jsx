import React, { lazy, Suspense, useEffect, useState } from "react";
import { useActivity } from "../../../hooks/client/useActivity";
import SkeletonCard from "../../../components/shared/Skeleton/SkeletonCard";
import { RefreshCw, Activity } from "lucide-react";
import "./ActivityPage.css";

// ✅ Lazy load components
const DecisionTrendChart = lazy(() => 
  import("../../../components/client/Activity/charts/DecisionTrendChart/DecisionTrendChart")
);
const EndpointDistribution = lazy(() => 
  import("../../../components/client/Activity/charts/EndpointDistribution/EndpointDistribution")
);
const ThreatTimeline = lazy(() => 
  import("../../../components/client/Activity/charts/ThreatTimeline/ThreatTimeline")
);
const SystemHealthCard = lazy(() => 
  import("../../../components/client/Activity/widgets/SystemHealthCard/SystemHealthCard")
);
const PeakAttackCard = lazy(() => 
  import("../../../components/client/Activity/widgets/PeakAttackCard/PeakAttackCard")
);
const TopEndpointCard = lazy(() => 
  import("../../../components/client/Activity/widgets/TopEndpointCard/TopEndpointCard")
);
const AttackPatterns = lazy(() => 
  import("../../../components/client/Activity/patterns/AttackPatterns/AttackPatterns")
);
const SpikeCorrelation = lazy(() => 
  import("../../../components/client/Activity/patterns/SpikeCorrelation/SpikeCorrelation")
);

function ActivityPage() {
  // ✅ All hooks at top level
  const { data, loading, error } = useActivity();
  const [showContent, setShowContent] = useState(false);

  useEffect(() => {
    if (data?.trend?.length > 0 || data?.endpoints?.length > 0) {
      setShowContent(true);
    } else if (!loading) {
      setShowContent(true);
    }
  }, [data, loading]);

  // ✅ Data calculations at top level
  const trend = data?.trend || [];
  const endpoints = data?.endpoints || [];
  const timeline = data?.timeline || [];

  const avgBlocked = trend.length > 0 
    ? trend.reduce((sum, d) => sum + d.blocked, 0) / trend.length 
    : 0;
  const latestBlocked = trend.length > 0 ? trend[trend.length - 1]?.blocked || 0 : 0;
  const isAttack = latestBlocked > avgBlocked * 2;
  const isWarning = latestBlocked > avgBlocked;

  let statusClass = "healthy";
  let statusLabel = "System Stable";
  let statusSub = `${latestBlocked} blocked requests (avg ${Math.round(avgBlocked)})`;

  if (isAttack) {
    statusClass = "attack";
    statusLabel = "Attack Spike Detected";
  } else if (isWarning) {
    statusClass = "warning";
    statusLabel = "Unusual Activity Detected";
  }

  // ✅ Loading state
  if (loading && !showContent) {
    return (
      <div className="activity-container">
        <div className="activity-header">
          <div className="activity-header-left">
            <h1>Activity Intelligence</h1>
            <p>Real-time API behavior monitoring</p>
          </div>
        </div>
        <SkeletonCard height="80px" />
        <div className="widgets-row">
          <SkeletonCard height="100px" />
          <SkeletonCard height="100px" />
          <SkeletonCard height="100px" />
        </div>
        <SkeletonCard height="250px" />
      </div>
    );
  }

  // ✅ Error state
  if (error && !data?.trend?.length) {
    return (
      <div className="activity-container">
        <div className="error-text">
          <Activity size={20} />
          Failed to load activity data
        </div>
      </div>
    );
  }

  // ✅ Main render
  return (
    <div className="activity-container">
      {/* Header */}
      <div className="activity-header">
        <div className="activity-header-left">
          <h1>Activity Intelligence</h1>
          <p>Real-time API behavior monitoring</p>
        </div>
        <div className="activity-header-right">
          <span className="timestamp">
            {new Date().toLocaleTimeString()}
          </span>
          <button 
            className="refresh-btn" 
            onClick={() => window.location.reload()}
          >
            <RefreshCw size={14} />
            Refresh
          </button>
        </div>
      </div>

      {/* Status Banner */}
      <div className="status-banner">
        <div className="status-left">
          <div className={`status-dot ${statusClass}`} />
          <div>
            <div className="status-text">{statusLabel}</div>
            <div className="status-sub">{statusSub}</div>
          </div>
        </div>
        <div className="status-right">
          <div className="status-stat">
            <div className="stat-value">{latestBlocked}</div>
            <div className="stat-label">Blocked</div>
          </div>
          <div className="status-stat">
            <div className="stat-value">{trend.length > 0 ? trend[trend.length - 1]?.allowed || 0 : 0}</div>
            <div className="stat-label">Allowed</div>
          </div>
          <div className="status-stat">
            <div className="stat-value">
              {trend.length > 0 ? Math.round((latestBlocked / (avgBlocked || 1)) * 50) : 0}%
            </div>
            <div className="stat-label">Risk Score</div>
          </div>
        </div>
      </div>

      {/* 3 Widgets Row */}
      <Suspense fallback={
        <div className="widgets-row">
          <SkeletonCard height="100px" />
          <SkeletonCard height="100px" />
          <SkeletonCard height="100px" />
        </div>
      }>
        <div className="widgets-row">
          <div className="widget-card">
            <div className="widget-title">System Health</div>
            <SystemHealthCard trend={trend} compact />
          </div>
          <div className="widget-card">
            <div className="widget-title">Peak Attack</div>
            <PeakAttackCard trend={trend} compact />
          </div>
          <div className="widget-card">
            <div className="widget-title">Top Endpoint</div>
            <TopEndpointCard endpoints={endpoints} compact />
          </div>
        </div>
      </Suspense>

      {/* Trend Chart */}
      <Suspense fallback={<SkeletonCard height="250px" />}>
        <div className="chart-card">
          <div className="chart-header">
            <span className="chart-title">Decision Trend</span>
            <span className={`chart-badge ${isAttack ? 'attack' : 'stable'}`}>
              {isAttack ? '⚠️ Active' : '✅ Normal'}
            </span>
          </div>
          <DecisionTrendChart initialData={trend} compact />
        </div>
      </Suspense>

      {/* 2 Column Grid */}
      <Suspense fallback={
        <div className="two-col-grid">
          <SkeletonCard height="200px" />
          <SkeletonCard height="200px" />
        </div>
      }>
        <div className="two-col-grid">
          <div className="chart-card">
            <div className="chart-header">
              <span className="chart-title">Threat Timeline</span>
            </div>
            <ThreatTimeline events={timeline} compact />
          </div>
          <div className="chart-card">
            <div className="chart-header">
              <span className="chart-title">Endpoint Distribution</span>
            </div>
            <EndpointDistribution data={endpoints} compact />
          </div>
        </div>
      </Suspense>

      {/* Patterns Row */}
      <Suspense fallback={
        <div className="two-col-grid">
          <SkeletonCard height="150px" />
          <SkeletonCard height="150px" />
        </div>
      }>
        <div className="two-col-grid">
          <div className="chart-card">
            <div className="chart-header">
              <span className="chart-title">Request Patterns</span>
            </div>
            <AttackPatterns endpoints={endpoints} compact />
          </div>
          <div className="chart-card">
            <div className="chart-header">
              <span className="chart-title">Spike Correlation</span>
            </div>
            <SpikeCorrelation trend={trend} endpoints={endpoints} compact />
          </div>
        </div>
      </Suspense>
    </div>
  );
}

export default ActivityPage;