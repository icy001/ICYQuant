from dataclasses import dataclass


@dataclass
class ResearchRequest:

    question: str

    context: dict
