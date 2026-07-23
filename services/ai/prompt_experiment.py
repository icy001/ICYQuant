"""
Prompt experiment framework.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class PromptExperiment:

    experiment_id: str

    control_prompt: str

    candidate_prompt: str