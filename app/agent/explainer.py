"""AI Finance Explainer - Generates human-readable explanations for reconciliation decisions."""
from typing import List
from app.models.schemas import ReconciliationResult, ReconciliationMetrics, MatchStatus, ExceptionType
from app.core import config
from app.core.logging import get_logger

logger = get_logger(__name__)


class FinanceExplainer:
    """Generates explanations for reconciliation decisions.
    
    Supports two modes:
    - 'local': Deterministic template-based explanations (default, no API key needed)
    - 'openai': LLM-enhanced explanations (requires OPENAI_API_KEY)
    """

    def __init__(self, mode: str = None):
        self.mode = mode or config.AI_MODE
        if self.mode == "openai" and not config.OPENAI_API_KEY:
            logger.warning("OpenAI mode requested but no API key found. Falling back to local mode.")
            self.mode = "local"

    def explain_exception(self, result: ReconciliationResult) -> str:
        """Generate a human-readable explanation for a reconciliation exception."""
        if self.mode == "openai":
            return self._explain_with_openai(result)
        return self._explain_local(result)

    def _explain_local(self, result: ReconciliationResult) -> str:
        """Generate explanation using deterministic templates."""
        parts = []

        if result.status == MatchStatus.MATCHED:
            return f"Transaction {result.source_id} was confidently matched to {result.target_id} with a score of {result.score:.2f}. No discrepancies detected."

        if result.status == MatchStatus.MISSING:
            return f"Transaction {result.source_id} from {result.source_type.value} has no matching counterpart in other financial sources. This may indicate an unrecorded transaction, a timing difference, or a data entry omission."

        if result.status == MatchStatus.DUPLICATE:
            return f"Transaction {result.source_id} appears to be a duplicate of {result.target_id}. Both records share the same amount, date, and currency. Verify whether this represents a legitimate separate transaction or an erroneous duplicate entry."

        parts.append(f"Transaction {result.source_id} was matched to {result.target_id or 'no target'} with a confidence score of {result.score:.2f}.")

        if result.exception_type == ExceptionType.AMOUNT_MISMATCH:
            parts.append(f"Amount discrepancy of {result.amount_difference:.2f} detected.")
        if result.date_difference > 0:
            parts.append(f"Date difference of {result.date_difference} day(s) found.")
        if result.exception_type == ExceptionType.CURRENCY_MISMATCH:
            parts.append("Currency codes do not match between source and target records.")
        if result.exception_type == ExceptionType.VENDOR_MISMATCH:
            parts.append("Vendor/merchant names show significant variation between records.")

        if result.status == MatchStatus.MANUAL_REVIEW:
            parts.append("Manual review is recommended to confirm this match.")
        elif result.status == MatchStatus.MISMATCH:
            parts.append("The system could not confidently reconcile these records.")
        elif result.status == MatchStatus.LIKELY_MATCH:
            parts.append("This is a likely match but has minor discrepancies that should be verified.")

        return " ".join(parts)

    def _explain_with_openai(self, result: ReconciliationResult) -> str:
        """Generate explanation using OpenAI API. Falls back to local on failure."""
        try:
            import openai
            client = openai.OpenAI(api_key=config.OPENAI_API_KEY)
            prompt = f"""You are a finance controller AI. Explain this reconciliation result in 2-3 sentences:
- Source: {result.source_id} ({result.source_type.value})
- Target: {result.target_id} ({result.target_type.value if result.target_type else 'None'})
- Status: {result.status.value}
- Score: {result.score:.2f}
- Amount Difference: {result.amount_difference:.2f}
- Date Difference: {result.date_difference} days
- Exception: {result.exception_type.value if result.exception_type else 'None'}
Be specific and actionable."""
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=150,
                temperature=0.3
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.warning(f"OpenAI call failed: {e}. Falling back to local explanation.")
            return self._explain_local(result)

    def generate_summary(self, metrics: ReconciliationMetrics, results: List[ReconciliationResult]) -> str:
        """Generate a comprehensive reconciliation summary."""
        exceptions = [r for r in results if r.status not in (MatchStatus.MATCHED,)]
        unresolved = [r for r in results if r.status in (MatchStatus.MISMATCH, MatchStatus.MISSING)]

        # Find highest-risk exception types
        exception_types = {}
        for r in exceptions:
            if r.exception_type:
                et = r.exception_type.value
                exception_types[et] = exception_types.get(et, 0) + 1

        top_exceptions = sorted(exception_types.items(), key=lambda x: x[1], reverse=True)[:3]
        top_exc_str = ", ".join([f"{k.lower().replace('_', ' ')}s ({v})" for k, v in top_exceptions]) if top_exceptions else "none"

        summary_parts = [
            f"{metrics.matched} of {metrics.total_records} records were confidently reconciled ({metrics.match_rate}% match rate).",
        ]

        if metrics.likely_matches > 0:
            summary_parts.append(f"{metrics.likely_matches} records are likely matches requiring brief verification.")
        if metrics.manual_review > 0:
            summary_parts.append(f"{metrics.manual_review} records require manual review.")
        if len(unresolved) > 0:
            summary_parts.append(f"{len(unresolved)} records remain unresolved.")
        if metrics.duplicates > 0:
            summary_parts.append(f"{metrics.duplicates} duplicate transactions were detected.")

        summary_parts.append(f"The highest-risk exceptions are: {top_exc_str}.")

        if metrics.total_amount_discrepancy > 0:
            summary_parts.append(f"Total amount discrepancy across all exceptions: {metrics.total_amount_discrepancy:.2f}.")

        summary_parts.append(f"Average confidence score: {metrics.average_confidence:.2%}.")
        summary_parts.append(f"Processing completed in {metrics.processing_time:.2f} seconds.")

        if metrics.accuracy is not None:
            summary_parts.append(f"Reconciliation accuracy vs ground truth: {metrics.accuracy:.1%}.")

        return " ".join(summary_parts)

    def generate_recommendations(self, results: List[ReconciliationResult]) -> List[str]:
        """Generate actionable recommendations based on reconciliation results."""
        recommendations = []

        mismatches = [r for r in results if r.status == MatchStatus.MISMATCH]
        missing = [r for r in results if r.status == MatchStatus.MISSING]
        duplicates = [r for r in results if r.status == MatchStatus.DUPLICATE]
        reviews = [r for r in results if r.status == MatchStatus.MANUAL_REVIEW]
        amount_issues = [r for r in results if r.exception_type == ExceptionType.AMOUNT_MISMATCH]

        if amount_issues:
            total_disc = sum(r.amount_difference for r in amount_issues)
            recommendations.append(f"Review {len(amount_issues)} amount mismatches totaling {total_disc:.2f} in discrepancies.")

        if duplicates:
            recommendations.append(f"Investigate {len(duplicates)} potential duplicate transactions to prevent double-counting.")

        if missing:
            recommendations.append(f"Locate {len(missing)} missing transaction counterparts across financial systems.")

        if reviews:
            recommendations.append(f"Prioritize manual review of {len(reviews)} flagged transactions, focusing on those with the lowest confidence scores.")

        if mismatches:
            recommendations.append(f"Escalate {len(mismatches)} unresolved mismatches to senior finance staff for investigation.")

        if not recommendations:
            recommendations.append("All transactions reconciled successfully. No action items.")

        return recommendations
