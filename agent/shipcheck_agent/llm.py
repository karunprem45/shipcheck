"""LLM clients. ClaudeClient for real runs, FakeLLM for tests and offline CI."""
import json
import os


class FakeLLM:
    """Returns canned responses in order, so CI never needs an API key."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def complete(self, system, prompt):
        self.calls.append(prompt)
        return self.responses.pop(0)


class ClaudeClient:
    def __init__(self, model=None):
        key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        if not key:  # CI passes an empty string when the secret is not set
            raise KeyError("ANTHROPIC_API_KEY")
        import anthropic  # lazy import so tests run without the package
        self.client = anthropic.Anthropic(api_key=key)
        self.model = model or os.environ.get("SHIPCHECK_MODEL", "claude-sonnet-4-5")

    def complete(self, system, prompt):
        msg = self.client.messages.create(
            model=self.model, max_tokens=2000, system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(b.text for b in msg.content if b.type == "text")


def parse_json(text):
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else ""
        text = text.rsplit("```", 1)[0]
    return json.loads(text)
