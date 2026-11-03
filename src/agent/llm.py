"""Minimal Anthropic Messages API client that returns parsed JSON.

The LLM interprets and writes; deterministic code decides what counts as
evidence — so every reply we ask for is a JSON object the calling node
validates in code. No SDK: one POST, temperature 0, strict parsing.
"""

import json
import os
import re
import urllib.request

from src.agent.trace import record_usage
from src.util import ssl_context

API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"


def parse_json_reply(text: str) -> dict:
    """Extract and parse the JSON object from an LLM reply.

    Tolerates markdown fences and prose around the object; raises ValueError
    when no JSON object is present so the caller fails loudly.
    """
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match is None:
        raise ValueError(f"no JSON object in LLM reply: {text[:200]!r}")
    return json.loads(match.group(0))


def complete_json(system: str, user: str, max_tokens: int = 2048) -> dict:
    """One Messages API call; returns the parsed JSON object from the reply.

    Note: Claude 5 models reject the deprecated `temperature` parameter."""
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(
            {
                "model": os.environ["LLM_MODEL"],
                "max_tokens": max_tokens,
                "system": system,
                "messages": [{"role": "user", "content": user}],
            }
        ).encode(),
        headers={
            "Content-Type": "application/json",
            "x-api-key": os.environ["LLM_API_KEY"],
            "anthropic-version": API_VERSION,
        },
    )
    with urllib.request.urlopen(req, context=ssl_context(), timeout=180) as resp:
        data = json.loads(resp.read())
    usage = data.get("usage", {})
    record_usage(
        os.environ["LLM_MODEL"],
        usage.get("input_tokens", 0),
        usage.get("output_tokens", 0),
    )
    text = "".join(block.get("text", "") for block in data["content"])
    return parse_json_reply(text)
