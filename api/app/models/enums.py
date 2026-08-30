from enum import Enum


class League(str, Enum):
    NBA = "NBA"
    WNBA = "WNBA"


class MatchMethod(str, Enum):
    """Entity-resolution tiers, per docs/adr/001-player-identity.md. Tier 4 rows
    should never actually exist in PlayerSourceMapping -- below-threshold matches
    go to a review queue (CAL-182) and only become a mapping row once a human
    confirms them, at which point they're recorded as tier4_manual for audit."""

    TIER1_PASSTHROUGH = "tier1_passthrough"
    TIER2_DETERMINISTIC = "tier2_deterministic"
    TIER3_FUZZY = "tier3_fuzzy"
    TIER4_MANUAL = "tier4_manual"
