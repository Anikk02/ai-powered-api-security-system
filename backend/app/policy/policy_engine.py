# app/policy/policy_engine.py

from __future__ import annotations

import logging
from .adaptive_thresholds import adaptive_thresholds
from .constants import (
    BLOCK_DURATIONS,
    THROTTLE_DURATION,
    VIOLATIONS_MEDIUM_BLOCK,
    VIOLATIONS_SOFT_BLOCK,
    REPUTATION_HARD_BLOCK,
)
from .context import PenaltyContext
from .decision import PenaltyDecision
from .types import Action

logger = logging.getLogger(__name__)


class PolicyEngine:
    """
    Pure business decision engine.

    Inputs
    ------
    - PenaltyContext
    - trust score (0-1)

    Outputs
    -------
    PenaltyDecision

    This class NEVER talks to Redis or updates external state.
    It is a pure function: same inputs → same decision.
    """

    # ---------------------------------------------------------

    @classmethod
    def evaluate(
        cls,
        context: PenaltyContext,
        trust_score: float,
    ) -> PenaltyDecision:

        # trust_score is 1.0 = fully trustworthy, 0.0 = fully
        # suspicious (see TrustEngine). The adaptive thresholds
        # are percentile-based over the "worst" tail of traffic,
        # so we feed them a suspicion score (inverse of trust)
        # rather than trust_score itself.
        suspicion_score = 1.0 - trust_score

        high_threshold, medium_threshold = (
            adaptive_thresholds.thresholds(
                context.client_id
            )
        )

        logger.info(
            f"[PolicyEngine] identity={context.identity_id}, "
            f"trust={trust_score:.3f}, "
            f"suspicion={suspicion_score:.3f}, "
            f"high_th={high_threshold:.3f}, "
            f"med_th={medium_threshold:.3f}, "
            f"violations={context.violation_count}, "
            f"blocked={context.is_blocked}, "
            f"throttled={context.is_throttled}"
        )

        # -------------------------------------------------
        # Already blocked
        # -------------------------------------------------

        if context.is_blocked:
            return cls._block(
                context,
                trust_score,
                "Identity already blocked",
                "hard",
                learn_baseline=False,  # ❌ Never learn from blocks
            )

        if context.ip_blocked:
            return cls._block(
                context,
                trust_score,
                "IP already blocked",
                "hard",
                learn_baseline=False,  # ❌ Never learn from blocks
            )

        if context.fingerprint_blocked:
            return cls._block(
                context,
                trust_score,
                "Fingerprint already blocked",
                "hard",
                learn_baseline=False,  # ❌ Never learn from blocks
            )

        # -------------------------------------------------
        # Hard security rules (NON-adaptive circuit breakers)
        #
        # These fire independent of the adaptive high/medium
        # thresholds. Adaptive thresholds are learned from the
        # identity's own traffic and can drift upward under
        # sustained abuse (see AdaptiveThresholdEngine) - so
        # accumulated violations/reputation must be checked
        # against fixed limits, not the current percentile-based
        # suspicion gate, or a repeat offender can hide forever
        # in the throttle loop below high_threshold.
        # -------------------------------------------------

        if context.combined_reputation >= REPUTATION_HARD_BLOCK:
            return cls._block(
                context,
                trust_score,
                f"Reputation {context.combined_reputation:.2f} exceeds "
                f"hard block threshold ({REPUTATION_HARD_BLOCK})",
                "hard",
                learn_baseline=False,  # ❌ Never learn from blocks
            )

        if context.violation_count >= VIOLATIONS_MEDIUM_BLOCK:
            return cls._block(
                context,
                trust_score,
                f"{context.violation_count} accumulated violations "
                f"(cap: {VIOLATIONS_MEDIUM_BLOCK})",
                "medium",
                learn_baseline=False,  # ❌ Never learn from blocks
            )

        if context.violation_count >= VIOLATIONS_SOFT_BLOCK:
            return cls._block(
                context,
                trust_score,
                f"{context.violation_count} accumulated violations "
                f"(cap: {VIOLATIONS_SOFT_BLOCK})",
                "soft",
                learn_baseline=False,  # ❌ Never learn from blocks
            )

        # -------------------------------------------------
        # Active throttle
        # -------------------------------------------------

        if context.is_throttled:
            still_suspicious = suspicion_score >= medium_threshold
            return PenaltyDecision(
                action="throttle",
                reason=("Continuing suspicious activity during active throttle"
                if still_suspicious
                else "Throttle already active"
                ),

                risk_score=context.risk_score,
                trust_score=trust_score,
                reputation=context.combined_reputation,

                should_throttle=True,
                throttle_duration=THROTTLE_DURATION,

                increment_violation=still_suspicious,  # ✅ Ignoring an active throttle is itself a violation

                learn_baseline=False,  # ❌ Never learn from repeated offenses during an active
                                        #    throttle - feeds adaptive thresholds with the
                                        #    attacker's own high-risk samples, dragging the
                                        #    percentile-based thresholds upward.

                metadata={
                    "throttle_type": "active",
                    "still_suspicious": still_suspicious,
                },
            )

        # -------------------------------------------------
        # Hard IP rotation
        # -------------------------------------------------

        if (
            context.unique_ip_count >= 5
            and suspicion_score >= medium_threshold
        ):
            return cls._block(
                context,
                trust_score,
                f"{context.unique_ip_count} IPs used within 5 minutes",
                "hard",
                learn_baseline=False,  # ❌ Never learn from blocks
            )

        # -------------------------------------------------
        # Medium IP rotation
        # -------------------------------------------------

        if (
            context.unique_ip_count >= 3
            and suspicion_score >= medium_threshold
        ):
            return PenaltyDecision(
                action="throttle",
                reason="Suspicious IP rotation",

                risk_score=context.risk_score,
                trust_score=trust_score,
                reputation=context.combined_reputation,

                reputation_delta=0.03,
                should_throttle=True,
                throttle_duration=THROTTLE_DURATION,

                learn_baseline=True,  # ✅ Learn from mild throttles

                metadata={
                    "unique_ips": context.unique_ip_count,
                    "throttle_type": "ip_rotation",
                },
            )

        # -------------------------------------------------
        # High suspicion score
        # -------------------------------------------------

        if suspicion_score >= high_threshold:
            severity = (
                "hard"
                if context.violation_count >= 5
                else "medium"
            )

            return cls._block(
                context,
                trust_score,
                "High suspicion score",
                severity,
                learn_baseline=False,  # ❌ Never learn from blocks
            )

        # -------------------------------------------------
        # Medium suspicion score
        # -------------------------------------------------

        if suspicion_score >= medium_threshold:
            return PenaltyDecision(
                action="throttle",
                reason="Elevated suspicion score",

                risk_score=context.risk_score,
                trust_score=trust_score,
                reputation=context.combined_reputation,

                reputation_delta=0.02,

                should_throttle=True,
                throttle_duration=THROTTLE_DURATION,

                increment_violation=True,

                learn_baseline=True,  # ✅ Learn from mild throttles

                metadata={
                    "threshold": medium_threshold,
                    "throttle_type": "elevated_suspicion",
                },
            )

        # -------------------------------------------------
        # Normal traffic - ALLOW
        # -------------------------------------------------

        return PenaltyDecision(
            action="allow",
            reason="Normal traffic",

            risk_score=context.risk_score,
            trust_score=trust_score,
            reputation=context.combined_reputation,

            learn_baseline=True,  # ✅ Learn from allowed traffic

            metadata={
                "threshold": medium_threshold,
            },
        )

    # ---------------------------------------------------------

    @staticmethod
    def _block(
        context: PenaltyContext,
        trust_score: float,
        reason: str,
        severity: str,
        learn_baseline: bool = False,
    ) -> PenaltyDecision:

        duration = BLOCK_DURATIONS[severity]

        return PenaltyDecision(
            action="block",
            reason=reason,

            risk_score=context.risk_score,
            trust_score=trust_score,
            reputation=context.combined_reputation,

            reputation_delta=0.08,

            should_block=True,
            block_severity=severity,
            block_duration=duration,

            increment_violation=True,

            learn_baseline=learn_baseline,

            metadata={
                "severity": severity,
            },
        )