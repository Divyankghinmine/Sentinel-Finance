from typing import List, Tuple, Optional
from app.models.schemas import NormalizedTransaction, ScoreBreakdown
from app.reconciliation.scorer import calculate_match_score
from app.core import config

def find_exact_matches(source_txns: List[NormalizedTransaction], target_txns: List[NormalizedTransaction]) -> List[Tuple[NormalizedTransaction, NormalizedTransaction, ScoreBreakdown]]:
    matches = []
    for s in source_txns:
        for t in target_txns:
            score = calculate_match_score(s, t)
            if score.total_score >= config.MATCHED_THRESHOLD:
                matches.append((s, t, score))
                break
    return matches

def find_fuzzy_matches(unmatched_source: List[NormalizedTransaction], unmatched_target: List[NormalizedTransaction], threshold: float = 0.5) -> List[Tuple[NormalizedTransaction, NormalizedTransaction, ScoreBreakdown]]:
    matches = []
    for s in unmatched_source:
        best_match = None
        best_score = None
        for t in unmatched_target:
            score = calculate_match_score(s, t)
            if score.total_score >= threshold:
                if not best_score or score.total_score > best_score.total_score:
                    best_score = score
                    best_match = t
        if best_match:
            matches.append((s, best_match, best_score))
    return matches

def find_best_match(source_tx: NormalizedTransaction, candidates: List[NormalizedTransaction]) -> Optional[Tuple[NormalizedTransaction, ScoreBreakdown]]:
    best_match = None
    best_score = None
    for t in candidates:
        score = calculate_match_score(source_tx, t)
        if not best_score or score.total_score > best_score.total_score:
            best_score = score
            best_match = t
    if best_match:
        return best_match, best_score
    return None

def detect_duplicates(transactions: List[NormalizedTransaction]) -> List[List[NormalizedTransaction]]:
    seen = {}
    duplicates = []
    for t in transactions:
        key = (t.amount, t.date, t.currency)
        if key in seen:
            seen[key].append(t)
        else:
            seen[key] = [t]
            
    for k, v in seen.items():
        if len(v) > 1:
            duplicates.append(v)
    return duplicates

def find_missing(all_normalized: List[NormalizedTransaction], matched_ids: set) -> List[str]:
    missing = []
    for t in all_normalized:
        if t.id not in matched_ids:
            missing.append(t.id)
    return missing
