import time
from datetime import datetime
from typing import List, Optional
import uuid

from app.models.schemas import (
    BankTransaction, LedgerEntry, PaymentRecord,
    NormalizedTransaction, ReconciliationResult,
    ReconciliationRun, ReconciliationMetrics, MatchStatus,
    ExceptionType, Source
)
from app.data.normalizer import normalize_bank, normalize_ledger, normalize_payment
from app.reconciliation.scorer import calculate_match_score
from app.reconciliation.matcher import find_exact_matches, find_fuzzy_matches, detect_duplicates, find_missing
from app.reconciliation.exceptions import (
    detect_exceptions, classify_result,
    generate_exception_reason, generate_recommended_action
)
from app.core.logging import get_logger

logger = get_logger(__name__)


class ReconciliationEngine:
    """Main reconciliation engine that orchestrates the full matching pipeline."""

    def __init__(self):
        self.results: List[ReconciliationResult] = []

    def run(
        self,
        bank_txns: List[BankTransaction],
        ledger_txns: List[LedgerEntry],
        payment_txns: List[PaymentRecord],
        ground_truth: Optional[List[dict]] = None
    ) -> ReconciliationRun:
        """Run full reconciliation pipeline across all source pairs."""
        start_time = time.time()
        logger.info("Starting reconciliation pipeline...")

        # Step 1: Normalize
        bank_norm = normalize_bank(bank_txns)
        ledger_norm = normalize_ledger(ledger_txns)
        payment_norm = normalize_payment(payment_txns)

        logger.info(f"Normalized: {len(bank_norm)} bank, {len(ledger_norm)} ledger, {len(payment_norm)} payment")

        # Step 2: Detect duplicates within each source
        duplicate_groups = []
        duplicate_groups.extend(detect_duplicates(bank_norm))
        duplicate_groups.extend(detect_duplicates(ledger_norm))
        duplicate_groups.extend(detect_duplicates(payment_norm))
        duplicate_ids = set()
        duplicate_results = []
        for group in duplicate_groups:
            for tx in group[1:]:  # Mark all but first as duplicate
                duplicate_ids.add(tx.id)
                duplicate_results.append(ReconciliationResult(
                    source_id=tx.id,
                    source_type=tx.source,
                    target_id=group[0].id,
                    target_type=group[0].source,
                    status=MatchStatus.DUPLICATE,
                    score=1.0,
                    exception_type=ExceptionType.DUPLICATE,
                    reason=f"Duplicate of {group[0].id}: same amount ({tx.amount}), date ({tx.date}), and currency ({tx.currency}).",
                    recommended_action=f"Verify if {tx.id} is an intentional duplicate of {group[0].id}. If not, remove the duplicate entry.",
                    confidence=1.0
                ))

        # Filter out duplicates from matching
        bank_clean = [t for t in bank_norm if t.id not in duplicate_ids]
        ledger_clean = [t for t in ledger_norm if t.id not in duplicate_ids]
        payment_clean = [t for t in payment_norm if t.id not in duplicate_ids]

        # Step 3: Reconcile pairs
        results = []
        matched_ids = set()

        # Bank <-> Ledger
        pair_results, pair_matched = self._reconcile_pair(bank_clean, ledger_clean, matched_ids)
        results.extend(pair_results)
        matched_ids.update(pair_matched)

        # Bank <-> Payment
        bank_unmatched = [t for t in bank_clean if t.id not in matched_ids]
        payment_unmatched = [t for t in payment_clean if t.id not in matched_ids]
        pair_results, pair_matched = self._reconcile_pair(bank_unmatched, payment_unmatched, matched_ids)
        results.extend(pair_results)
        matched_ids.update(pair_matched)

        # Ledger <-> Payment
        ledger_unmatched = [t for t in ledger_clean if t.id not in matched_ids]
        payment_unmatched2 = [t for t in payment_clean if t.id not in matched_ids]
        pair_results, pair_matched = self._reconcile_pair(ledger_unmatched, payment_unmatched2, matched_ids)
        results.extend(pair_results)
        matched_ids.update(pair_matched)

        # Step 4: Mark missing (unmatched transactions)
        all_normalized = bank_norm + ledger_norm + payment_norm
        missing_ids = find_missing(all_normalized, matched_ids | duplicate_ids)
        for mid in missing_ids:
            tx = next((t for t in all_normalized if t.id == mid), None)
            if tx:
                results.append(ReconciliationResult(
                    source_id=tx.id,
                    source_type=tx.source,
                    status=MatchStatus.MISSING,
                    score=0.0,
                    exception_type=ExceptionType.MISSING_TRANSACTION,
                    reason=f"No matching transaction found in other sources for {tx.id} ({tx.source.value}).",
                    recommended_action=f"Investigate missing counterpart for {tx.id}. Check if the transaction was recorded in the corresponding system.",
                    confidence=0.0
                ))

        # Add duplicate results
        results.extend(duplicate_results)

        # Step 5: Calculate metrics
        processing_time = time.time() - start_time
        accuracy = None
        if ground_truth:
            accuracy = self._evaluate_accuracy(results, ground_truth)
        metrics = self._calculate_metrics(results, processing_time, accuracy)

        run_id = str(uuid.uuid4())[:8]
        logger.info(f"Reconciliation complete: {metrics.matched}/{metrics.total_records} matched in {processing_time:.2f}s")

        return ReconciliationRun(
            run_id=run_id,
            timestamp=datetime.now().isoformat(),
            metrics=metrics,
            results=results
        )

    def _reconcile_pair(
        self,
        source_txns: List[NormalizedTransaction],
        target_txns: List[NormalizedTransaction],
        already_matched: set
    ) -> tuple[List[ReconciliationResult], set]:
        """Reconcile a pair of transaction lists."""
        results = []
        newly_matched = set()

        if not source_txns or not target_txns:
            return results, newly_matched

        # Phase 1: Exact matches
        exact = find_exact_matches(source_txns, target_txns)
        used_targets = set()

        for src, tgt, score in exact:
            if src.id in newly_matched or tgt.id in used_targets:
                continue
            exceptions = detect_exceptions(src, tgt, score)
            status = classify_result(score.total_score, exceptions)

            d1 = datetime.strptime(src.date, "%Y-%m-%d")
            d2 = datetime.strptime(tgt.date, "%Y-%m-%d")

            results.append(ReconciliationResult(
                source_id=src.id,
                source_type=src.source,
                target_id=tgt.id,
                target_type=tgt.source,
                status=status,
                score=round(score.total_score, 4),
                score_breakdown=score,
                amount_difference=round(abs(src.amount - tgt.amount), 2),
                date_difference=abs((d1 - d2).days),
                exception_type=exceptions[0] if exceptions else None,
                reason=generate_exception_reason(src, tgt, score.total_score, exceptions),
                recommended_action=generate_recommended_action(src, tgt, exceptions),
                confidence=round(score.total_score, 4)
            ))
            newly_matched.add(src.id)
            newly_matched.add(tgt.id)
            used_targets.add(tgt.id)

        # Phase 2: Fuzzy matches for remaining
        remaining_src = [t for t in source_txns if t.id not in newly_matched]
        remaining_tgt = [t for t in target_txns if t.id not in used_targets]

        fuzzy = find_fuzzy_matches(remaining_src, remaining_tgt, threshold=0.3)
        for src, tgt, score in fuzzy:
            if src.id in newly_matched or tgt.id in used_targets:
                continue
            exceptions = detect_exceptions(src, tgt, score)
            status = classify_result(score.total_score, exceptions)

            d1 = datetime.strptime(src.date, "%Y-%m-%d")
            d2 = datetime.strptime(tgt.date, "%Y-%m-%d")

            results.append(ReconciliationResult(
                source_id=src.id,
                source_type=src.source,
                target_id=tgt.id,
                target_type=tgt.source,
                status=status,
                score=round(score.total_score, 4),
                score_breakdown=score,
                amount_difference=round(abs(src.amount - tgt.amount), 2),
                date_difference=abs((d1 - d2).days),
                exception_type=exceptions[0] if exceptions else None,
                reason=generate_exception_reason(src, tgt, score.total_score, exceptions),
                recommended_action=generate_recommended_action(src, tgt, exceptions),
                confidence=round(score.total_score, 4)
            ))
            newly_matched.add(src.id)
            newly_matched.add(tgt.id)
            used_targets.add(tgt.id)

        return results, newly_matched

    def _calculate_metrics(
        self,
        results: List[ReconciliationResult],
        processing_time: float,
        accuracy: Optional[float] = None
    ) -> ReconciliationMetrics:
        """Calculate comprehensive reconciliation metrics."""
        total = len(results)
        if total == 0:
            return ReconciliationMetrics(
                total_records=0, matched=0, likely_matches=0,
                manual_review=0, mismatches=0, duplicates=0, missing=0,
                match_rate=0.0, average_confidence=0.0,
                total_amount_discrepancy=0.0, processing_time=processing_time,
                records_per_second=0.0, accuracy=accuracy
            )

        matched = sum(1 for r in results if r.status == MatchStatus.MATCHED)
        likely = sum(1 for r in results if r.status == MatchStatus.LIKELY_MATCH)
        review = sum(1 for r in results if r.status == MatchStatus.MANUAL_REVIEW)
        mismatch = sum(1 for r in results if r.status == MatchStatus.MISMATCH)
        dup = sum(1 for r in results if r.status == MatchStatus.DUPLICATE)
        missing = sum(1 for r in results if r.status == MatchStatus.MISSING)

        return ReconciliationMetrics(
            total_records=total,
            matched=matched,
            likely_matches=likely,
            manual_review=review,
            mismatches=mismatch,
            duplicates=dup,
            missing=missing,
            match_rate=round((matched / total) * 100, 1) if total else 0.0,
            average_confidence=round(sum(r.confidence for r in results) / total, 4) if total else 0.0,
            total_amount_discrepancy=round(sum(r.amount_difference for r in results), 2),
            processing_time=round(processing_time, 3),
            records_per_second=round(total / processing_time, 1) if processing_time > 0 else 0.0,
            accuracy=accuracy
        )

    def _evaluate_accuracy(
        self,
        results: List[ReconciliationResult],
        ground_truth: List[dict]
    ) -> float:
        """Evaluate reconciliation accuracy against ground truth."""
        if not ground_truth:
            return 0.0

        correct = 0
        total_gt = len(ground_truth)

        result_map = {r.source_id: r for r in results}

        for gt in ground_truth:
            source_id = gt["source_id"]
            expected_target = gt.get("expected_target_id", "")
            expected_status = gt.get("expected_status", "")

            if source_id in result_map:
                result = result_map[source_id]
                # Check if target matches
                target_match = (result.target_id == expected_target) if expected_target else True
                # Check if status category is broadly correct
                status_match = False
                if expected_status == "MATCHED" and result.status in (MatchStatus.MATCHED, MatchStatus.LIKELY_MATCH):
                    status_match = True
                elif expected_status == "MISSING" and result.status == MatchStatus.MISSING:
                    status_match = True
                elif expected_status == "DUPLICATE" and result.status == MatchStatus.DUPLICATE:
                    status_match = True
                elif expected_status in ("MANUAL_REVIEW", "LIKELY_MATCH") and result.status in (MatchStatus.LIKELY_MATCH, MatchStatus.MANUAL_REVIEW, MatchStatus.MATCHED):
                    status_match = True
                elif expected_status == "MISMATCH" and result.status == MatchStatus.MISMATCH:
                    status_match = True

                if target_match and status_match:
                    correct += 1
            elif expected_status == "MISSING":
                correct += 1  # Correctly identified as not found

        return round(correct / total_gt, 4) if total_gt > 0 else 0.0
