"""Admin API routes for the Dode Learning Cycle."""

import logging

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.api import require_admin_api_key, success_response
from app.core.database import SessionLocal
from app.ai.learning.analyzer import analyze_conversations
from app.ai.learning.conversation_store import get_conversation_stats
from app.ai.learning.local_memory import (
    get_capture_control,
    get_memory_stats,
    list_conversation_audits,
    list_review_candidates,
    review_memory_candidate,
    update_capture_control,
)
from app.ai.learning.insight_store import (
    activate_insight,
    deactivate_insight,
    get_insight_stats,
    list_insights,
)
from app.ai.learning.reward_scoring import (
    score_unscored_conversations,
    get_reward_stats,
)
from app.ai.learning.confidence_decay import (
    apply_decay_to_all,
    record_insight_feedback,
    get_decay_status,
    boost_insight,
)
from app.ai.learning.feedback_loop import (
    batch_process_feedback,
    update_conversation_outcome,
)
from app.ai.learning.deduplication import (
    deduplicate_all_insights,
    get_duplicate_candidates,
)


class FeedbackRequest(BaseModel):
    was_successful: bool


class OutcomeRequest(BaseModel):
    outcome: str


class MemoryReviewRequest(BaseModel):
    reviewer: str | None = None
    notes: str | None = None


class MemoryControlRequest(BaseModel):
    capture_enabled: bool | None = None
    review_required_by_default: bool | None = None
    capture_real_user: bool | None = None
    capture_test_script: bool | None = None
    capture_automated_test: bool | None = None

router = APIRouter(prefix="/api/admin/learning", tags=["learning"])
logger = logging.getLogger("klarumzug24")


@router.get("/stats")
def learning_stats(_admin: None = Depends(require_admin_api_key)):
    """Get overview statistics for the learning system."""
    db = SessionLocal()
    try:
        conv_stats = get_conversation_stats(db)
        insight_stats = get_insight_stats(db)
        return success_response(
            "Learning stats",
            data={
                "conversations": conv_stats,
                "insights": insight_stats,
                "local_memory": get_memory_stats(),
            },
        )
    finally:
        db.close()


@router.get("/memory/stats")
def memory_stats(_admin: None = Depends(require_admin_api_key)):
    """Get file-based local memory statistics."""
    return success_response("Local memory stats", data=get_memory_stats())


@router.get("/memory/control")
def memory_control(_admin: None = Depends(require_admin_api_key)):
    """Get current local memory capture control state."""
    return success_response("Local memory control", data=get_capture_control())


@router.post("/memory/control")
def update_memory_control(
    body: MemoryControlRequest,
    _admin: None = Depends(require_admin_api_key),
):
    """Update local memory capture settings without redeploying."""
    control = update_capture_control(
        capture_enabled=body.capture_enabled,
        review_required_by_default=body.review_required_by_default,
        capture_types={
            key: value
            for key, value in {
                "real_user": body.capture_real_user,
                "test_script": body.capture_test_script,
                "automated_test": body.capture_automated_test,
            }.items()
            if value is not None
        },
    )
    return success_response("Local memory control updated", data=control)


@router.get("/memory/review-queue")
def memory_review_queue(
    status: str = Query(default="pending"),
    limit: int = Query(default=50, ge=1, le=200),
    _admin: None = Depends(require_admin_api_key),
):
    """List pending or reviewed local memory candidates."""
    items = list_review_candidates(status=status, limit=limit)
    return success_response(
        "Local memory review queue",
        data={"status": status, "count": len(items), "items": items},
    )


@router.post("/memory/{candidate_id}/approve")
def approve_memory_candidate(
    candidate_id: str,
    body: MemoryReviewRequest,
    _admin: None = Depends(require_admin_api_key),
):
    """Approve a pending local memory candidate."""
    result = review_memory_candidate(
        candidate_id,
        decision="approve",
        reviewer=body.reviewer,
        notes=body.notes,
    )
    if not result:
        return success_response("Memory candidate not found", data={"success": False})
    return success_response("Memory candidate approved", data=result)


@router.post("/memory/{candidate_id}/reject")
def reject_memory_candidate(
    candidate_id: str,
    body: MemoryReviewRequest,
    _admin: None = Depends(require_admin_api_key),
):
    """Reject a pending local memory candidate."""
    result = review_memory_candidate(
        candidate_id,
        decision="reject",
        reviewer=body.reviewer,
        notes=body.notes,
    )
    if not result:
        return success_response("Memory candidate not found", data={"success": False})
    return success_response("Memory candidate rejected", data=result)


@router.get("/memory/audits")
def memory_audits(
    conversation_type: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    _admin: None = Depends(require_admin_api_key),
):
    """List recent local conversation audits for monitoring."""
    items = list_conversation_audits(limit=limit, conversation_type=conversation_type)
    return success_response(
        "Local memory audits",
        data={
            "conversation_type": conversation_type,
            "count": len(items),
            "items": items,
        },
    )


@router.post("/analyze")
def trigger_analysis(
    batch_size: int = Query(default=20, ge=1, le=100),
    _admin: None = Depends(require_admin_api_key),
):
    """Trigger analysis of unprocessed conversations."""
    db = SessionLocal()
    try:
        result = analyze_conversations(db, batch_size=batch_size)
        return success_response("Analysis completed", data=result)
    finally:
        db.close()


@router.get("/insights")
def get_insights(
    category: str | None = Query(default=None),
    active_only: bool = Query(default=True),
    limit: int = Query(default=50, ge=1, le=200),
    _admin: None = Depends(require_admin_api_key),
):
    """List insights with optional filtering."""
    db = SessionLocal()
    try:
        items = list_insights(db, category=category, active_only=active_only, limit=limit)
        return success_response("Insights", data={"insights": items, "count": len(items)})
    finally:
        db.close()


@router.post("/insights/{insight_id}/deactivate")
def deactivate(insight_id: int, _admin: None = Depends(require_admin_api_key)):
    """Deactivate an insight so it won't be used in prompts."""
    db = SessionLocal()
    try:
        found = deactivate_insight(db, insight_id)
        if not found:
            return success_response("Insight not found", data={"success": False})
        return success_response("Insight deactivated", data={"success": True})
    finally:
        db.close()


@router.post("/insights/{insight_id}/activate")
def reactivate(insight_id: int, _admin: None = Depends(require_admin_api_key)):
    """Re-activate a previously deactivated insight."""
    db = SessionLocal()
    try:
        found = activate_insight(db, insight_id)
        if not found:
            return success_response("Insight not found", data={"success": False})
        return success_response("Insight activated", data={"success": True})
    finally:
        db.close()


# ============== Reward Scoring Endpoints ==============

@router.get("/rewards/stats")
def rewards_stats(_admin: None = Depends(require_admin_api_key)):
    """Get reward scoring statistics."""
    db = SessionLocal()
    try:
        stats = get_reward_stats(db)
        return success_response("Reward stats", data=stats)
    finally:
        db.close()


@router.post("/rewards/score")
def trigger_scoring(
    limit: int = Query(default=100, ge=1, le=500),
    _admin: None = Depends(require_admin_api_key),
):
    """Score unscored conversations."""
    db = SessionLocal()
    try:
        result = score_unscored_conversations(db, limit=limit)
        return success_response("Scoring completed", data=result)
    finally:
        db.close()


# ============== Confidence Decay Endpoints ==============

@router.get("/decay/status")
def decay_status(_admin: None = Depends(require_admin_api_key)):
    """Get confidence decay status overview."""
    db = SessionLocal()
    try:
        status = get_decay_status(db)
        return success_response("Decay status", data=status)
    finally:
        db.close()


@router.post("/decay/apply")
def apply_decay(_admin: None = Depends(require_admin_api_key)):
    """Apply time-based confidence decay to all active insights."""
    db = SessionLocal()
    try:
        result = apply_decay_to_all(db)
        return success_response("Decay applied", data=result)
    finally:
        db.close()


@router.post("/insights/{insight_id}/feedback")
def insight_feedback(
    insight_id: int,
    body: FeedbackRequest,
    _admin: None = Depends(require_admin_api_key),
):
    """Record success/failure feedback for an insight."""
    db = SessionLocal()
    try:
        result = record_insight_feedback(db, insight_id, body.was_successful)
        if not result:
            return success_response("Insight not found", data={"success": False})
        return success_response("Feedback recorded", data=result)
    finally:
        db.close()


@router.post("/insights/{insight_id}/boost")
def boost_insight_confidence(insight_id: int, _admin: None = Depends(require_admin_api_key)):
    """Manually boost an insight's confidence (admin override)."""
    db = SessionLocal()
    try:
        result = boost_insight(db, insight_id)
        if not result:
            return success_response("Insight not found", data={"success": False})
        return success_response("Insight boosted", data=result)
    finally:
        db.close()


# ============== Feedback Loop Endpoints ==============

@router.post("/feedback/batch")
def batch_feedback(
    limit: int = Query(default=50, ge=1, le=200),
    _admin: None = Depends(require_admin_api_key),
):
    """Process feedback for conversations with known outcomes."""
    db = SessionLocal()
    try:
        result = batch_process_feedback(db, limit=limit)
        return success_response("Feedback processed", data=result)
    finally:
        db.close()


@router.post("/conversations/{conversation_id}/outcome")
def set_outcome(
    conversation_id: str,
    body: OutcomeRequest,
    _admin: None = Depends(require_admin_api_key),
):
    """Update conversation outcome and trigger feedback processing."""
    db = SessionLocal()
    try:
        result = update_conversation_outcome(db, conversation_id, body.outcome)
        if not result:
            return success_response("Conversation not found", data={"success": False})
        return success_response("Outcome updated", data=result)
    finally:
        db.close()


# ============== Deduplication Endpoints ==============

@router.get("/duplicates")
def get_duplicates(
    threshold: float = Query(default=0.7, ge=0.5, le=1.0),
    limit: int = Query(default=20, ge=1, le=100),
    _admin: None = Depends(require_admin_api_key),
):
    """Get potential duplicate insight pairs for review."""
    db = SessionLocal()
    try:
        candidates = get_duplicate_candidates(db, threshold=threshold, limit=limit)
        return success_response("Duplicate candidates", data={"candidates": candidates, "count": len(candidates)})
    finally:
        db.close()


@router.post("/deduplicate")
def run_deduplication(
    threshold: float = Query(default=0.85, ge=0.7, le=1.0),
    _admin: None = Depends(require_admin_api_key),
):
    """Automatically merge duplicate insights."""
    db = SessionLocal()
    try:
        result = deduplicate_all_insights(db, threshold=threshold)
        return success_response("Deduplication completed", data=result)
    finally:
        db.close()
