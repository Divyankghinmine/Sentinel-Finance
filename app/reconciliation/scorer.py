from datetime import datetime
from rapidfuzz import fuzz
from app.models.schemas import NormalizedTransaction, ScoreBreakdown
from app.core import config

def calculate_reference_similarity(ref1: str, ref2: str) -> float:
    return fuzz.ratio(ref1, ref2) / 100.0

def calculate_amount_similarity(amt1: float, amt2: float) -> float:
    if amt1 == amt2:
        return 1.0
    diff = abs(amt1 - amt2)
    max_amt = max(abs(amt1), abs(amt2))
    if max_amt == 0:
        return 0.0
    return max(0.0, 1.0 - (diff / max_amt))

def calculate_date_similarity(date1: str, date2: str) -> float:
    d1 = datetime.strptime(date1, "%Y-%m-%d")
    d2 = datetime.strptime(date2, "%Y-%m-%d")
    diff_days = abs((d1 - d2).days)
    if diff_days == 0:
        return 1.0
    return max(0.0, 1.0 - (diff_days * 0.1))

def calculate_vendor_similarity(v1: str, v2: str) -> float:
    return fuzz.token_sort_ratio(v1.lower(), v2.lower()) / 100.0

def calculate_currency_match(c1: str, c2: str) -> float:
    return 1.0 if c1 == c2 else 0.0

def calculate_match_score(tx1: NormalizedTransaction, tx2: NormalizedTransaction) -> ScoreBreakdown:
    ref_score = calculate_reference_similarity(tx1.reference, tx2.reference)
    amt_score = calculate_amount_similarity(tx1.amount, tx2.amount)
    date_score = calculate_date_similarity(tx1.date, tx2.date)
    vendor_score = calculate_vendor_similarity(tx1.entity_name, tx2.entity_name)
    curr_score = calculate_currency_match(tx1.currency, tx2.currency)
    
    total = (
        ref_score * config.REFERENCE_WEIGHT +
        amt_score * config.AMOUNT_WEIGHT +
        date_score * config.DATE_WEIGHT +
        vendor_score * config.VENDOR_WEIGHT +
        curr_score * config.CURRENCY_WEIGHT
    )
    
    return ScoreBreakdown(
        reference_score=ref_score,
        amount_score=amt_score,
        date_score=date_score,
        vendor_score=vendor_score,
        currency_score=curr_score,
        total_score=total
    )
