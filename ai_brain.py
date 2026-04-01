"""OpenAI-backed AI brain for command parsing and general chat."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

try:
    from openai import OpenAI
except Exception:
    OpenAI = None


class AIBrain:
    def __init__(self, api_key: str):
        self.api_key = (api_key or "").strip()
        self.client = OpenAI(api_key=self.api_key) if (OpenAI and self.api_key) else None
        self.model = os.getenv("JARVIS_OPENAI_MODEL", "gpt-5.3").strip() or "gpt-5.3"

    def parse_command(self, text: str, actions: List[str]) -> Optional[Dict[str, Any]]:
        if not self.client:
            return None

        prompt = (
            "You are an AI assistant.\\n\\n"
            "Convert user input into a JSON command.\\n\\n"
            "Available actions:\\n"
            f"{actions}\\n\\n"
            f'Input: "{text}"\\n\\n'
            "Output JSON only:"
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
            )
            content = str(response.choices[0].message.content or "").strip()
            if not content:
                return None
            return json.loads(content)
        except Exception:
            return None

    def general_chat(self, text: str) -> str:
        if not self.client:
            return "AI error: OPENAI_API_KEY is not set"
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": text}],
            )
            return str(response.choices[0].message.content or "").strip() or "AI fallback returned an empty response"
        except Exception as exc:
            return f"AI error: {exc}"


def ai_process(command: str) -> str:
    """Compatibility helper for existing callers."""
    clean = (command or "").strip()
    if not clean:
        return "AI error: empty command"
    brain = AIBrain(api_key=os.getenv("OPENAI_API_KEY", ""))
    return brain.general_chat(clean)
