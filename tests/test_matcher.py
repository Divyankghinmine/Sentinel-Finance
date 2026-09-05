"""Tests for the matching engine."""
import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models.schemas import NormalizedTransaction, Source
from app.reconciliation.matcher import (
    find_exact_matches,
    find_fuzzy_matches,
    detect_duplicates,
    find_missing
)
from app.core.config import MATCHED_THRESHOLD


def test_exact_match_found(sample_bank_transaction, sample_ledger_transaction):
    """Test that exact matches are found correctly."""
    matches = find_exact_matches(
        [sample_bank_transaction],
        [sample_ledger_transaction]
    )
    assert len(matches) >= 1
    src, tgt, score = matches[0]
    assert src.id == "BNK-TXN-001"
    assert tgt.id == "LED-001"
    assert score.total_score >= MATCHED_THRESHOLD


def test_fuzzy_match_found(sample_bank_transaction, mismatched_transaction):
    """Test that fuzzy matches are found for similar transactions."""
    matches = find_fuzzy_matches(
        [sample_bank_transaction],
        [mismatched_transaction],
        threshold=0.3
    )
    assert len(matches) == 1
    src, tgt, score = matches[0]
    assert src.id == "BNK-TXN-001"
    assert score.total_score > 0.3


def test_no_match_found(sample_bank_transaction):
    """Test empty target list yields no matches."""
    matches = find_exact_matches([sample_bank_transaction], [])
    assert len(matches) == 0


def test_duplicate_detection(sample_bank_transaction):
    """Test that duplicate transactions are detected."""
    # Create a duplicate with same amount, date, currency
    dup = NormalizedTransaction(
        id="BNK-TXN-001-DUP",
        source=Source.BANK,
        date="2026-08-15",
        amount=12500.00,
        currency="INR",
        entity_name="Acme Supplies",
        reference="INV-1001",
        original_data={}
    )
    duplicates = detect_duplicates([sample_bank_transaction, dup])
    assert len(duplicates) >= 1
    assert len(duplicates[0]) == 2


def test_no_duplicates_when_different():
    """Test that different transactions are not flagged as duplicates."""
    tx1 = NormalizedTransaction(
        id="TX-001", source=Source.BANK, date="2026-08-15",
        amount=1000.00, currency="INR", entity_name="A",
        reference="R1", original_data={}
    )
    tx2 = NormalizedTransaction(
        id="TX-002", source=Source.BANK, date="2026-08-16",
        amount=2000.00, currency="INR", entity_name="B",
        reference="R2", original_data={}
    )
    duplicates = detect_duplicates([tx1, tx2])
    assert len(duplicates) == 0


def test_find_missing():
    """Test that unmatched transactions are identified as missing."""
    tx1 = NormalizedTransaction(
        id="TX-001", source=Source.BANK, date="2026-08-15",
        amount=1000.00, currency="INR", entity_name="A",
        reference="R1", original_data={}
    )
    tx2 = NormalizedTransaction(
        id="TX-002", source=Source.LEDGER, date="2026-08-15",
        amount=2000.00, currency="INR", entity_name="B",
        reference="R2", original_data={}
    )
    matched_ids = {"TX-001"}
    missing = find_missing([tx1, tx2], matched_ids)
    assert "TX-002" in missing
    assert "TX-001" not in missing


def test_amount_mismatch_detection(sample_bank_transaction):
    """Test that amount mismatches are reflected in scores."""
    different_amount = NormalizedTransaction(
        id="LED-099", source=Source.LEDGER, date="2026-08-15",
        amount=9999.99, currency="INR", entity_name="Acme Supplies Pvt Ltd",
        reference="INV-1001", original_data={}
    )
    matches = find_fuzzy_matches(
        [sample_bank_transaction], [different_amount], threshold=0.0
    )
    assert len(matches) == 1
    _, _, score = matches[0]
    assert score.amount_score < 0.9  # Amount mismatch should lower score


def test_date_mismatch_in_score(sample_bank_transaction):
    """Test that date mismatches are reflected in scores."""
    diff_date = NormalizedTransaction(
        id="LED-099", source=Source.LEDGER, date="2027-01-01",
        amount=12500.00, currency="INR", entity_name="Acme Supplies Pvt Ltd",
        reference="INV-1001", original_data={}
    )
    matches = find_fuzzy_matches(
        [sample_bank_transaction], [diff_date], threshold=0.0
    )
    assert len(matches) == 1
    _, _, score = matches[0]
    assert score.date_score < 0.5  # Large date difference
