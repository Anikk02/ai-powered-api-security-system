"""
Centralized configuration for the policy subsystem.

This module intentionally contains ONLY constants.
Business logic belongs inside the engines.
"""

from __future__ import annotations

# ==============================================================================
# Sliding Windows (seconds)
# ==============================================================================

WINDOW_SHORT = 60          # 1 minute
WINDOW_MEDIUM = 300        # 5 minutes
WINDOW_LONG = 1800         # 30 minutes

WINDOWS = {
    'short': WINDOW_SHORT,
    'medium': WINDOW_MEDIUM,
    'long': WINDOW_LONG
}

# ==============================================================================
# Redis TTLs
# ==============================================================================

TTL_REPUTATION = 60 * 60           # 1 hour
TTL_RISK_SCORE = 300               # 5 minutes
TTL_THROTTLE = 60                  # 1 minute
TTL_IP_TRACKING = 300              # 5 minutes
TTL_REQUEST_HISTORY = WINDOW_LONG
TTL_VIOLATIONS = WINDOW_LONG

# ==============================================================================
# Blocking Durations
# ==============================================================================

SOFT_BLOCK_DURATION = 60 * 60 * 2      # 2 hours
MEDIUM_BLOCK_DURATION = 60 * 60 * 6    # 6 hours
HARD_BLOCK_DURATION = 60 * 60 * 12     # 12 hours

BLOCK_DURATIONS = {
    "soft": SOFT_BLOCK_DURATION,
    "medium": MEDIUM_BLOCK_DURATION,
    "hard": HARD_BLOCK_DURATION,
}

# ==============================================================================
# Reputation Update Values
# ==============================================================================

# Increase when malicious
REPUTATION_BLOCK_PENALTY = 0.20
REPUTATION_THROTTLE_PENALTY = 0.05

# Decrease when behaving normally
REPUTATION_RECOVERY = -0.02

# Clamp
MIN_REPUTATION = 0.0
MAX_REPUTATION = 1.0

# ==============================================================================
# Reputation Weights
# ==============================================================================

IP_REPUTATION_WEIGHT = 0.50
IDENTITY_REPUTATION_WEIGHT = 0.30
FINGERPRINT_REPUTATION_WEIGHT = 0.20

# ==============================================================================
# Final Risk Weights
# ==============================================================================

RISK_WEIGHT_MODEL = 0.70
RISK_WEIGHT_REPUTATION = 0.10
RISK_WEIGHT_VIOLATIONS = 0.10
RISK_WEIGHT_REQUEST_RATE = 0.05
RISK_WEIGHT_ERRORS = 0.05

# ==============================================================================
# Normalization Limits
# ==============================================================================

MAX_VIOLATIONS = 30
MAX_REQUESTS = 250
MAX_ERRORS = 150

# ==============================================================================
# Adaptive Threshold Defaults
# ==============================================================================

DEFAULT_HIGH_THRESHOLD = 0.75
DEFAULT_MEDIUM_THRESHOLD = 0.50

HIGH_PERCENTILE = 85
MEDIUM_PERCENTILE = 65

EWMA_ALPHA = 0.30

MIN_HIGH_THRESHOLD = 0.60
MAX_HIGH_THRESHOLD = 0.75

MIN_MEDIUM_THRESHOLD = 0.50
MAX_MEDIUM_THRESHOLD = 0.60

THRESHOLD_SMOOTHING = 0.30

# History size per client
THRESHOLD_HISTORY = 300

# Minimum samples before using adaptive thresholds
MIN_SAMPLES = 30

# ==============================================================================
# Trust Engine
# ==============================================================================

# Trust starts at 1.0 and decreases toward 0.0
INITIAL_TRUST = 1.0

TRUST_REPUTATION_WEIGHT = 0.45
TRUST_RISK_WEIGHT = 0.35
TRUST_HISTORY_WEIGHT = 0.20

# ==============================================================================
# IP Rotation
# ==============================================================================

LOW_IP_ROTATION = 2
MEDIUM_IP_ROTATION = 3
HIGH_IP_ROTATION = 5
EXTREME_IP_ROTATION = 10

LOW_ROTATION_MULTIPLIER = 1.05
MEDIUM_ROTATION_MULTIPLIER = 1.15
HIGH_ROTATION_MULTIPLIER = 1.30
EXTREME_ROTATION_MULTIPLIER = 1.50

# ==============================================================================
# Hard Security Rules
# ==============================================================================

REPUTATION_HARD_BLOCK = 0.90

VIOLATIONS_MEDIUM_BLOCK = 50
VIOLATIONS_SOFT_BLOCK = 30

# ==============================================================================
# Recovery
# ==============================================================================

GOOD_REQUESTS_FOR_RECOVERY = 20

MAX_RECOVERY_PER_REQUEST = 0.02

MIN_RECOVERY_RISK = 0.20

RECOVERY_TRUST_THRESHOLD = 0.80

# ==============================================================================
# Throttling
# ==============================================================================

THROTTLE_DURATION = TTL_THROTTLE

# ==============================================================================
# Redis Keys
# ==============================================================================

REDIS_REPUTATION_PREFIX = "rep"

REDIS_IP_PREFIX = "ip"

REDIS_FP_PREFIX = "fp"

REDIS_CLIENT_PREFIX = "client"

REDIS_IDENTITY_PREFIX = "identity"

# ==============================================================================
# Actions
# ==============================================================================

ACTION_ALLOW = "allow"
ACTION_THROTTLE = "throttle"
ACTION_BLOCK = "block"

VALID_ACTIONS = {
    ACTION_ALLOW,
    ACTION_THROTTLE,
    ACTION_BLOCK,
}

# ==============================================================================
# Block Levels
# ==============================================================================

BLOCK_SOFT = "soft"
BLOCK_MEDIUM = "medium"
BLOCK_HARD = "hard"

VALID_BLOCK_LEVELS = {
    BLOCK_SOFT,
    BLOCK_MEDIUM,
    BLOCK_HARD,
}