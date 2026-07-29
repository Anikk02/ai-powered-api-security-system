# app/policy/redis_repository.py

from __future__ import annotations

import logging
import time

from redis.asyncio import Redis

from app.state.redis_client import redis_client
from app.state.state_manager import StateManager

from .context import PenaltyContext
from .decision import PenaltyDecision
from .utils import combine_reputation

from .constants import (
    WINDOW_SHORT,
    WINDOW_LONG,

    TTL_REPUTATION,
    TTL_REQUEST_HISTORY,
    TTL_IP_TRACKING,
    TTL_RISK_SCORE,
    THROTTLE_DURATION,

    REDIS_REPUTATION_PREFIX,
    REDIS_IP_PREFIX,
    REDIS_FP_PREFIX,

    DEFAULT_HIGH_THRESHOLD,
    DEFAULT_MEDIUM_THRESHOLD,
)

logger = logging.getLogger(__name__)


class RedisRepository:
    """
    Repository responsible for ALL Redis interaction.

    Architecture:

        PenaltyManager
             │
             ▼
      RedisRepository
      ├── load_context()
      ├── update_historical_suspicion()
      └── apply_decision()

    Every request performs

        ONE read pipeline
        ONE write pipeline

    regardless of how many engines are used.
    """

    def __init__(self, redis: Redis | None = None):

        self.redis = redis or redis_client

    # ==========================================================
    # PUBLIC API
    # ==========================================================

    async def load_context(
        self,
        identity,
        signals,
        fingerprint: str,
        risk_score: float,
    ) -> PenaltyContext:
        """
        Single Redis read.

        Everything required by TrustEngine,
        PolicyEngine and RecoveryEngine
        is fetched here.

        Returns:
            PenaltyContext
        """

        try:

            data = await self._pipeline_read(identity, fingerprint)

            return self._build_context(
                identity=identity,
                signals=signals,
                fingerprint=fingerprint,
                risk_score=risk_score,
                data=data,
            )

        except Exception:

            logger.exception("Failed loading penalty context")

            raise

    # ==========================================================

    async def update_historical_suspicion(
        self,
        context: PenaltyContext,
        decision: PenaltyDecision,
        features: dict | None = None,
    ) -> None:
        """
        Update historical suspicion using EWMA with behavioral features.

        Only updates for decisions that should learn the baseline:
        - allow ✅
        - throttle ✅
        - block ❌

        EWMA: new = 0.9 * old + 0.1 * current_suspicion
        """
        
        if not decision.learn_baseline:
            return
        
        # Base suspicion from trust score
        base_suspicion = 1.0 - decision.trust_score
        
        # Enhance with behavioral features if available
        behavioral_suspicion = self._compute_behavioral_suspicion(features)
        
        # Combine: 70% from trust, 30% from behavioral
        current_suspicion = 0.7 * base_suspicion + 0.3 * behavioral_suspicion
        
        # EWMA update
        old_historical = context.historical_suspicion
        new_historical = 0.9 * old_historical + 0.1 * current_suspicion
        
        # Store in Redis with 7-day TTL
        base = StateManager._base(
            context.client_id,
            context.identity_id,
        )
        key = f"{base}:historical_suspicion"
        
        await self.redis.setex(
            key,
            86400 * 7,  # 7 days
            str(round(new_historical, 4)),
        )
        
        # Log the update
        logger.debug(
            f"[RedisRepository] Updated historical_suspicion for {context.identity_id}: "
            f"{old_historical:.3f} → {new_historical:.3f} "
            f"(base={base_suspicion:.3f}, behavioral={behavioral_suspicion:.3f}, "
            f"action={decision.action})"
        )

    # ==========================================================

    async def apply_decision(
        self,
        context: PenaltyContext,
        decision: PenaltyDecision,
    ) -> None:
        """
        Persist PolicyEngine output.

        This is the ONLY write entrypoint.
        """

        try:

            await self._pipeline_write(
                context,
                decision,
            )

        except Exception:

            logger.exception(
                "Failed applying penalty decision"
            )

    # ==========================================================
    # PIPELINE READ
    # ==========================================================

    async def _pipeline_read(self, identity, fingerprint: str):

        base = StateManager._base(
            identity.client_id,
            identity.identity_id,
        )

        now = time.time()

        pipe = self.redis.pipeline()

        # ------------------------------------------------------
        # Request history
        # ------------------------------------------------------

        pipe.zcount(
            f"{base}:timestamps",
            now - WINDOW_SHORT,
            now,
        )

        # ------------------------------------------------------
        # Errors
        # ------------------------------------------------------

        pipe.get(f"{base}:errors")

        # ------------------------------------------------------
        # Violations
        # ------------------------------------------------------

        pipe.get(f"{base}:violations")

        # ------------------------------------------------------
        # IP Rotation
        # ------------------------------------------------------

        pipe.scard(f"{base}:ips")

        # ------------------------------------------------------
        # Reputation
        # ------------------------------------------------------

        pipe.get(
            f"{REDIS_REPUTATION_PREFIX}:{REDIS_IP_PREFIX}:{identity.ip_address}"
        )

        pipe.get(
            f"{REDIS_REPUTATION_PREFIX}:identity:{identity.identity_id}"
        )

        pipe.get(
            f"{REDIS_REPUTATION_PREFIX}:{REDIS_FP_PREFIX}:{fingerprint}"
        )

        # ------------------------------------------------------
        # Existing penalties
        # ------------------------------------------------------

        pipe.exists(f"{base}:blocked")

        pipe.exists(
            f"{REDIS_IP_PREFIX}:{identity.ip_address}:blocked"
        )

        pipe.exists(
            f"{REDIS_FP_PREFIX}:{fingerprint}:blocked"
        )

        pipe.exists(f"{base}:throttled")

        # ------------------------------------------------------
        # Previous risk
        # ------------------------------------------------------

        pipe.get(f"{base}:risk_score")

        # ------------------------------------------------------
        # Historical suspicion (EWMA)
        # ------------------------------------------------------

        pipe.get(f"{base}:historical_suspicion")

        return await pipe.execute()

    # ==========================================================
    # CONTEXT BUILDER
    # ==========================================================

    def _build_context(
        self,
        identity,
        signals,
        fingerprint: str,
        risk_score: float,
        data,
    ) -> PenaltyContext:
        """
        Convert Redis pipeline response into PenaltyContext.
        """

        (
            req_count,
            error_count,
            violation_count,
            unique_ip_count,

            ip_rep,
            identity_rep,
            fingerprint_rep,

            identity_blocked,
            ip_blocked,
            fingerprint_blocked,
            throttled,

            previous_risk,

            historical_suspicion,
        ) = data

        def _to_int(value):
            if value is None:
                return 0

            if isinstance(value, bytes):
                value = value.decode()

            try:
                return int(float(value))
            except Exception:
                return 0

        def _to_float(value):
            if value is None:
                return 0.0

            if isinstance(value, bytes):
                value = value.decode()

            try:
                return float(value)
            except Exception:
                return 0.0

        ip_reputation = _to_float(ip_rep)
        identity_reputation = _to_float(identity_rep)
        fingerprint_reputation = _to_float(fingerprint_rep)

        combined_reputation = combine_reputation(
            ip_reputation,
            identity_reputation,
            fingerprint_reputation,
        )

        return PenaltyContext(

            client_id=identity.client_id,
            identity_id=identity.identity_id,

            ip_address=identity.ip_address,

            fingerprint=fingerprint,

            user_agent=getattr(signals, "user_agent", ""),

            risk_score=risk_score,

            request_count=_to_int(req_count),

            error_count=_to_int(error_count),

            violation_count=_to_int(
                violation_count
            ),

            unique_ip_count=_to_int(
                unique_ip_count
            ),

            ip_reputation=ip_reputation,

            identity_reputation=identity_reputation,

            fingerprint_reputation=fingerprint_reputation,

            combined_reputation=combined_reputation,

            historical_suspicion=_to_float(historical_suspicion),

            is_blocked=bool(
                identity_blocked
            ),

            ip_blocked=bool(
                ip_blocked
            ),

            fingerprint_blocked=bool(
                fingerprint_blocked
            ),

            is_throttled=bool(
                throttled
            ),

            allow_threshold=DEFAULT_MEDIUM_THRESHOLD,
            throttle_threshold=DEFAULT_MEDIUM_THRESHOLD,
            block_threshold=DEFAULT_HIGH_THRESHOLD,

            metadata={
                "previous_risk": _to_float(previous_risk),
            },
        )

    # ==========================================================
    # PIPELINE WRITE
    # ==========================================================

    async def _pipeline_write(
        self,
        context: PenaltyContext,
        decision: PenaltyDecision,
    ) -> None:

        pipe = self.redis.pipeline()

        base = StateManager._base(
            context.client_id,
            context.identity_id,
        )

        now = time.time()

        # ------------------------------------------------------
        # Request history
        # ------------------------------------------------------

        pipe.zadd(
            f"{base}:timestamps",
            {str(now): now},
        )

        pipe.zremrangebyscore(
            f"{base}:timestamps",
            0,
            now - WINDOW_LONG,
        )

        pipe.expire(
            f"{base}:timestamps",
            TTL_REQUEST_HISTORY,
        )

        # ------------------------------------------------------
        # Track IP history
        # ------------------------------------------------------

        pipe.sadd(
            f"{base}:ips",
            context.ip_address,
        )

        pipe.expire(
            f"{base}:ips",
            TTL_IP_TRACKING,
        )

        # ------------------------------------------------------
        # Update reputation
        # ------------------------------------------------------

        self._update_reputation(
            pipe,
            context,
            decision,
        )

        # ------------------------------------------------------
        # Update historical suspicion (EWMA)
        # ------------------------------------------------------

        self._update_historical_suspicion_in_pipeline(
            pipe,
            context,
            decision,
            base,
        )

        # ------------------------------------------------------
        # Violations
        # ------------------------------------------------------

        if decision.increment_violation:

            pipe.incr(
                f"{base}:violations"
            )

            pipe.expire(
                f"{base}:violations",
                WINDOW_LONG,
            )

        # ------------------------------------------------------
        # Risk cache
        # ------------------------------------------------------

        self._store_risk(
            pipe,
            base,
            decision,
        )

        # ------------------------------------------------------
        # Block
        # ------------------------------------------------------

        if decision.should_block:

            self._apply_block(
                pipe,
                context,
                decision,
                base,
            )

        # ------------------------------------------------------
        # Throttle
        # ------------------------------------------------------

        elif decision.should_throttle:

            self._apply_throttle(
                pipe,
                decision,
                base,
            )

        else:

            pipe.delete(
                f"{base}:throttled"
            )

        # ------------------------------------------------------
        # Recovery
        # ------------------------------------------------------

        if decision.should_recover:

            self._apply_recovery(
                pipe,
                context,
                decision,
            )

        await pipe.execute()

    # ==========================================================
    # HISTORICAL SUSPICION (EWMA)
    # ==========================================================

    def _update_historical_suspicion_in_pipeline(
        self,
        pipe,
        context: PenaltyContext,
        decision: PenaltyDecision,
        base: str,
    ) -> None:
        """
        Update historical suspicion using EWMA.

        Only update for decisions that should learn the baseline:
        - allow ✅
        - throttle ✅
        - block ❌

        EWMA: new = 0.9 * old + 0.1 * current_suspicion

        This creates a smooth, decaying average of recent behavior.
        """
        
        if not decision.learn_baseline:
            return
        
        # Current suspicion (inverse of trust)
        current_suspicion = 1.0 - decision.trust_score
        
        # Get old historical value from context
        old_historical = context.historical_suspicion
        
        # EWMA: 90% old, 10% current
        new_historical = 0.9 * old_historical + 0.1 * current_suspicion
        
        # Store in Redis with 7-day TTL
        key = f"{base}:historical_suspicion"
        pipe.setex(
            key,
            86400 * 7,  # 7 days
            str(round(new_historical, 4)),
        )
        
        # Log the update
        logger.debug(
            f"[RedisRepository] Updated historical_suspicion for {context.identity_id}: "
            f"{old_historical:.3f} → {new_historical:.3f} "
            f"(current_suspicion={current_suspicion:.3f}, action={decision.action})"
        )

    # ==========================================================

    def _compute_behavioral_suspicion(self, features: dict | None) -> float:
        """
        Compute suspicion from behavioral features.
        """
        if not features:
            return 0.0
        
        suspicion = 0.0
        
        # 1. Request regularity (low = suspicious)
        regularity = features.get("request_regularity", 1.0)
        if regularity < 0.3:
            suspicion += 0.4
        elif regularity < 0.5:
            suspicion += 0.2
        
        # 2. Burst score (high = suspicious)
        burst_score = features.get("burst_score", 0.0)
        if burst_score > 0.6:
            suspicion += 0.3
        elif burst_score > 0.4:
            suspicion += 0.15
        
        # 3. IP changes
        ip_changes = features.get("ip_changes", 0)
        if ip_changes >= 5:
            suspicion += 0.5
        elif ip_changes >= 3:
            suspicion += 0.25
        
        # 4. Error rate (high = suspicious)
        error_rate = features.get("error_rate", 0.0)
        if error_rate > 0.3:
            suspicion += 0.3
        elif error_rate > 0.15:
            suspicion += 0.15
        
        # 5. Endpoint entropy (high = exploratory = suspicious)
        entropy = features.get("endpoint_entropy", 0.0)
        if entropy > 0.7:
            suspicion += 0.3
        elif entropy > 0.5:
            suspicion += 0.15
        
        # 6. Sensitive endpoint hits
        sensitive_hits = features.get("sensitive_hits", 0)
        if sensitive_hits > 10:
            suspicion += 0.4
        elif sensitive_hits > 5:
            suspicion += 0.2
        
        # 7. Bot user agent
        if features.get("is_bot", False):
            suspicion += 0.3
        
        # Cap at 1.0
        return min(1.0, suspicion)

    # ==========================================================
    # REPUTATION
    # ==========================================================

    def _update_reputation(
        self,
        pipe,
        context: PenaltyContext,
        decision: PenaltyDecision,
    ) -> None:
        """
        Update all reputation sources using the final
        reputation delta produced by PolicyEngine +
        RecoveryEngine.
        """

        delta = decision.final_reputation_delta

        if delta == 0:
            return

        keys = [
            f"{REDIS_REPUTATION_PREFIX}:{REDIS_IP_PREFIX}:{context.ip_address}",
            f"{REDIS_REPUTATION_PREFIX}:identity:{context.identity_id}",
        ]

        if context.fingerprint:
            keys.append(
                f"{REDIS_REPUTATION_PREFIX}:{REDIS_FP_PREFIX}:{context.fingerprint}"
            )

        for key in keys:
            pipe.incrbyfloat(key, delta)
            pipe.expire(key, TTL_REPUTATION)

    # ==========================================================
    # RISK CACHE
    # ==========================================================

    def _store_risk(
        self,
        pipe,
        base: str,
        decision: PenaltyDecision,
    ) -> None:
        """
        Cache the latest adjusted risk.
        """

        pipe.setex(
            f"{base}:risk_score",
            TTL_RISK_SCORE,
            round(decision.risk_score, 4),
        )

    # ==========================================================
    # BLOCK
    # ==========================================================

    def _apply_block(
        self,
        pipe,
        context: PenaltyContext,
        decision: PenaltyDecision,
        base: str,
    ) -> None:
        """
        Apply identity/IP/fingerprint block.
        """

        duration = decision.block_duration

        pipe.setex(
            f"{base}:blocked",
            duration,
            "1",
        )

        pipe.setex(
            f"{REDIS_IP_PREFIX}:{context.ip_address}:blocked",
            duration,
            "1",
        )

        if context.fingerprint:
            pipe.setex(
                f"{REDIS_FP_PREFIX}:{context.fingerprint}:blocked",
                duration,
                "1",
            )

        # remove throttle if blocked
        pipe.delete(
            f"{base}:throttled"
        )

    # ==========================================================
    # THROTTLE
    # ==========================================================

    def _apply_throttle(
        self,
        pipe,
        decision: PenaltyDecision,
        base: str,
    ) -> None:
        """
        Apply temporary throttle.
        """

        duration = (
            decision.throttle_duration
            if decision.throttle_duration > 0
            else THROTTLE_DURATION
        )

        pipe.setex(
            f"{base}:throttled",
            duration,
            "1",
        )

    # ==========================================================
    # RECOVERY
    # ==========================================================

    def _apply_recovery(
        self,
        pipe,
        context: PenaltyContext,
        decision: PenaltyDecision,
    ) -> None:
        """
        Recovery is already reflected through the
        reputation delta.

        This method exists so future versions can
        persist additional recovery statistics.
        """

        if decision.recovery_delta == 0:
            return

        # Future:
        # pipe.incr(...)
        # pipe.set(...)
        # pipe.hincrby(...)

        return

    # ==========================================================
    # OPTIONAL HELPERS
    # ==========================================================

    @staticmethod
    def _safe_int(value) -> int:
        if value is None:
            return 0

        if isinstance(value, bytes):
            value = value.decode()

        try:
            return int(float(value))
        except Exception:
            return 0

    @staticmethod
    def _safe_float(value) -> float:
        if value is None:
            return 0.0

        if isinstance(value, bytes):
            value = value.decode()

        try:
            return float(value)
        except Exception:
            return 0.0


redis_repository = RedisRepository()