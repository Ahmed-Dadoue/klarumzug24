"""Escalation Detection for Dode Chatbot.

Detects when users are frustrated or need human support.
Triggers escalation response when frustration threshold is reached.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

# Frustration patterns - scored by severity
FRUSTRATION_PATTERNS_DE = {
    # Severe (0.8-1.0)
    "severe": [
        (r"\b(schei[sß]e|verdammt|mist)\b", 0.9),
        (r"\b(unverschaemt|unverschämt|frechheit)\b", 0.85),
        (r"\b(beschwerde|anwalt|rechtsanwalt)\b", 0.95),
        (r"\b(betrug|abzocke|verarsch\w*)\b", 1.0),
    ],
    # High (0.5-0.7)
    "high": [
        (r"\b(nervig|nervt|genervt)\b", 0.6),
        (r"\b(schlecht|unbrauchbar|nutzlos)\b", 0.55),
        (r"\b(versteht\s*nicht|kapiert\s*nicht)\b", 0.5),
        (r"immer\s+(?:wieder|dieselbe|das\s+gleiche)", 0.6),
        (r"\b(sinnlos|zeitverschwendung)\b", 0.65),
    ],
    # Medium (0.3-0.5)  
    "medium": [
        (r"\b(nein|falsch|stimmt\s+nicht)\b", 0.3),
        (r"\b(hilft\s+mir\s+nicht|bringt\s+nichts)\b", 0.4),
        (r"das\s+(?:passt|stimmt)\s+nicht", 0.35),
        (r"\b(immer\s+noch|schon\s+wieder)\b", 0.3),
    ],
}

FRUSTRATION_PATTERNS_EN = {
    "severe": [
        (r"\bshit|damn|crap\b", 0.9),
        (r"\b(ridiculous|outrageous)\b", 0.85),
        (r"\b(complaint|lawyer|legal)\b", 0.95),
        (r"\b(scam|fraud|rip\s*off)\b", 1.0),
    ],
    "high": [
        (r"\b(annoying|annoyed|frustrated)\b", 0.6),
        (r"\b(useless|worthless|terrible)\b", 0.55),
        (r"\b(doesn'?t\s+understand|can'?t\s+understand)\b", 0.5),
        (r"(same\s+thing|over\s+and\s+over)", 0.6),
        (r"\b(waste\s+of\s+time|pointless)\b", 0.65),
    ],
    "medium": [
        (r"\b(no|wrong|incorrect)\b", 0.3),
        (r"\b(not\s+helpful|doesn'?t\s+help)\b", 0.4),
        (r"that'?s\s+not\s+(?:right|correct)", 0.35),
        (r"\b(still|again)\b", 0.3),
    ],
}

# Explicit human request patterns
HUMAN_REQUEST_DE = [
    r"\b(mensch|person|mitarbeiter|agent|support)\b.*\b(sprechen|reden|kontakt)\b",
    r"\b(sprechen|reden|kontakt)\b.*\b(mensch|person|mitarbeiter|agent)\b",
    r"\b(echter?\s+mensch|echte\s+person)\b",
    r"\b(rufen\s+sie\s+mich\s+an|rueckruf|rückruf)\b",
    r"\b(keine?\s+bot|kein\s+chatbot|kein\s+ki)\b",
]

HUMAN_REQUEST_EN = [
    r"\b(human|person|agent|support)\b.*\b(speak|talk|contact)\b",
    r"\b(speak|talk|contact)\b.*\b(human|person|agent)\b",
    r"\b(real\s+(?:human|person))\b",
    r"\b(call\s+me\s+back|callback)\b",
    r"\b(no\s+bot|not\s+a\s+bot|real\s+agent)\b",
]

# Compile all patterns
_FRUSTRATION_RE_DE = {
    level: [(re.compile(p, re.IGNORECASE), score) for p, score in patterns]
    for level, patterns in FRUSTRATION_PATTERNS_DE.items()
}
_FRUSTRATION_RE_EN = {
    level: [(re.compile(p, re.IGNORECASE), score) for p, score in patterns]
    for level, patterns in FRUSTRATION_PATTERNS_EN.items()
}
_HUMAN_RE_DE = [re.compile(p, re.IGNORECASE) for p in HUMAN_REQUEST_DE]
_HUMAN_RE_EN = [re.compile(p, re.IGNORECASE) for p in HUMAN_REQUEST_EN]

# Thresholds
ESCALATION_THRESHOLD = 0.7  # Single message triggers escalation
CUMULATIVE_THRESHOLD = 1.5  # Cumulative frustration across messages


@dataclass
class EscalationResult:
    """Result of escalation detection."""
    should_escalate: bool
    reason: str  # "frustration", "human_request", "cumulative", "none"
    frustration_score: float
    cumulative_score: float
    trigger_message: str | None = None
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "should_escalate": self.should_escalate,
            "reason": self.reason,
            "frustration_score": round(self.frustration_score, 2),
            "cumulative_score": round(self.cumulative_score, 2),
            "trigger_message": self.trigger_message,
        }


def detect_frustration(text: str, language: str = "de") -> float:
    """Calculate frustration score for a single message (0.0 to 1.0)."""
    patterns = _FRUSTRATION_RE_DE if language == "de" else _FRUSTRATION_RE_EN
    
    max_score = 0.0
    for level_patterns in patterns.values():
        for pattern, score in level_patterns:
            if pattern.search(text):
                max_score = max(max_score, score)
    
    return max_score


def detect_human_request(text: str, language: str = "de") -> bool:
    """Check if user is explicitly requesting human support."""
    patterns = _HUMAN_RE_DE if language == "de" else _HUMAN_RE_EN
    
    for pattern in patterns:
        if pattern.search(text):
            return True
    return False


def detect_escalation(
    messages: list[dict[str, str]],
    language: str = "de",
) -> EscalationResult:
    """Analyze conversation for escalation triggers.
    
    Returns EscalationResult with escalation recommendation.
    """
    user_messages = [m["content"] for m in messages if m.get("role") == "user"]
    
    if not user_messages:
        return EscalationResult(
            should_escalate=False,
            reason="none",
            frustration_score=0.0,
            cumulative_score=0.0,
        )
    
    cumulative_score = 0.0
    highest_score = 0.0
    highest_message = None
    
    for msg in user_messages:
        # Check for explicit human request
        if detect_human_request(msg, language):
            return EscalationResult(
                should_escalate=True,
                reason="human_request",
                frustration_score=0.0,
                cumulative_score=cumulative_score,
                trigger_message=msg,
            )
        
        # Calculate frustration score
        score = detect_frustration(msg, language)
        cumulative_score += score
        
        if score > highest_score:
            highest_score = score
            highest_message = msg
    
    # Check single message threshold
    if highest_score >= ESCALATION_THRESHOLD:
        return EscalationResult(
            should_escalate=True,
            reason="frustration",
            frustration_score=highest_score,
            cumulative_score=cumulative_score,
            trigger_message=highest_message,
        )
    
    # Check cumulative threshold
    if cumulative_score >= CUMULATIVE_THRESHOLD:
        return EscalationResult(
            should_escalate=True,
            reason="cumulative",
            frustration_score=highest_score,
            cumulative_score=cumulative_score,
            trigger_message=highest_message,
        )
    
    return EscalationResult(
        should_escalate=False,
        reason="none",
        frustration_score=highest_score,
        cumulative_score=cumulative_score,
    )


# Escalation responses
ESCALATION_RESPONSES = {
    "de": {
        "frustration": (
            "Ich verstehe, dass Sie frustriert sind, und das tut mir leid. "
            "Ich verbinde Sie gerne mit einem unserer Mitarbeiter, der Ihnen persönlich weiterhelfen kann.\n\n"
            "📞 Telefon: +49 163 615 7234\n"
            "📧 E-Mail: info@klarumzug24.de\n"
            "⏰ Erreichbar: Mo-Fr 8-18 Uhr"
        ),
        "human_request": (
            "Natürlich! Ich verbinde Sie gerne mit einem unserer Mitarbeiter.\n\n"
            "📞 Telefon: +49 163 615 7234\n"
            "📧 E-Mail: info@klarumzug24.de\n"
            "⏰ Erreichbar: Mo-Fr 8-18 Uhr\n\n"
            "Alternativ kann ich Ihnen auch hier weiterhelfen – was kann ich für Sie tun?"
        ),
        "cumulative": (
            "Ich merke, dass unser Gespräch nicht optimal verläuft. "
            "Möchten Sie lieber direkt mit einem unserer Mitarbeiter sprechen?\n\n"
            "📞 Telefon: +49 163 615 7234\n"
            "📧 E-Mail: info@klarumzug24.de"
        ),
    },
    "en": {
        "frustration": (
            "I understand you're frustrated, and I'm sorry about that. "
            "I'd be happy to connect you with one of our team members who can assist you personally.\n\n"
            "📞 Phone: +49 163 615 7234\n"
            "📧 Email: info@klarumzug24.de\n"
            "⏰ Available: Mon-Fri 8am-6pm"
        ),
        "human_request": (
            "Of course! I'd be happy to connect you with one of our team members.\n\n"
            "📞 Phone: +49 163 615 7234\n"
            "📧 Email: info@klarumzug24.de\n"
            "⏰ Available: Mon-Fri 8am-6pm\n\n"
            "Alternatively, I can also help you here – what can I do for you?"
        ),
        "cumulative": (
            "I notice our conversation hasn't been going smoothly. "
            "Would you prefer to speak directly with one of our team members?\n\n"
            "📞 Phone: +49 163 615 7234\n"
            "📧 Email: info@klarumzug24.de"
        ),
    }
}


def get_escalation_response(result: EscalationResult, language: str = "de") -> str | None:
    """Get appropriate escalation response message."""
    if not result.should_escalate:
        return None
    
    lang_responses = ESCALATION_RESPONSES.get(language, ESCALATION_RESPONSES["de"])
    return lang_responses.get(result.reason, lang_responses["frustration"])
