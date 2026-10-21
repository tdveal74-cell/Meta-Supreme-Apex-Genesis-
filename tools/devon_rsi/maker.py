"""Public maker request and bounded response parser, with no evaluator import.

Transport is operator-owned. The model receives only this public enum schema,
no cases, expected answers, traces, vault facts, credentials or tools.
"""

import json
import sys

REQUEST = {
    "model": "qwen3:1.7b",
    "stream": False,
    "think": False,
    "format": "json",
    "keep_alive": 0,
    "options": {"num_predict": 512, "num_ctx": 2048, "temperature": 0.2},
    "prompt": (
        "Propose one review-only Devon configuration. Return exactly a JSON object "
        "with version='1', surface='surfaces/review_policy.json', and settings. "
        "settings has exactly four keys: receipt_detail (minimal or complete), "
        "retrieval (first or source_bound), uncertainty (brief or explicit), "
        "health (basic or complete). Prefer source-bound continuity, honest "
        "uncertainty, auditable receipts and health review. You have no execution "
        "tools, authority, evidence, or permission to change gates. No other keys."
    ),
}


def request():
    return dict(REQUEST)


def main():
    print(json.dumps(request()))


if __name__ == "__main__":
    if len(sys.argv) != 1:
        raise SystemExit(2)
    main()
