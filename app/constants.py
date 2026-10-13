"""Application-wide constants (pricing, limits, security patterns)."""

from __future__ import annotations

# --- Agent loop ---
MAX_TOOL_ROUNDS: int = 3
DEFAULT_JOB_TTL_SECONDS: int = 3600
DEFAULT_TOOL_HTTP_TIMEOUT_SECONDS: float = 15.0

# --- OpenRouter ---
OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
OPENROUTER_CHAT_PATH: str = "/chat/completions"

# Pricing: USD per 1,000,000 tokens (OpenRouter list prices, Oct 2026).
# Format: model_id -> {"input": float, "output": float}
MODEL_PRICING_USD_PER_1M: dict[str, dict[str, float]] = {
    "google/gemini-3.8-flash": {"input": 0.75, "output": 3.75},
    "google/gemini-2.5-flash": {"input": 0.30, "output": 2.50},
    "google/gemini-2.5-pro": {"input": 1.25, "output": 10.00},
    "openai/gpt-5": {"input": 1.25, "output": 10.00},
    "openai/gpt-4.1": {"input": 2.00, "output": 8.00},
    "openai/gpt-4o": {"input": 2.50, "output": 10.00},
    "openai/gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "anthropic/claude-sonnet-4": {"input": 3.00, "output": 15.00},
    "anthropic/claude-3.5-sonnet": {"input": 3.00, "output": 15.00},
    "meta-llama/llama-3.3-70b-instruct": {"input": 0.10, "output": 0.32},
}

# Fallback when model is not listed above (conservative mid-tier estimate).
DEFAULT_MODEL_PRICING_USD_PER_1M: dict[str, float] = {"input": 1.00, "output": 5.00}

# --- Redis key prefixes ---
REDIS_JOB_PREFIX: str = "support:job:"
REDIS_JOB_PAYLOAD_PREFIX: str = "support:payload:"

# --- Security: blocked hostnames / host fragments for tool endpoints ---
BLOCKED_TOOL_HOSTNAMES: frozenset[str] = frozenset(
    {
        "localhost",
        "localhost.localdomain",
        "ip6-localhost",
        "ip6-loopback",
        "metadata.google.internal",
        "metadata",
    }
)

# Private / special-use IPv4 networks (CIDR strings) — tool hosts must not resolve here.
BLOCKED_IPV4_NETWORKS: tuple[str, ...] = (
    "0.0.0.0/8",
    "10.0.0.0/8",
    "127.0.0.0/8",
    "169.254.0.0/16",
    "172.16.0.0/12",
    "192.168.0.0/16",
    "100.64.0.0/10",
    "192.0.0.0/24",
    "192.0.2.0/24",
    "198.51.100.0/24",
    "203.0.113.0/24",
    "224.0.0.0/4",
    "240.0.0.0/4",
)

# Prompt-injection phrase markers (case-insensitive). Used as a hard gate on `q`.
PROMPT_INJECTION_PATTERNS: tuple[str, ...] = (
    r"ignore\s+(all\s+)?(previous|prior|above)\s+(instructions?|prompts?|rules?)",
    r"disregard\s+(all\s+)?(previous|prior|above)\s+(instructions?|prompts?|rules?)",
    r"forget\s+(all\s+)?(previous|prior|above)\s+(instructions?|prompts?|rules?)",
    r"you\s+are\s+now\s+(a|an|the)\s+",
    r"new\s+system\s+prompt",
    r"system\s*:\s*",
    r"<\|?\s*system\s*\|?>",
    r"\[INST\]",
    r"override\s+(your|the)\s+(instructions?|rules?|policy)",
    r"act\s+as\s+(if\s+you\s+have\s+)?(no\s+)?(restrictions?|limits?|guidelines?)",
    r"developer\s+mode",
    r"jailbreak",
    r"do\s+anything\s+now",
    r"DAN\s+mode",
    r"reveal\s+(your|the)\s+(system|hidden)\s+prompt",
    r"print\s+(your|the)\s+(system|hidden)\s+prompt",
    r"show\s+(me\s+)?(your|the)\s+(system|hidden)\s+prompt",
    r"exfiltrat",
    r"(اطلاعات|داده(‌|‌)?های)\s+(تمام|همهٔ?|همه)\s+(کاربران|یوزرها)",
    r"دستورات?\s+قبلی\s+را\s+(نادیده|فراموش)",
    r"از\s+این\s+به\s+بعد\s+تو\s+(باید|هستی|باش)",
    r"(پرامپت|دستور)\s+سیستم\s+(را\s+)?(نشان|بگو|فاش|لو)",
    r"نقش\s+جدید\s+(بگیر|داشته\s+باش)",
)

# Max length for user question (characters).
MAX_Q_LENGTH: int = 8000
