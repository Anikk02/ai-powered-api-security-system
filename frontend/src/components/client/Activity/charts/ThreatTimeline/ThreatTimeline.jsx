import React, { useEffect, useRef, useState } from "react";
import "./ThreatTimeline.css";

function ThreatTimeline({ events = [], compact = false }) {
  const containerRef = useRef(null);
  const [expandedIndex, setExpandedIndex] = useState(null);

  // 🔄 Latest first
  const sortedEvents = [...events].reverse();

  // ⚡ Auto scroll to top
  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = 0;
    }
  }, [events]);

  // Compact mode for dashboard embedding
  if (compact) {
    const displayEvents = sortedEvents.slice(0, 5);
    const nowLabel = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

    return (
      <div className="threat-timeline-compact">
        {displayEvents.length === 0 ? (
          <div className="timeline-item">
            <div className="timeline-dot low" />
            <div className="timeline-content">
              <span className="timeline-event">No threats detected</span>
              <span className="timeline-time">{nowLabel}</span>
            </div>
          </div>
        ) : (
          displayEvents.map((event, index) => (
            <div key={index} className="timeline-item">
              <div className={`timeline-dot ${event.severity || 'low'}`} />
              <div className="timeline-content">
                <span className="timeline-event">{event.event}</span>
                <span className="timeline-time">{event.time}</span>
              </div>
            </div>
          ))
        )}
      </div>
    );
  }

  // Full version
  const nowLabel = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

  return (
    <div className="timeline-card">
      <h2 className="timeline-title">🚨 Threat Timeline</h2>

      {sortedEvents.length === 0 ? (
        <div className="timeline-container">
          <div className="timeline-item">
            <div className="timeline-left">
              <div className="timeline-dot low" />
            </div>
            <div className="timeline-content">
              <div className="timeline-header">
                <span className="timeline-time">{nowLabel}</span>
                <span className="badge low">STABLE</span>
              </div>
              <p className="timeline-event">No recent threats detected</p>
            </div>
          </div>
        </div>
      ) : (
        <div ref={containerRef} className="timeline-container">
          {sortedEvents.map((event, index) => {
            const isCritical = event.severity === "critical";
            const isExpanded = expandedIndex === index;

            return (
              <div
                key={index}
                className={`timeline-item ${isCritical ? "critical" : ""}`}
                onClick={() =>
                  setExpandedIndex(isExpanded ? null : index)
                }
              >
                {/* Left side */}
                <div className="timeline-left">
                  <div
                    className={`timeline-dot ${event.severity}`}
                  />
                  {index !== sortedEvents.length - 1 && (
                    <div className="timeline-line" />
                  )}
                </div>

                {/* Content */}
                <div className="timeline-content">
                  <div className="timeline-header">
                    <span className="timeline-time">{event.time}</span>
                    <span className={`badge ${event.severity}`}>
                      {event.severity?.toUpperCase()}
                    </span>
                  </div>

                  <p className="timeline-event">{event.event}</p>

                  {isExpanded && (
                    <p className="timeline-desc">
                      {event.description}
                    </p>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default ThreatTimeline;