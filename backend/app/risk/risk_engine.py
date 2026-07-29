import logging
import math
from collections import deque

logger = logging.getLogger(__name__)

# CONFIG (tunable weights)
WEIGHTS = {
    'behavior': 0.4,
    'pattern': 0.35,
    'endpoint': 0.25,
}

SMOOTHED_HIGH = 0.7
SMOOTHED_MEDIUM = 0.45
RECENT_SCORES = deque(maxlen=200)

def _percentile(data, p):
    data = sorted(data)
    k = int(len(data) * p / 100)
    return data[min(k, len(data) - 1)]


def get_adaptive_thresholds():
    global SMOOTHED_HIGH, SMOOTHED_MEDIUM

    if len(RECENT_SCORES) < 30:
        return 0.70, 0.50

    data = list(RECENT_SCORES)

    dynamic_high = _percentile(data, 90)
    dynamic_medium = _percentile(data, 70)

    # Hybrid floor - keep reasonable lower bounds
    dynamic_high = max(0.60, min(dynamic_high, 0.75))  # Was 0.70
    dynamic_medium = max(0.40, min(dynamic_medium, 0.60))  # Was 0.45

    # Smoothing
    alpha = 0.3
    SMOOTHED_HIGH = (1 - alpha) * SMOOTHED_HIGH + alpha * dynamic_high
    SMOOTHED_MEDIUM = (1 - alpha) * SMOOTHED_MEDIUM + alpha * dynamic_medium

    # Clamp - MUCH LOWER upper bounds
    SMOOTHED_HIGH = max(0.60, min(SMOOTHED_HIGH, 0.75))
    SMOOTHED_MEDIUM = max(0.40, min(SMOOTHED_MEDIUM, 0.60))

    return SMOOTHED_HIGH, SMOOTHED_MEDIUM


def _non_linear_req_score(rpm: float) -> float:
    """
    Piecewise function for better discrimination:
    10 rpm → 0.2
    20 rpm → 0.45
    30 rpm → 0.7
    40 rpm → 0.85
    60 rpm → 1.0
    """
    if rpm <= 10:
        return 0.2 * (rpm / 10)
    elif rpm <= 20:
        return 0.2 + 0.25 * ((rpm - 10) / 10)
    elif rpm <= 30:
        return 0.45 + 0.25 * ((rpm - 20) / 10)
    elif rpm <= 40:
        return 0.70 + 0.15 * ((rpm - 30) / 10)
    elif rpm <= 60:
        return 0.85 + 0.15 * ((rpm - 40) / 20)
    else:
        return 1.0


# MAIN ENTRY - keep the same signature
async def compute_risk(signals, features: dict):
    """
    Returns:
        risk_score, label, explanation, contributions
    """
    try:
        is_suspicious_ua = features.get("is_suspicious_ua", False)
        top_ratio = features.get("top_endpoint_ratio", 0.0)
        
        # Additional features
        ip_changes = features.get("ip_changes", 0)
        error_rate = features.get("error_rate", 0.0)
        regularity = features.get("request_regularity", 1.0)
        is_bot = features.get("is_bot", False)
        sensitive_hits = features.get("sensitive_hits", 0)

        behavior_score = _behavior_risk(features, ip_changes, error_rate)
        pattern_score = _pattern_risk(features, regularity, is_bot, sensitive_hits)
        endpoint_score = _endpoint_risk(signals, features, sensitive_hits)

        # Your original risk calculation - unchanged
        risk = (
            behavior_score * WEIGHTS['behavior']
            + pattern_score * WEIGHTS['pattern']
            + endpoint_score * WEIGHTS['endpoint']
        )

        raw_score = min(risk, 1.0)

        RECENT_SCORES.append(raw_score)

        # Get adaptive thresholds (now with sane upper bounds)
        high_th, med_th = get_adaptive_thresholds()

        # LABEL
        if raw_score >= 0.80:
            label = "critical"
        if raw_score > high_th:
            label = "high"
        elif raw_score > med_th:
            label = "medium"
        else:
            label = "low"

        risk_score = round(raw_score, 4)

        # EXPLANATION - enhanced with new signals
        reasons = []

        if raw_score >= 80:
            reasons.append("⚠️ CRITICAL: Extremely high risk score")

        if behavior_score > 0.5:
            reasons.append("Abnormal traffic spike")
        if pattern_score > 0.5:
            reasons.append("Suspicious access pattern")
        if top_ratio > 0.8:
            reasons.append("Endpoint abuse detected")
        if endpoint_score > 0.4:
            reasons.append("Sensitive endpoint access")
        if is_suspicious_ua:
            reasons.append("Suspicious user agent")
        if error_rate > 0.3:
            reasons.append("High error rate")
        if ip_changes > 3:
            reasons.append("IP rotation detected")
        if regularity < 0.3:
            reasons.append("Irregular request timing")
        if is_bot:
            reasons.append("Bot-like behavior")
        if sensitive_hits > 5:
            reasons.append("Multiple sensitive endpoints")

        explanation = ", ".join(reasons) or "Normal behavior"

        # CONTRIBUTIONS - keep your original structure
        contributions = {
            "behavior": round(behavior_score, 3),
            "pattern": round(pattern_score, 3),
            "endpoint": round(endpoint_score, 3),
        }

        return risk_score, label, explanation, contributions

    except Exception as e:
        logger.error(f"Risk computation failed: {e}")
        return 0.0, "low", "fallback mode", {}


# 1. BEHAVIORAL RISK - ENHANCED
def _behavior_risk(features: dict, ip_changes: int = 0, error_rate: float = 0.0) -> float:
    """
    Enhanced behavior risk with:
    - Non-linear rate scoring (better discrimination)
    - IP rotation signal
    - Error rate signal
    - UA suspiciousness (existing)
    """
    req_count = features.get('req_per_min', 0)
    burst_ratio = features.get('burst_score', 0.0)
    is_suspicious_ua = features.get("is_suspicious_ua", False)

    # MODIFIED: Use non-linear scoring instead of linear
    req_score = _non_linear_req_score(req_count)
    burst_score = min(max(burst_ratio, 0.0), 1.0)

    # Your original behavior combination (probabilistic OR)
    combined = 1 - (1 - req_score) * (1 - burst_score)

    # NEW: IP changes signal
    ip_score = min(ip_changes / 5, 1.0)  # 5+ IPs = max signal

    # NEW: Error rate signal
    error_score = min(error_rate * 2, 1.0)  # 50% error rate = max signal

    # UA signal (your original)
    ua_score = 0.3 if is_suspicious_ua else 0.0

    # Enhanced fusion with all signals (preserving probabilistic OR approach)
    final_score = 1 - (1 - combined) * (1 - ip_score * 0.3) * (1 - error_score * 0.3) * (1 - ua_score)

    return final_score


# 2. PATTERN RISK - ENHANCED
def _pattern_risk(features: dict, regularity: float = 1.0, is_bot: bool = False, sensitive_hits: int = 0) -> float:
    """
    Enhanced pattern risk with:
    - Entropy (existing)
    - Hammering (existing)
    - Request regularity (new)
    - Bot flag (new)
    - Sensitive hits count (new)
    """
    entropy = features.get("endpoint_entropy", 0)
    top_ratio = features.get("top_endpoint_ratio", 0)
    req_per_min = features.get("req_per_min", 0)

    # Safety normalization
    entropy = min(max(entropy, 0.0), 1.0)
    top_ratio = min(max(top_ratio, 0.0), 1.0)

    # Your original entropy signal
    entropy_score = entropy

    # Your original hammering signal
    volume_factor = min(req_per_min / 30.0, 1.0)
    hammering_score = top_ratio * volume_factor

    # NEW: Regularity signal (low regularity = suspicious)
    regularity_score = 1 - min(max(regularity, 0.0), 1.0)

    # NEW: Bot signal
    bot_score = 0.5 if is_bot else 0.0

    # NEW: Sensitive hits signal
    sensitive_score = min(sensitive_hits / 10, 1.0)  # 10+ sensitive hits = max

    # Your original soft fusion, now enhanced with new signals
    score = 1 - (1 - entropy_score) * (1 - hammering_score) * (1 - regularity_score * 0.2) * (1 - bot_score * 0.15) * (1 - sensitive_score * 0.1)

    return round(score, 4)


# 3. ENDPOINT RISK - ENHANCED
# Exact path matches (no substring confusion)
_SENSITIVE_EXACT = {
    "/login", "/auth", "/admin", "/payment", "/reset-password",
    "/api/data", "/api/secure",
}

# Prefix matches
_SENSITIVE_PREFIXES = (
    "/api/admin",
    "/api/user",
    "/api/secure",
    "/api/data",
)

def _endpoint_risk(signals, features: dict, sensitive_hits: int = 0) -> float:
    """
    Enhanced endpoint risk with:
    - Higher base score for sensitive endpoints
    - Method risk (existing, slightly enhanced)
    - Repeat penalty for multiple sensitive hits (new)
    """
    endpoint = getattr(signals, "endpoint", "")
    method = getattr(signals, "method", "")

    is_sensitive = False

    # Exact match
    if endpoint in _SENSITIVE_EXACT:
        is_sensitive = True
    else:
        # Prefix match
        for prefix in _SENSITIVE_PREFIXES:
            if endpoint == prefix or endpoint.startswith(prefix + "/") or endpoint.startswith(prefix + "?"):
                is_sensitive = True
                break

    # MODIFIED: Higher base score for sensitive endpoints (0.8 instead of 0.6)
    endpoint_score = 0.8 if is_sensitive else 0.0
    method_score = 0.0

    # Context-aware method risk (your original logic, slightly enhanced)
    if is_sensitive and method in ["POST", "PUT", "DELETE"]:
        req_rate = features.get("req_per_min", 0)
        entropy = features.get("endpoint_entropy", 0)

        if req_rate > 20 or entropy > 0.6:
            method_score = 0.4
        elif req_rate > 10:
            method_score = 0.25
        else:
            method_score = 0.2  # Was 0.1 - increased for better discrimination

    # NEW: Repeat penalty - multiple sensitive hits
    repeat_penalty = min(sensitive_hits / 15, 0.2)  # Up to 0.2

    # Soft fusion with all signals
    score = 1 - (1 - endpoint_score) * (1 - method_score) * (1 - repeat_penalty)

    return score