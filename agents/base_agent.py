"""Abstract base agent with LLM integration via OpenAI-compatible SDK."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Type, TypeVar

from loguru import logger
from openai import OpenAI
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential

from config import settings
from orchestrator.message_bus import MessageBus

T = TypeVar("T", bound=BaseModel)


class BaseAgent(ABC):
    """Base class for all analysis agents."""

    name: str = "base_agent"
    description: str = "Base agent"
    provider: str = "deepseek"  # "grok" or "deepseek"

    def __init__(self, bus: MessageBus) -> None:
        self.bus = bus
        self._client = self._build_client()
        self._prompt_text = self._load_prompt()

    def _build_client(self) -> OpenAI:
        if self.provider == "grok":
            return OpenAI(
                api_key=settings.GROK_API_KEY,
                base_url=settings.GROK_BASE_URL,
            )
        return OpenAI(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=settings.DEEPSEEK_BASE_URL,
        )

    @property
    def _model(self) -> str:
        return settings.GROK_MODEL if self.provider == "grok" else settings.DEEPSEEK_MODEL

    def _load_prompt(self) -> str:
        prompt_path = Path(__file__).parent.parent / "config" / "prompts" / f"{self.name}.md"
        if prompt_path.exists():
            return prompt_path.read_text()
        logger.warning(f"No prompt file found for {self.name} at {prompt_path}")
        return f"You are a {self.description}."

    @retry(
        stop=stop_after_attempt(settings.LLM_MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=2, max=30),
    )
    def _call_llm(self, user_message: str, response_model: Type[T] | None = None) -> str:
        """Call the LLM with retry logic. Returns raw text response."""
        messages = [
            {"role": "system", "content": self._prompt_text},
            {"role": "user", "content": user_message},
        ]
        logger.info(f"[{self.name}] Calling {self.provider} ({self._model})...")

        kwargs = dict(
            model=self._model,
            messages=messages,
        )
        if self._model == "deepseek-reasoner":
            # reasoner: max_tokens covers reasoning + content; no temperature support
            kwargs["max_tokens"] = 32768
        else:
            kwargs["max_tokens"] = settings.LLM_MAX_TOKENS
            kwargs["temperature"] = settings.LLM_TEMPERATURE
        response = self._client.chat.completions.create(**kwargs)
        msg = response.choices[0].message
        content = msg.content or ""
        if hasattr(msg, "reasoning_content") and msg.reasoning_content:
            logger.debug(f"[{self.name}] Reasoning: {len(msg.reasoning_content)} chars")
        logger.debug(f"[{self.name}] Content: {len(content)} chars")
        return content

    def _parse_json_response(self, text: str, model_class: Type[T]) -> T:
        """Extract JSON from LLM response and parse into Pydantic model."""
        # Try to find JSON block in the response
        cleaned = text.strip()

        # Handle markdown code fences
        if "```json" in cleaned:
            start = cleaned.index("```json") + 7
            end_idx = cleaned.find("```", start)
            cleaned = cleaned[start:end_idx].strip() if end_idx != -1 else cleaned[start:].strip()
        elif "```" in cleaned:
            start = cleaned.index("```") + 3
            end_idx = cleaned.find("```", start)
            cleaned = cleaned[start:end_idx].strip() if end_idx != -1 else cleaned[start:].strip()

        # Try direct parse
        parsed = None
        try:
            parsed = json.loads(cleaned)
            return model_class.model_validate(parsed)
        except json.JSONDecodeError:
            # Try to find any JSON object or array in the text
            for start_char, end_char in [("{", "}"), ("[", "]")]:
                if start_char in text and end_char in text:
                    start = text.index(start_char)
                    end = text.rindex(end_char) + 1
                    try:
                        parsed = json.loads(text[start:end])
                        return model_class.model_validate(parsed)
                    except json.JSONDecodeError:
                        continue
                    except Exception:
                        break
        except Exception:
            pass

        # JSON parsed but validation failed — ask deepseek-chat to fix the schema
        if parsed is not None:
            schema = model_class.model_json_schema()
            logger.warning(f"[{self.name}] JSON valid but schema mismatch, requesting fix...")
            fix_client = OpenAI(
                api_key=settings.DEEPSEEK_API_KEY,
                base_url=settings.DEEPSEEK_BASE_URL,
            )
            fix_resp = fix_client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": "Restructure the JSON to match the required schema. Output ONLY valid JSON."},
                    {"role": "user", "content": f"SCHEMA:\n{json.dumps(schema, indent=1)}\n\nDATA:\n{json.dumps(parsed, default=str)[:12000]}"},
                ],
                temperature=0.0,
                max_tokens=settings.LLM_MAX_TOKENS,
            )
            fix_text = fix_resp.choices[0].message.content or ""
            fix_text = fix_text.strip()
            if "```json" in fix_text:
                s = fix_text.index("```json") + 7
                e = fix_text.find("```", s)
                fix_text = fix_text[s:e].strip() if e != -1 else fix_text[s:].strip()
            elif "```" in fix_text:
                s = fix_text.index("```") + 3
                e = fix_text.find("```", s)
                fix_text = fix_text[s:e].strip() if e != -1 else fix_text[s:].strip()
            try:
                fixed = json.loads(fix_text)
                return model_class.model_validate(fixed)
            except Exception as e2:
                logger.error(f"[{self.name}] Schema fix also failed: {e2}")

        logger.error(f"[{self.name}] Failed to parse JSON\nRaw: {text[:500]}")
        raise ValueError(f"Failed to parse response into {model_class.__name__}")

    @abstractmethod
    async def gather_data(self) -> dict[str, Any]:
        """Gather all data needed for analysis. Returns dict of data."""
        ...

    @abstractmethod
    async def analyze(self, data: dict[str, Any]) -> BaseModel:
        """Run analysis using gathered data + LLM. Returns structured output."""
        ...

    async def run(self) -> BaseModel:
        """Execute the full agent pipeline: gather data → analyze → publish."""
        logger.info(f"[{self.name}] Starting...")
        data = await self.gather_data()
        result = await self.analyze(data)
        self.bus.publish(self.name, result)
        logger.info(f"[{self.name}] Complete.")
        return result
