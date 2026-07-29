# app/policy/trust_engine.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.policy.context import PenaltyContext
from app.policy.types import TrustLevel
from app.policy.constants import VIOLATIONS_MEDIUM_BLOCK


@dataclass(slots=True)
class TrustResult:
    """
    Result produced by the TrustEngine.
    """

    trust: float
    level: TrustLevel
    reasons: list[str]


class TrustEngine:
    """
    Computes the trust score of an identity.

    Responsibilities
    ----------------
    • Uses current context only.
    • Does not access Redis.
    • Does not modify state.
    • Does not make policy decisions.

    Four time scales:
    1. risk_score           → this request (instant)
    2. behavioral_patterns  → current request patterns (from FeatureBuilder)
    3. historical_suspicion → EWMA over recent behavior (minutes/hundreds of requests)
    4. combined_reputation  → long-term accumulated behavior (sessions)
    """

    # ==========================================================
    # Weights for each time scale
    # ==========================================================

    RISK_WEIGHT = 0.50          # Current request risk
    BEHAVIORAL_WEIGHT = 0.20    # Behavioral patterns (regularity, burst, etc.)
    HISTORY_WEIGHT = 0.15       # EWMA of recent suspicion
    REPUTATION_WEIGHT = 0.15    # Long-term reputation

    # ==========================================================
    # Penalty caps
    # ==========================================================

    MAX_BEHAVIORAL_PENALTY = 0.60
    MAX_VIOLATION_PENALTY = 0.15
    MAX_REQUEST_PENALTY = 0.20
    MAX_ERROR_PENALTY = 0.20
    MAX_IP_ROTATION_PENALTY = 0.25

    # ==========================================================
    # Thresholds
    # ==========================================================

    HISTORY_SUSPICION_THRESHOLD = 0.50
    BEHAVIORAL_PENALTY_THRESHOLD = 0.30

    # ==========================================================

    def evaluate(
        self,
        ctx: PenaltyContext,
        features: dict | None = None,
    ) -> TrustResult:

        trust = 1.0
        reasons: list[str] = []

        # -------------------------------------------------
        # 1. Risk Score (current request)
        # -------------------------------------------------

        risk_penalty = ctx.risk_score * self.RISK_WEIGHT
        trust -= risk_penalty

        if ctx.risk_score >= 0.85:
            reasons.append("Very high current risk")
        elif ctx.risk_score >= 0.70:
            reasons.append("High current risk")
        elif ctx.risk_score >= 0.50:
            reasons.append("Elevated current risk")

        # -------------------------------------------------
        # 2. Behavioral Patterns (from FeatureBuilder)
        # -------------------------------------------------

        raw_behavioral_penalty = self._compute_behavioral_penalty(features)
        behavioral_penalty = raw_behavioral_penalty * self.BEHAVIORAL_WEIGHT
        trust -= behavioral_penalty

        if raw_behavioral_penalty > self.BEHAVIORAL_PENALTY_THRESHOLD:
            reasons.append("Suspicious behavioral pattern")

        # -------------------------------------------------
        # 3. Historical Suspicion (EWMA)
        # -------------------------------------------------

        history_penalty = ctx.historical_suspicion * self.HISTORY_WEIGHT
        trust -= history_penalty

        if ctx.historical_suspicion >= self.HISTORY_SUSPICION_THRESHOLD:
            reasons.append("Persistent suspicious behavior")

        # -------------------------------------------------
        # 4. Reputation (long-term)
        # -------------------------------------------------

        reputation_penalty = ctx.combined_reputation * self.REPUTATION_WEIGHT
        trust -= reputation_penalty

        if ctx.combined_reputation >= 0.70:
            reasons.append("Poor reputation")
        elif ctx.combined_reputation >= 0.60:
            reasons.append("Reputation under observation")

        # -------------------------------------------------
        # 5. Violations
        # -------------------------------------------------
        # Scale so MAX_VIOLATION_PENALTY is reached right at the hard
        # block cap (VIOLATIONS_MEDIUM_BLOCK), instead of saturating
        # early and going flat for a long stretch before the block
        # actually fires (was hardcoded 0.015, saturating at count=10
        # regardless of where the hard caps sat).
        
        per_violation_penalty = self.MAX_VIOLATION_PENALTY / VIOLATIONS_MEDIUM_BLOCK
        violation_penalty = min(
            ctx.violation_count * per_violation_penalty,
            self.MAX_VIOLATION_PENALTY,
        )
        trust -= violation_penalty

        if ctx.violation_count >= 20:
            reasons.append(f"{ctx.violation_count} recent violations")

        # -------------------------------------------------
        # 6. Request Volume
        # -------------------------------------------------

        if ctx.request_count > 20:
            request_penalty = min(
                (ctx.request_count - 20) / 100,
                self.MAX_REQUEST_PENALTY,
            )
            trust -= request_penalty
            reasons.append(f"High request volume ({ctx.request_count}/min)")

        # -------------------------------------------------
        # 7. Error Count
        # -------------------------------------------------

        if ctx.error_count > 5:
            error_penalty = min(
                ctx.error_count / 150,
                self.MAX_ERROR_PENALTY,
            )
            trust -= error_penalty
            reasons.append(f"{ctx.error_count} recent errors")

        # -------------------------------------------------
        # 8. IP Rotation
        # -------------------------------------------------

        if ctx.unique_ip_count > 1:
            rotation_penalty = min(
                ctx.unique_ip_count * 0.04,
                self.MAX_IP_ROTATION_PENALTY,
            )
            trust -= rotation_penalty
            reasons.append(f"{ctx.unique_ip_count} different IPs observed")

        # -------------------------------------------------
        # 9. Recovery Bonus
        # -------------------------------------------------

        if ctx.recovery_score > 0:
            trust += ctx.recovery_score
            reasons.append("Recovered from previous suspicious activity")

        # -------------------------------------------------
        # Clamp
        # -------------------------------------------------

        trust = max(0.0, min(trust, 1.0))

        # -------------------------------------------------
        # Trust Level
        # -------------------------------------------------

        if trust >= 0.80:
            level = TrustLevel.HIGH
        elif trust >= 0.50:
            level = TrustLevel.MEDIUM
        else:
            level = TrustLevel.LOW

        return TrustResult(
            trust=round(trust, 4),
            level=level,
            reasons=reasons,
        )

    # ==========================================================

    @classmethod
    def compute(
        cls,
        ctx: PenaltyContext,
        features: dict | None = None,
    ) -> float:
        """
        Convenience wrapper used by PenaltyManager.

        Runs evaluate() and returns just the trust score,
        stashing the human-readable reasons on the context's
        metadata dict for explainability/logging.
        """

        result = cls().evaluate(ctx, features)

        ctx.metadata["trust_reasons"] = result.reasons
        ctx.metadata["trust_level"] = result.level.value
        ctx.metadata["trust_score"] = result.trust

        behavioral_penalty = cls._compute_behavioral_penalty(features) * cls.BEHAVIORAL_WEIGHT

        # Also store the components for debugging
        ctx.metadata["trust_components"] = {
            "risk": round(ctx.risk_score * cls.RISK_WEIGHT, 4),
            "behavioral": round(behavioral_penalty, 4,),
            "historical": round(
                ctx.historical_suspicion * cls.HISTORY_WEIGHT,
                4,
            ),
            "reputation": round(
                ctx.combined_reputation * cls.REPUTATION_WEIGHT,
                4,
            ),
        }

        return result.trust

    # ==========================================================
    # Behavioral Penalty Computation
    # ==========================================================

    @classmethod
    def _compute_behavioral_penalty(cls, features: dict | None) -> float:
        """
        Compute penalty from behavioral features.

        Detects:
        - Irregular request timing (bot/script behavior)
        - Burst patterns (request acceleration)
        - IP rotation (account takeover)
        - Endpoint exploration (enumeration)
        - High error rates (probing)
        - Sensitive endpoint access
        - Bot user agents
        """
        if not features:
            return 0.0

        penalty = 0.0

        # 1. Request regularity (low = suspicious)
        regularity = features.get("request_regularity", 1.0)
        if regularity < 0.2:
            penalty += 0.35
        elif regularity < 0.4:
            penalty += 0.20

        # 2. Burst score (high = suspicious)
        burst = features.get("burst_score", 0.0)
        if burst > 0.7:
            penalty += 0.30
        elif burst > 0.5:
            penalty += 0.15

        # 3. IP rotation (multiple IPs = suspicious)
        ip_changes = features.get("ip_changes", 0)
        if ip_changes >= 5:
            penalty += 0.40
        elif ip_changes >= 3:
            penalty += 0.20

        # 4. Endpoint entropy (exploratory behavior)
        entropy = features.get("endpoint_entropy", 0.0)
        if entropy > 0.8:
            penalty += 0.25
        elif entropy > 0.6:
            penalty += 0.10

        # 5. Error rate (high = suspicious)
        error_rate = features.get("error_rate", 0.0)
        if error_rate > 0.4:
            penalty += 0.30
        elif error_rate > 0.2:
            penalty += 0.15

        # 6. Sensitive endpoints (multiple hits = suspicious)
        sensitive = features.get("sensitive_hits", 0)
        if sensitive > 10:
            penalty += 0.35
        elif sensitive > 5:
            penalty += 0.15

        # 7. Bot user agent
        if features.get("is_bot", False):
            penalty += 0.20

        return min(cls.MAX_BEHAVIORAL_PENALTY, penalty)