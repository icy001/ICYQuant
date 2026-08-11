"""Autonomy Policy — Controls autonomy boundaries and levels.

LEVEL 0: Manual — no autonomous actions
LEVEL 1: Research Suggestion — suggest research ideas
LEVEL 2: Automatic Experiment — auto-run experiments
LEVEL 3: Automatic Candidate Generation — auto-generate candidates
LEVEL 4: Automatic Strategy Validation — auto-validate strategies
LEVEL 5: Production Proposal — propose for production (still requires approval)
"""

import logging
from enum import Enum
from typing import Any, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .autonomous_platform import AutonomyConfig

logger = logging.getLogger(__name__)


class AutonomyLevel(Enum):
    LEVEL_0_MANUAL = 0
    LEVEL_1_SUGGEST = 1
    LEVEL_2_EXPERIMENT = 2
    LEVEL_3_CANDIDATE = 3
    LEVEL_4_VALIDATE = 4
    LEVEL_5_PROPOSE = 5


class AutonomyPolicy:
    """Enforces autonomy boundaries for the autonomous quant platform."""

    def __init__(self, config: "AutonomyConfig") -> None:
        self.config = config
        self.level = config.level

    def can_suggest(self) -> bool:
        return self.level.value >= AutonomyLevel.LEVEL_1_SUGGEST.value

    def can_experiment(self) -> bool:
        return self.level.value >= AutonomyLevel.LEVEL_2_EXPERIMENT.value

    def can_generate_candidate(self) -> bool:
        return self.level.value >= AutonomyLevel.LEVEL_3_CANDIDATE.value

    def can_validate(self) -> bool:
        return self.level.value >= AutonomyLevel.LEVEL_4_VALIDATE.value

    def can_propose(self) -> bool:
        return self.level.value >= AutonomyLevel.LEVEL_5_PROPOSE.value

    def set_level(self, level: AutonomyLevel) -> None:
        self.level = level
        logger.info("Autonomy level set to %s", level.name)
