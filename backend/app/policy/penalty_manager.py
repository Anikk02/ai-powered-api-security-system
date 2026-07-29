# app/policy/penalty_manager.py

from __future__ import annotations

import hashlib
import logging

from .context import PenaltyContext
from .decision import PenaltyDecision

from .redis_repository import redis_repository
from .trust_engine import TrustEngine
from .policy_engine import PolicyEngine
from .recovery_engine import RecoveryEngine

logger = logging.getLogger(__name__)


class PenaltyManager:
    """
    High-level orchestrator.

    Flow
    ----

        Redis
          │
          ▼
    PenaltyContext
          │
          ▼
    TrustEngine
          │
          ▼
    PolicyEngine
          │
          ▼
    RecoveryEngine
          │
          ▼
    PenaltyDecision
          │
          ▼
    Redis

    This class contains NO business logic.
    """

    # ---------------------------------------------------------

    @staticmethod
    def _fingerprint(identity, signals) -> str:

        fp = getattr(identity, "behavioral_fingerprint", None)

        if fp:
            return fp

        ip = getattr(identity, "ip_address", "")

        ua = getattr(signals, "user_agent", "")

        return hashlib.sha256(
            f"{ip}:{ua}".encode()
        ).hexdigest()

    # ---------------------------------------------------------
    # Core orchestration. Returns the full PenaltyDecision so
    # callers that need the rich object (trust_score, reputation,
    # etc.) don't have to re-run the pipeline.
    # ---------------------------------------------------------

    @classmethod
    async def evaluate_decision(
        cls,
        *,
        identity,
        signals,
        risk_score: float,
        base_action: str = "allow",
        features: dict | None = None,
    ) -> PenaltyDecision:

        fingerprint = cls._fingerprint(
            identity,
            signals,
        )

        # -------------------------------------------------
        # Load Redis state
        # -------------------------------------------------

        context: PenaltyContext = (
            await redis_repository.load_context(
                identity=identity,
                signals=signals,
                fingerprint=fingerprint,
                risk_score=risk_score,
            )
        )

        # -------------------------------------------------
        # Trust Engine (with features)
        # -------------------------------------------------

        trust_score = TrustEngine.compute(
            ctx=context,
            features=features,
        )

        # -------------------------------------------------
        # Policy Engine
        # -------------------------------------------------

        decision: PenaltyDecision = (
            PolicyEngine.evaluate(
                context=context,
                trust_score=trust_score,
            )
        )

        # -------------------------------------------------
        # Recovery Engine
        # -------------------------------------------------

        decision = RecoveryEngine.apply(
            context=context,
            decision=decision,
        )

        # -------------------------------------------------
        # Update historical suspicion (EWMA with behavioral features)
        # -------------------------------------------------

        if decision.learn_baseline:
            await redis_repository.update_historical_suspicion(
                context=context,
                decision=decision,
                features=features,
            )

        # -------------------------------------------------
        # Persist decision
        # -------------------------------------------------

        if decision.needs_redis_update:

            await redis_repository.apply_decision(
                context=context,
                decision=decision,
            )

        # -------------------------------------------------
        # Metadata
        # -------------------------------------------------

        decision.metadata["base_action"] = base_action

        decision.metadata["adaptive_threshold"] = (
            decision.metadata.get("threshold")
        )

        decision.metadata["request_count"] = context.request_count

        decision.metadata["error_count"] = context.error_count

        decision.metadata["violation_count"] = (
            context.violation_count
        )

        decision.metadata["unique_ip_count"] = (
            context.unique_ip_count
        )

        decision.metadata["historical_suspicion"] = (
            context.historical_suspicion
        )

        decision.metadata["learn_baseline"] = decision.learn_baseline

        return decision

    # ---------------------------------------------------------
    # Backwards-compatible flattened-tuple API.
    # ---------------------------------------------------------

    @classmethod
    async def evaluate(
        cls,
        *,
        identity,
        signals,
        risk_score: float,
        base_action: str = "allow",
        features: dict | None = None,
    ) -> tuple[str, str, dict]:

        decision = await cls.evaluate_decision(
            identity=identity,
            signals=signals,
            risk_score=risk_score,
            base_action=base_action,
            features=features,
        )

        metadata = decision.to_metadata()

        metadata["base_action"] = decision.metadata.get("base_action")

        metadata["adaptive_threshold"] = (
            decision.metadata.get("adaptive_threshold")
        )

        metadata["request_count"] = decision.metadata.get("request_count")

        metadata["error_count"] = decision.metadata.get("error_count")

        metadata["violation_count"] = (
            decision.metadata.get("violation_count")
        )

        metadata["unique_ip_count"] = (
            decision.metadata.get("unique_ip_count")
        )

        metadata["historical_suspicion"] = (
            decision.metadata.get("historical_suspicion")
        )

        metadata["learn_baseline"] = decision.metadata.get("learn_baseline")

        return (
            decision.action,
            decision.reason,
            metadata,
        )


# ---------------------------------------------------------
# Module-level convenience function.
#
# analysis_pipeline.py imports `apply_penalty` directly and
# expects a PenaltyDecision back - this is that contract.
# ---------------------------------------------------------

async def apply_penalty(
    *,
    identity,
    signals,
    risk_score: float,
    base_action: str = "allow",
    features: dict | None = None,
) -> PenaltyDecision:

    return await PenaltyManager.evaluate_decision(
        identity=identity,
        signals=signals,
        risk_score=risk_score,
        base_action=base_action,
        features=features,
    )