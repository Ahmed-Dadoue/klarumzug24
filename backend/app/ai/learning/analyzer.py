"""GPT-powered conversation analyzer – extracts insights from past conversations."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from sqlalchemy.orm import Session

from .conversation_store import get_unanalyzed_conversations, mark_analyzed
from .insight_store import save_insights

logger = logging.getLogger("klarumzug24")

ANALYSIS_MODEL = os.getenv("DODE_ANALYSIS_MODEL", "gpt-4.1-mini").strip()
BATCH_SIZE = 20

ANALYSIS_SYSTEM_PROMPT = """\
Du bist ein Analyse-Assistent fuer einen Umzugs-Chatbot namens "Dode".
Du bekommst eine Liste von Kundengespraechen (Chatverlauf).

Deine Aufgabe:
Analysiere die Gespraeche und extrahiere nuetzliche Erkenntnisse, die dem Chatbot helfen, in Zukunft besser zu antworten.

Kategorien fuer Erkenntnisse:
- faq_gap: Fragen, die Kunden gestellt haben, die der Bot nicht gut beantworten konnte
- common_objection: Haeufige Einwaende oder Bedenken der Kunden
- pricing_feedback: Feedback zu Preisen (zu hoch, ueberraschend, etc.)
- correction_pattern: Stellen, an denen der Kunde den Bot korrigiert hat
- conversation_tip: Allgemeine Tipps zur Verbesserung der Gespraechsfuehrung
- service_insight: Erkenntnisse ueber bestimmte Dienstleistungen

Regeln:
- Maximal 10 Erkenntnisse pro Batch
- Jede Erkenntnis max. 200 Zeichen
- Confidence zwischen 0.0 und 1.0 (wie sicher bist du, dass diese Erkenntnis nuetzlich ist)
- Nur Erkenntnisse mit echtem Mehrwert – keine Trivialitaeten
- Keine personenbezogenen Daten in den Erkenntnissen
- Formuliere Erkenntnisse als konkrete Handlungsanweisungen fuer den Bot

Antworte ausschliesslich als JSON-Array:
[
  {"category": "...", "content": "...", "confidence": 0.8},
  ...
]
"""


def analyze_conversations(
    db: Session,
    *,
    batch_size: int = BATCH_SIZE,
) -> dict[str, Any]:
    """Analyze unprocessed conversations and extract insights.

    Returns a summary dict with counts.
    """
    conversations = get_unanalyzed_conversations(db, limit=batch_size)
    if not conversations:
        return {"analyzed": 0, "insights_created": 0, "status": "no_pending"}

    # Build transcript block for GPT
    transcript_blocks: list[str] = []
    conversation_ids: list[str] = []

    for conv in conversations:
        try:
            messages = json.loads(conv.messages_json)
        except (json.JSONDecodeError, TypeError):
            continue

        conversation_ids.append(conv.conversation_id)
        lines = [
            (
                f"--- Gespraech {conv.conversation_id} "
                f"(Typ: {getattr(conv, 'conversation_type', 'real_user')}, "
                f"Outcome: {conv.outcome}, "
                f"Service: {conv.service_type or 'unbekannt'}, "
                f"Source: {getattr(conv, 'source_used', 'unbekannt') or 'unbekannt'}) ---"
            )
        ]
        for msg in messages:
            role = msg.get("role", "?")
            content = msg.get("content", "")
            # Truncate very long messages
            if len(content) > 500:
                content = content[:500] + "..."
            lines.append(f"{role}: {content}")
        transcript_blocks.append("\n".join(lines))

    if not transcript_blocks:
        return {"analyzed": 0, "insights_created": 0, "status": "no_valid_conversations"}

    full_transcript = "\n\n".join(transcript_blocks)

    # Call GPT for analysis
    try:
        from openai import OpenAI

        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))
        response = client.responses.create(
            model=ANALYSIS_MODEL,
            instructions=ANALYSIS_SYSTEM_PROMPT,
            input=f"Analysiere diese {len(transcript_blocks)} Gespraeche:\n\n{full_transcript}",
            max_output_tokens=1500,
            store=False,
        )
        raw_text = (getattr(response, "output_text", "") or "").strip()
    except Exception:
        logger.exception("Learning analysis GPT call failed")
        return {"analyzed": 0, "insights_created": 0, "status": "gpt_error"}

    # Parse insights from GPT response
    insights = _parse_insights_json(raw_text)
    if not insights:
        # Mark as analyzed even if no insights extracted (to avoid re-processing)
        mark_analyzed(db, conversation_ids)
        return {"analyzed": len(conversation_ids), "insights_created": 0, "status": "no_insights_extracted"}

    # Save insights
    saved_count = save_insights(db, insights, source_conversation_ids=conversation_ids)

    # Mark conversations as analyzed
    mark_analyzed(db, conversation_ids)

    return {
        "analyzed": len(conversation_ids),
        "insights_created": saved_count,
        "status": "success",
    }


def _parse_insights_json(raw_text: str) -> list[dict[str, Any]]:
    """Parse the GPT response as a JSON array of insights."""
    # Try to find JSON array in the response
    text = raw_text.strip()

    # Handle markdown code blocks
    if "```" in text:
        start = text.find("[")
        end = text.rfind("]")
        if start != -1 and end != -1:
            text = text[start : end + 1]

    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return parsed
    except json.JSONDecodeError:
        pass

    # Try to find array in text
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end != -1:
        try:
            parsed = json.loads(text[start : end + 1])
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            pass

    logger.warning("Could not parse insights JSON from GPT response: %s", text[:200])
    return []
