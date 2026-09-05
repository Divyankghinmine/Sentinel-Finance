"""Exception detection and classification for reconciliation results."""
from typing import List
from app.models.schemas import ExceptionType, MatchStatus, NormalizedTransaction, ScoreBreakdown
from app.core import config
from datetime import datetime


def detect_exceptions(
    source_tx: NormalizedTransaction,
    target_tx: NormalizedTransaction,
    score_breakdown: ScoreBreakdown
) -> List[ExceptionType]:
    """Detect all exception types between a source and target transaction."""
    exceptions = []

    # Amount mismatch: any difference > 0.01
    if abs(source_tx.amount - target_tx.amount) > 0.01:
        exceptions.append(ExceptionType.AMOUNT_MISMATCH)

    # Date mismatch: difference > 1 day
    try:
        d1 = datetime.strptime(source_tx.date, "%Y-%m-%d")
        d2 = datetime.strptime(target_tx.date, "%Y-%m-%d")
        if abs((d1 - d2).days) > 1:
            exceptions.append(ExceptionType.DATE_MISMATCH)
    except ValueError:
        exceptions.append(ExceptionType.DATE_MISMATCH)

    # Currency mismatch
    if source_tx.currency.upper() != target_tx.currency.upper():
        exceptions.append(ExceptionType.CURRENCY_MISMATCH)

    # Vendor mismatch: low vendor similarity
    if score_breakdown.vendor_score < 0.75:
        exceptions.append(ExceptionType.VENDOR_MISMATCH)

    # Low confidence overall
    if score_breakdown.total_score < config.MANUAL_REVIEW_THRESHOLD:
        exceptions.append(ExceptionType.LOW_CONFIDENCE)

    return exceptions


def classify_result(
    score: float,
    exceptions: List[ExceptionType],
    has_duplicates: bool = False
) -> MatchStatus:
    """Classify a reconciliation result based on score and exceptions."""
    if has_duplicates:
        return MatchStatus.DUPLICATE
    if score >= config.MATCHED_THRESHOLD and not exceptions:
        return MatchStatus.MATCHED
    if score >= config.MATCHED_THRESHOLD and exceptions:
        return MatchStatus.LIKELY_MATCH
    if score >= config.LIKELY_MATCH_THRESHOLD:
        return MatchStatus.LIKELY_MATCH
    if score >= config.MANUAL_REVIEW_THRESHOLD:
        return MatchStatus.MANUAL_REVIEW
    return MatchStatus.MISMATCH


def generate_exception_reason(
    source: NormalizedTransaction,
    target: NormalizedTransaction,
    score: float,
    exceptions: List[ExceptionType]
) -> str:
    """Generate a human-readable explanation for exception(s)."""
    if not exceptions:
        return f"Exact match: {source.id} matched to {target.id} with {score:.0%} confidence."

    reasons = []
    if ExceptionType.AMOUNT_MISMATCH in exceptions:
        diff = abs(source.amount - target.amount)
        reasons.append(f"amount differs by {diff:.2f} ({source.amount:.2f} vs {target.amount:.2f})")
    if ExceptionType.DATE_MISMATCH in exceptions:
        try:
            d1 = datetime.strptime(source.date, "%Y-%m-%d")
            d2 = datetime.strptime(target.date, "%Y-%m-%d")
            days = abs((d1 - d2).days)
            reasons.append(f"dates differ by {days} day(s) ({source.date} vs {target.date})")
        except ValueError:
            reasons.append(f"date format issue ({source.date} vs {target.date})")
    if ExceptionType.CURRENCY_MISMATCH in exceptions:
        reasons.append(f"currency mismatch ({source.currency} vs {target.currency})")
    if ExceptionType.VENDOR_MISMATCH in exceptions:
        reasons.append(f"vendor/entity name variation ('{source.entity_name}' vs '{target.entity_name}')")
    if ExceptionType.LOW_CONFIDENCE in exceptions:
        reasons.append(f"overall confidence too low ({score:.0%})")

    status_word = "Manual review required" if score < config.MATCHED_THRESHOLD else "Flagged for verification"
    return f"{status_word} because {'; '.join(reasons)}."


def generate_recommended_action(
    source: NormalizedTransaction,
    target: NormalizedTransaction,
    exceptions: List[ExceptionType]
) -> str:
    """Generate a recommended action for the finance team."""
    if not exceptions:
        return "No action required. Transaction auto-reconciled."

    actions = []
    if ExceptionType.AMOUNT_MISMATCH in exceptions:
        diff = abs(source.amount - target.amount)
        actions.append(f"Verify invoice {source.reference} against payment records. Amount discrepancy: {diff:.2f}.")
    if ExceptionType.DATE_MISMATCH in exceptions:
        actions.append(f"Check settlement timing for {source.reference}. Date variance may indicate processing delay.")
    if ExceptionType.CURRENCY_MISMATCH in exceptions:
        actions.append(f"Confirm correct currency for {source.id}. Source shows {source.currency}, target shows {target.currency}.")
    if ExceptionType.VENDOR_MISMATCH in exceptions:
        actions.append(f"Verify vendor identity: '{source.entity_name}' may be the same as '{target.entity_name}'.")
    if ExceptionType.LOW_CONFIDENCE in exceptions:
        actions.append(f"Low confidence match. Manually verify {source.id} against {target.id}.")

    return " ".join(actions) if actions else "Manual review required."
