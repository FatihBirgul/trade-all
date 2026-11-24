"""AI provider abstraction.

Centralizes all LLM calls in the backend so no API key is ever exposed to the
mobile client. Uses a vision-capable model to read chart screenshots and a
reasoning pass to turn the *structured* technical data into human-readable
scenarios. The AI is never the source of indicator numbers or the final score.

Swappable via env: AI_PROVIDER / AI_MODEL. Emergent Universal Key by default.
"""
from __future__ import annotations

import json
import logging
from typing import Dict, Optional, Tuple

from ..config import AI_MODEL, AI_PROVIDER, EMERGENT_LLM_KEY

logger = logging.getLogger(__name__)


def _extract_json(text: str) -> Optional[dict]:
    if not text:
        return None
    t = text.strip()
    if t.startswith("```"):
        t = t.split("```", 2)[1] if "```" in t else t
        if t.lstrip().lower().startswith("json"):
            t = t.lstrip()[4:]
    # find first { and last }
    start = t.find("{")
    end = t.rfind("}")
    if start == -1 or end == -1:
        return None
    try:
        return json.loads(t[start : end + 1])
    except Exception:
        return None


class AIProvider:
    def __init__(self):
        self.available = bool(EMERGENT_LLM_KEY)
        self.model = AI_MODEL
        self.provider = AI_PROVIDER

    def _chat(self, session_id: str, system_message: str):
        from emergentintegrations.llm.chat import LlmChat

        return LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=session_id,
            system_message=system_message,
        ).with_model(self.provider, self.model)

    async def analyze_image(self, image_base64: str, symbol_hint: str, tf_hint: str) -> Tuple[Optional[dict], Optional[str]]:
        """Vision pass: read the chart screenshot into structured observations."""
        if not self.available:
            return None, "AI provider not configured"
        try:
            from emergentintegrations.llm.chat import ImageContent, UserMessage

            raw = image_base64.split(",", 1)[1] if image_base64.startswith("data:") else image_base64

            system = (
                "You are a professional technical chart-reading assistant. You examine a screenshot of a "
                "financial candlestick chart and report ONLY what is visually observable. You must NOT invent "
                "exact indicator numbers. If something is not clearly visible, say 'uncertain'. You never give "
                "guaranteed calls. Respond with STRICT JSON only, no prose."
            )
            prompt = (
                f"User selected asset hint: {symbol_hint}. Timeframe hint: {tf_hint}. "
                "Analyze this chart image and return JSON with EXACTLY these keys: "
                "{\"detected_symbol\": string|null, \"detected_timeframe\": string|null, "
                "\"symbol_confidence\": \"high|medium|low|uncertain\", "
                "\"visible_price_levels\": [string], \"trend\": \"up|down|sideways|uncertain\", "
                "\"candlestick_structures\": [string], \"chart_patterns\": [string], "
                "\"support_resistance\": [string], \"breakouts_breakdowns\": [string], "
                "\"visible_indicators\": [string], \"potential_entry_zones\": [string], "
                "\"potential_target_zones\": [string], \"potential_invalidation_zones\": [string], "
                "\"notes\": string}."
            )
            chat = self._chat("vision-" + symbol_hint, system)
            resp = await chat.send_message(
                UserMessage(text=prompt, file_contents=[ImageContent(image_base64=raw)])
            )
            parsed = _extract_json(resp if isinstance(resp, str) else str(resp))
            if parsed is None:
                return None, "Could not parse vision response"
            return parsed, None
        except Exception as e:
            logger.exception("Vision analysis failed")
            return None, str(e)

    async def reason(self, payload: Dict) -> Tuple[Optional[dict], Optional[str]]:
        """Reasoning pass over STRUCTURED technical data -> scenarios + narrative."""
        if not self.available:
            return None, "AI provider not configured"
        try:
            from emergentintegrations.llm.chat import UserMessage

            system = (
                "You are an analytical decision-support assistant for financial markets. You receive STRUCTURED, "
                "pre-computed technical data (indicators, patterns, scores, levels) — you must reason ONLY from it "
                "and must NOT invent numbers or override the computed direction/score. This is analytical support, "
                "NOT financial advice. NEVER use words like 'guaranteed', 'certain', 'risk-free', or 'will definitely'. "
                "Always express uncertainty. Respond with STRICT JSON only."
            )
            prompt = (
                "Here is the structured analysis data:\n"
                + json.dumps(payload, default=str)
                + "\n\nReturn JSON with EXACTLY these keys: "
                "{\"summary\": string (2-3 sentences, neutral tone), "
                "\"scenarios\": {\"bullish\": string, \"bearish\": string, \"neutral\": string}, "
                "\"supporting_reasons\": [string] (3-6, evidence for the computed direction), "
                "\"contradicting_reasons\": [string] (2-5, risks/evidence against it)}. "
                "Reference the actual indicators, patterns and levels provided. Keep each string concise."
            )
            chat = self._chat("reason-" + str(payload.get("symbol", "x")), system)
            resp = await chat.send_message(UserMessage(text=prompt))
            parsed = _extract_json(resp if isinstance(resp, str) else str(resp))
            if parsed is None:
                return None, "Could not parse reasoning response"
            return parsed, None
        except Exception as e:
            logger.exception("Reasoning failed")
            return None, str(e)


_ai: Optional[AIProvider] = None


def get_ai_provider() -> AIProvider:
    global _ai
    if _ai is None:
        _ai = AIProvider()
    return _ai
