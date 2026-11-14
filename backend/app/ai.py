"""Future AI integration boundary. No model, network calls or scientific inference."""
from typing import Protocol


class ExperimentAnalyzer(Protocol):
    def analyze(self, experiments: list[dict]) -> dict:
        """Implement only after agreeing model inputs and output with analysts."""
        ...
