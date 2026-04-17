"""Dode Learning Cycle – self-improving chatbot knowledge system."""

from .conversation_store import save_conversation, get_unanalyzed_conversations, mark_analyzed
from .insight_store import get_active_insights, build_insights_prompt_block
from .analyzer import analyze_conversations
from .reward_scoring import (
    calculate_reward_score,
    score_conversation,
    score_unscored_conversations,
    get_reward_stats,
)
from .confidence_decay import (
    apply_decay_to_all,
    record_insight_feedback,
    get_decay_status,
    boost_insight,
)
from .escalation_detector import (
    detect_escalation,
    detect_frustration,
    get_escalation_response,
    EscalationResult,
)
from .feedback_loop import (
    update_conversation_outcome,
    batch_process_feedback,
)
from .deduplication import (
    is_duplicate,
    find_similar_insights,
    deduplicate_all_insights,
    get_duplicate_candidates,
)

__all__ = [
    # Conversation Store
    "save_conversation",
    "get_unanalyzed_conversations",
    "mark_analyzed",
    # Insight Store
    "get_active_insights",
    "build_insights_prompt_block",
    # Analyzer
    "analyze_conversations",
    # Reward Scoring
    "calculate_reward_score",
    "score_conversation",
    "score_unscored_conversations",
    "get_reward_stats",
    # Confidence Decay
    "apply_decay_to_all",
    "record_insight_feedback",
    "get_decay_status",
    "boost_insight",
    # Escalation Detection
    "detect_escalation",
    "detect_frustration",
    "get_escalation_response",
    "EscalationResult",
    # Feedback Loop
    "update_conversation_outcome",
    "batch_process_feedback",
    # Deduplication
    "is_duplicate",
    "find_similar_insights",
    "deduplicate_all_insights",
    "get_duplicate_candidates",
]
