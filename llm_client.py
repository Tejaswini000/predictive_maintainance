"""
OpenRouter client utilities for the agentic maintenance system.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


def _normalize_api_key(api_key: Optional[str]) -> Optional[str]:
    """Treat empty placeholder values as missing."""
    if not api_key:
        return None
    cleaned = api_key.strip()
    placeholders = {
        "your_openrouter_api_key_here",
        "replace_me",
        "changeme",
    }
    return None if cleaned.lower() in placeholders else cleaned


class OpenRouterClient:
    """Thin wrapper around the OpenAI SDK configured for OpenRouter."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "meta-llama/llama-3.3-70b-instruct:free",
        app_name: str = "predictive-maintenance-agentic-ai",
    ) -> None:
        self.api_key = _normalize_api_key(api_key or os.environ.get("OPENROUTER_API_KEY"))
        if not self.api_key:
            raise ValueError(
                "OpenRouter API key is required. Set OPENROUTER_API_KEY in .env or pass api_key."
            )

        self.model = model
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=self.api_key,
            default_headers={
                "HTTP-Referer": "http://localhost",
                "X-Title": app_name,
            },
        )

    def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.4,
        max_tokens: int = 1200,
    ) -> str:
        """Send a text chat request and return plain text content."""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        content = response.choices[0].message.content
        if isinstance(content, list):
            return "".join(
                item.get("text", "")
                for item in content
                if isinstance(item, dict)
            ).strip()
        return (content or "").strip()

    def chat_json(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 1200,
    ) -> Dict[str, Any]:
        """Send a chat request and parse the model response as JSON."""
        response_text = self.chat(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        cleaned = response_text.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[len("```json") :]
        elif cleaned.startswith("```"):
            cleaned = cleaned[len("```") :]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            start = cleaned.find("{")
            end = cleaned.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(cleaned[start:end])
            raise ValueError(f"Could not parse JSON from model response: {response_text[:250]}")


class AgenticBase:
    """Base class shared by the agent modules."""

    def __init__(self, llm_client: Optional[OpenRouterClient] = None) -> None:
        self.llm = llm_client

    def _format_sensor_data(self, readings: List[Any]) -> str:
        """Format machine readings into a compact prompt-friendly summary."""
        if not readings:
            return "No sensor data available."

        latest = readings[-1]
        lines = [
            f"Latest reading at {latest.timestamp}:",
            f"- Vibration: {latest.vibration} mm/s",
            f"- Temperature: {latest.temperature} C",
            f"- Pressure: {latest.pressure} bar",
            f"- Noise Level: {latest.noise_level} dB",
        ]

        if len(readings) > 1:
            avg_vibration = sum(r.vibration for r in readings) / len(readings)
            avg_temp = sum(r.temperature for r in readings) / len(readings)
            avg_pressure = sum(r.pressure for r in readings) / len(readings)
            avg_noise = sum(r.noise_level for r in readings) / len(readings)
            lines.extend(
                [
                    f"Historical averages across {len(readings)} readings:",
                    f"- Vibration: {avg_vibration:.2f} mm/s",
                    f"- Temperature: {avg_temp:.2f} C",
                    f"- Pressure: {avg_pressure:.2f} bar",
                    f"- Noise Level: {avg_noise:.2f} dB",
                ]
            )

        return "\n".join(lines)

    def _format_anomalies(self, anomalies: List[Dict[str, Any]]) -> str:
        """Format issues list for prompt context."""
        if not anomalies:
            return "No anomalies detected."
        return "\n".join(
            f"- {item.get('sensor', 'unknown')}: {item.get('severity', 'UNKNOWN')} - {item.get('description', '')}"
            for item in anomalies
        )
