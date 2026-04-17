"""Smart Insight Deduplication for Dode Learning Cycle.

Prevents duplicate or very similar insights from being stored.
Uses text similarity to detect near-duplicates.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any

from sqlalchemy.orm import Session

from .models import InsightDB

# Similarity threshold for considering two insights as duplicates
SIMILARITY_THRESHOLD = 0.85

# Common filler words to remove for comparison
STOPWORDS_DE = {
    "der", "die", "das", "den", "dem", "des", "ein", "eine", "einen", "einem",
    "einer", "und", "oder", "aber", "wenn", "weil", "dass", "ob", "als",
    "ist", "sind", "war", "waren", "wird", "werden", "hat", "haben", "hatte",
    "zu", "zum", "zur", "bei", "mit", "nach", "von", "vor", "aus", "auf", "an",
    "in", "im", "am", "um", "für", "über", "unter", "zwischen", "durch",
    "sehr", "auch", "noch", "schon", "nur", "immer", "oft", "manchmal",
    "ja", "nein", "nicht", "kein", "keine", "keinen", "keinem",
}

STOPWORDS_EN = {
    "the", "a", "an", "and", "or", "but", "if", "because", "that", "whether",
    "is", "are", "was", "were", "will", "be", "has", "have", "had",
    "to", "at", "by", "with", "after", "from", "before", "of", "on",
    "in", "for", "about", "above", "below", "between", "through",
    "very", "also", "still", "already", "only", "always", "often", "sometimes",
    "yes", "no", "not", "none",
}


def normalize_text(text: str, language: str = "de") -> str:
    """Normalize text for comparison."""
    # Lowercase
    text = text.lower()
    
    # Remove special characters
    text = re.sub(r"[^\w\s]", " ", text)
    
    # Remove stopwords
    stopwords = STOPWORDS_DE if language == "de" else STOPWORDS_EN
    words = text.split()
    words = [w for w in words if w not in stopwords and len(w) > 2]
    
    # Sort words for order-independent comparison
    words.sort()
    
    return " ".join(words)


def calculate_similarity(text1: str, text2: str, language: str = "de") -> float:
    """Calculate similarity between two texts (0.0 to 1.0)."""
    norm1 = normalize_text(text1, language)
    norm2 = normalize_text(text2, language)
    
    if not norm1 or not norm2:
        return 0.0
    
    # Use SequenceMatcher for similarity
    return SequenceMatcher(None, norm1, norm2).ratio()


def find_similar_insights(
    db: Session,
    content: str,
    category: str,
    threshold: float = SIMILARITY_THRESHOLD,
    language: str = "de",
) -> list[dict[str, Any]]:
    """Find existing insights similar to the given content."""
    existing = (
        db.query(InsightDB)
        .filter(InsightDB.category == category)
        .all()
    )
    
    similar = []
    for insight in existing:
        similarity = calculate_similarity(content, insight.content, language)
        if similarity >= threshold:
            similar.append({
                "id": insight.id,
                "content": insight.content,
                "confidence": insight.confidence,
                "similarity": round(similarity, 3),
                "active": insight.active,
            })
    
    # Sort by similarity descending
    similar.sort(key=lambda x: x["similarity"], reverse=True)
    return similar


def is_duplicate(
    db: Session,
    content: str,
    category: str,
    threshold: float = SIMILARITY_THRESHOLD,
    language: str = "de",
) -> bool:
    """Check if an insight is a duplicate of an existing one."""
    similar = find_similar_insights(db, content, category, threshold, language)
    return len(similar) > 0


def merge_similar_insights(
    db: Session,
    insight_id: int,
    keep_higher_confidence: bool = True,
) -> dict[str, Any] | None:
    """Merge similar insights into one.
    
    Finds insights similar to the given one and merges them,
    keeping the one with higher confidence (or the newer one).
    """
    target = db.query(InsightDB).filter(InsightDB.id == insight_id).first()
    if not target:
        return None
    
    similar = find_similar_insights(
        db, 
        target.content, 
        target.category,
        threshold=SIMILARITY_THRESHOLD,
    )
    
    # Filter out the target itself
    similar = [s for s in similar if s["id"] != insight_id]
    
    if not similar:
        return {
            "merged": 0,
            "kept_id": insight_id,
            "message": "No similar insights found",
        }
    
    merged_ids = []
    total_used_count = target.used_count
    total_success = target.success_count or 0
    total_failure = target.failure_count or 0
    
    for sim in similar:
        other = db.query(InsightDB).filter(InsightDB.id == sim["id"]).first()
        if other:
            # Accumulate stats
            total_used_count += other.used_count
            total_success += other.success_count or 0
            total_failure += other.failure_count or 0
            
            # Check if we should keep the other one instead
            if keep_higher_confidence and other.confidence > target.confidence:
                # Deactivate target, keep other
                target.active = False
                merged_ids.append(target.id)
                target = other
            else:
                # Deactivate other
                other.active = False
                merged_ids.append(other.id)
    
    # Update the kept insight with merged stats
    target.used_count = total_used_count
    target.success_count = total_success
    target.failure_count = total_failure
    
    db.commit()
    
    return {
        "merged": len(merged_ids),
        "merged_ids": merged_ids,
        "kept_id": target.id,
        "kept_content": target.content,
        "new_confidence": target.confidence,
    }


def deduplicate_all_insights(
    db: Session,
    threshold: float = SIMILARITY_THRESHOLD,
) -> dict[str, Any]:
    """Scan all insights and merge duplicates."""
    processed = set()
    total_merged = 0
    merge_groups = []
    
    # Get all active insights
    insights = (
        db.query(InsightDB)
        .filter(InsightDB.active == True)  # noqa: E712
        .order_by(InsightDB.confidence.desc())  # Start with highest confidence
        .all()
    )
    
    for insight in insights:
        if insight.id in processed:
            continue
        
        processed.add(insight.id)
        
        # Find similar insights
        similar = find_similar_insights(
            db,
            insight.content,
            insight.category,
            threshold=threshold,
        )
        
        # Filter out already processed
        similar = [s for s in similar if s["id"] not in processed and s["id"] != insight.id]
        
        if similar:
            # Merge these insights
            for sim in similar:
                processed.add(sim["id"])
            
            result = merge_similar_insights(db, insight.id)
            if result and result.get("merged", 0) > 0:
                total_merged += result["merged"]
                merge_groups.append({
                    "kept": result["kept_id"],
                    "merged": result.get("merged_ids", []),
                })
    
    return {
        "total_insights_scanned": len(insights),
        "duplicates_merged": total_merged,
        "merge_groups": merge_groups,
    }


def get_duplicate_candidates(
    db: Session,
    threshold: float = 0.7,  # Lower threshold to find potential duplicates
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Get pairs of potentially duplicate insights for review."""
    insights = (
        db.query(InsightDB)
        .filter(InsightDB.active == True)  # noqa: E712
        .all()
    )
    
    candidates = []
    checked_pairs = set()
    
    for i, insight1 in enumerate(insights):
        for insight2 in insights[i + 1:]:
            if insight1.category != insight2.category:
                continue
            
            pair_key = (min(insight1.id, insight2.id), max(insight1.id, insight2.id))
            if pair_key in checked_pairs:
                continue
            checked_pairs.add(pair_key)
            
            similarity = calculate_similarity(insight1.content, insight2.content)
            if similarity >= threshold:
                candidates.append({
                    "insight1_id": insight1.id,
                    "insight1_content": insight1.content,
                    "insight1_confidence": insight1.confidence,
                    "insight2_id": insight2.id,
                    "insight2_content": insight2.content,
                    "insight2_confidence": insight2.confidence,
                    "similarity": round(similarity, 3),
                    "category": insight1.category,
                })
    
    # Sort by similarity
    candidates.sort(key=lambda x: x["similarity"], reverse=True)
    return candidates[:limit]
