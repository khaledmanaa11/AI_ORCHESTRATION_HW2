"""Seeded placeholder player brain for Module H (RH1.1)."""
from __future__ import annotations

import random


class SeededPlayerBrain:
    """Deterministic, seeded placeholder player brain.

    Guarantees same seed ⇒ identical utterances run-to-run.
    No reliance on wall-clock, global entropy, or system time.
    """

    def __init__(self, seed: int, side: str) -> None:
        self.seed = seed
        self.side = side

    def generate_utterance(self, turn_number: int) -> str:
        """Deterministically generate an utterance for the given turn."""
        # Use seed + turn_number to ensure turn-level determinism
        state_rng = random.Random(self.seed + turn_number)
        adjectives = ["strong", "compelling", "unshakeable", "rational", "logical", "persuasive"]
        nouns = ["argument", "evidence", "rebuttal", "position", "clash", "framework"]
        adj = state_rng.choice(adjectives)
        noun = state_rng.choice(nouns)
        return f"This is a {adj} {noun} from {self.side} under seed {self.seed} at turn {turn_number}."
