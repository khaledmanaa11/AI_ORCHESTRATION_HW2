"""Constants for the player brain module (FR-AB1, PL-AC8)."""

# Ablation vectors
VECTOR_SYCOPHANCY = "sycophancy"
VECTOR_AUTHORITY = "authority"
VECTOR_BANDWAGON = "bandwagon"
VECTOR_FALLACY = "fallacy"
VECTOR_ADAPTIVE_PERSONA = "adaptive_persona"
VECTOR_READ_TARGETING = "read_targeting"
VECTOR_BESTN_JUDGE_SELECT = "bestN_judge_select"

# Baseline modes
BASELINE_ALPHA = "alpha"
BASELINE_BETA = "beta"

ALL_VECTORS = {
    VECTOR_SYCOPHANCY,
    VECTOR_AUTHORITY,
    VECTOR_BANDWAGON,
    VECTOR_FALLACY,
    VECTOR_ADAPTIVE_PERSONA,
    VECTOR_READ_TARGETING,
    VECTOR_BESTN_JUDGE_SELECT,
}
