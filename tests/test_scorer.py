"""Tests for the scoring engine."""
import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.reconciliation.scorer import (
    calculate_reference_similarity,
    calculate_amount_similarity,
    calculate_date_similarity,
    calculate_vendor_similarity,
    calculate_currency_match,
    calculate_match_score
)


def test_reference_exact_match():
    score = calculate_reference_similarity("INV-1001", "INV-1001")
    assert score == 1.0


def test_reference_partial_match():
    score = calculate_reference_similarity("INV-1001", "INV-1001-A")
    assert 0.5 < score < 1.0


def test_reference_no_match():
    score = calculate_reference_similarity("INV-1001", "REF-9999")
    assert score < 0.5


def test_amount_exact_match():
    score = calculate_amount_similarity(100.0, 100.0)
    assert score == 1.0


def test_amount_close_match():
    score = calculate_amount_similarity(100.0, 101.0)
    assert 0.9 < score < 1.0


def test_amount_large_difference():
    score = calculate_amount_similarity(100.0, 200.0)
    assert score < 0.6


def test_date_same_day():
    score = calculate_date_similarity("2026-08-15", "2026-08-15")
    assert score == 1.0


def test_date_one_day_diff():
    score = calculate_date_similarity("2026-08-15", "2026-08-16")
    assert score == 0.9


def test_date_large_diff():
    score = calculate_date_similarity("2026-08-15", "2026-09-15")
    assert score == 0.0  # 31 days * 0.1 = 3.1, max(0, 1-3.1) = 0


def test_vendor_exact_match():
    score = calculate_vendor_similarity("Acme Corp", "Acme Corp")
    assert score == 1.0


def test_vendor_fuzzy_match():
    score = calculate_vendor_similarity("Acme Supplies Pvt Ltd", "ACME SUPPLIES PVT LTD")
    assert score > 0.8


def test_vendor_no_match():
    score = calculate_vendor_similarity("Acme Corp", "Global Technologies")
    assert score < 0.5


def test_currency_match():
    score = calculate_currency_match("USD", "USD")
    assert score == 1.0


def test_currency_mismatch():
    score = calculate_currency_match("USD", "EUR")
    assert score == 0.0


def test_full_score_calculation(sample_bank_transaction, sample_ledger_transaction):
    """Test full score calculation with matching transactions."""
    breakdown = calculate_match_score(sample_bank_transaction, sample_ledger_transaction)

    assert breakdown.total_score > 0.85
    assert breakdown.reference_score == 1.0
    assert breakdown.amount_score == 1.0
    assert breakdown.date_score == 1.0
    assert breakdown.vendor_score > 0.8  # Fuzzy match for casing differences
    assert breakdown.currency_score == 1.0


def test_score_with_mismatch(sample_bank_transaction, mismatched_transaction):
    """Test score with mismatched transaction shows lower score."""
    breakdown = calculate_match_score(sample_bank_transaction, mismatched_transaction)

    assert breakdown.total_score < 0.9  # Should not be a confident match
    assert breakdown.amount_score < 1.0  # Amount differs
    assert breakdown.date_score < 1.0  # Date differs
