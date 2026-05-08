"""Per-run cost ledger with budget enforcement."""
from __future__ import annotations

import threading
from dataclasses import dataclass


class BudgetExceeded(Exception):
    pass


@dataclass
class CostLedger:
    max_usd: float
    total_usd: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    n_calls: int = 0
    _lock: threading.Lock = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        self._lock = threading.Lock()

    def add(self, *, cost: float, in_tok: int | None, out_tok: int | None) -> None:
        with self._lock:
            self.total_usd += cost
            self.input_tokens += in_tok or 0
            self.output_tokens += out_tok or 0
            self.n_calls += 1

    def check_budget(self) -> None:
        if self.total_usd >= self.max_usd:
            raise BudgetExceeded(
                f"Run cost ${self.total_usd:.2f} reached budget ${self.max_usd:.2f}"
            )

    def estimate_remaining(self, mean_per_call: float) -> int:
        remaining = self.max_usd - self.total_usd
        if mean_per_call <= 0:
            return 10_000
        return max(0, int(remaining / mean_per_call))

    def to_dict(self) -> dict:
        return {
            "total_usd": round(self.total_usd, 4),
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "n_calls": self.n_calls,
        }
