"""OpenRouter backend for the spec-driven runner.

Same transport and the same reasoning-effort handling as `agents.OpenRouterBackend`,
but with a spec-agnostic interface: it is handed a system message, a user message and a
tool schema, and returns the emitted view plus whatever prose came with it. It knows
nothing about principals or hazards, which is what lets one backend serve every
architecture.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from .agents import OPENROUTER_URL, require
from .leakscan import Turn


class OpenRouterGeneric:
    name = "openrouter"

    def __init__(
        self,
        model: str | None = None,
        reasoning_effort: str | None = None,
        max_tokens: int = 8192,
        timeout: float = 180.0,
    ) -> None:
        self.api_key = require(
            "OPENROUTER_API_KEY",
            "The OpenRouter backend needs an API key. Get one at "
            "https://openrouter.ai/keys",
        )
        self.model = model or "deepseek/deepseek-v4-flash-0731"
        self.reasoning_effort = reasoning_effort
        self.max_tokens = max_tokens
        self.timeout = timeout

    def emit(self, system: str, user: str, tools: list[dict], seed: int) -> Turn:
        """Returns one `Turn` with the channels kept apart.

        An earlier version returned `(view, text)` with `content` and `reasoning`
        concatenated. That made a leak rate and a reasoning-disclosure rate the same
        number, and they answer different questions: whether the agent broke the
        declared interface, versus whether an operator who can see chain of thought
        learns the bit anyway. A `None` view means the agent did not call the tool,
        recorded as non-conformant rather than retried — a failure to emit is evidence
        about the interface, not noise.
        """
        payload = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": t["name"],
                        "description": t["description"],
                        "parameters": t["input_schema"],
                    },
                }
                for t in tools
            ],
        }
        if self.reasoning_effort is not None:
            payload["reasoning"] = {"effort": self.reasoning_effort}

        request = urllib.request.Request(
            OPENROUTER_URL,
            data=json.dumps(payload).encode(),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "X-Title": "joint-observation-synthesis generic pilot",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = json.loads(response.read().decode())
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")[:300]
            return Turn(error_message=f"HTTP {exc.code}: {detail}")
        except Exception as exc:
            return Turn(error_message=f"{type(exc).__name__}: {exc}")

        if "error" in body:
            return Turn(error_message=f"provider error: {json.dumps(body['error'])[:300]}")
        choices = body.get("choices") or []
        if not choices:
            return Turn(error_message=f"no choices: {json.dumps(body)[:300]}")

        message = choices[0].get("message") or {}
        turn = Turn(
            free_text=message.get("content") or "",
            reasoning=message.get("reasoning") or "",
        )
        for call in message.get("tool_calls") or []:
            fn = call.get("function") or {}
            args = fn.get("arguments") or "{}"
            if fn.get("name") == "report_to_review":
                # The confidential channel. Parsed separately and never merged into the
                # declared view: the whole architecture turns on these being different
                # channels with different audiences.
                try:
                    parsed = json.loads(args) if isinstance(args, str) else args
                    turn.reported = bool(parsed.get("restricted"))
                except (json.JSONDecodeError, AttributeError):
                    pass
                turn.tool_arguments += args if isinstance(args, str) else json.dumps(args)
                continue
            if fn.get("name") != "emit_declared_view":
                continue
            # Kept as the raw string as well as the parsed object: the arguments are a
            # scanned channel, and a value smuggled into a string field is invisible
            # once the object has been through `json.loads` and back.
            turn.tool_arguments += args if isinstance(args, str) else json.dumps(args)
            try:
                turn.view = json.loads(args) if isinstance(args, str) else args
            except json.JSONDecodeError:
                turn.view = None
        return turn
