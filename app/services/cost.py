"""Token-usage cost calculation from fixed OpenRouter price tables."""

from __future__ import annotations

from app.constants import DEFAULT_MODEL_PRICING_USD_PER_1M, MODEL_PRICING_USD_PER_1M


def resolve_pricing(model: str) -> dict[str, float]:
    if model in MODEL_PRICING_USD_PER_1M:
        return MODEL_PRICING_USD_PER_1M[model]
    # Try without date/version suffix variants already exact-matched above.
    return dict(DEFAULT_MODEL_PRICING_USD_PER_1M)


def calculate_cost_usd(*, model: str, prompt_tokens: int, completion_tokens: int) -> float:
    pricing = resolve_pricing(model)
    input_cost = (prompt_tokens / 1_000_000) * pricing["input"]
    output_cost = (completion_tokens / 1_000_000) * pricing["output"]
    return round(input_cost + output_cost, 8)


class CostAccumulator:
    def __init__(self, model: str) -> None:
        self.model = model
        self.total_usd: float = 0.0
        self.prompt_tokens: int = 0
        self.completion_tokens: int = 0

    def add_usage(self, *, prompt_tokens: int, completion_tokens: int) -> None:
        self.prompt_tokens += max(0, prompt_tokens)
        self.completion_tokens += max(0, completion_tokens)
        self.total_usd = round(
            self.total_usd
            + calculate_cost_usd(
                model=self.model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            ),
            8,
        )
