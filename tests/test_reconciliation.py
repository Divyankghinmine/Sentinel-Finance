"""Integration tests for the full reconciliation pipeline."""
import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models.schemas import (
    BankTransaction, LedgerEntry, PaymentRecord,
    MatchStatus, Source
)
from app.reconciliation.engine import ReconciliationEngine


@pytest.fixture
def engine():
    return ReconciliationEngine()


@pytest.fixture
def sample_bank_records():
    return [
        BankTransaction(
            bank_transaction_id="BNK-001",
            transaction_date="2026-08-15",
            amount=12500.00,
            currency="INR",
            description="Acme Supplies Pvt Ltd",
            reference="BNK-001"
        ),
        BankTransaction(
            bank_transaction_id="BNK-002",
            transaction_date="2026-08-20",
            amount=8750.00,
            currency="INR",
            description="TCS Technologies",
            reference="BNK-002"
        ),
    ]


@pytest.fixture
def sample_ledger_records():
    return [
        LedgerEntry(
            ledger_id="LED-001",
            posting_date="2026-08-15",
            amount=12500.00,
            currency="INR",
            vendor="Acme Supplies Pvt Ltd",
            invoice_number="INV-1001",
            account="Accounts Payable"
        ),
        LedgerEntry(
            ledger_id="LED-002",
            posting_date="2026-08-20",
            amount=8750.00,
            currency="INR",
            vendor="TCS Technologies",
            invoice_number="INV-1002",
            account="Accounts Payable"
        ),
    ]


@pytest.fixture
def sample_payment_records():
    return [
        PaymentRecord(
            payment_id="PAY-001",
            settlement_date="2026-08-15",
            amount=12500.00,
            currency="INR",
            merchant="Acme Supplies Pvt Ltd",
            payment_reference="INV-1001",
            status="COMPLETED"
        ),
    ]


def test_full_reconciliation_pipeline(engine, sample_bank_records, sample_ledger_records, sample_payment_records):
    """Test that the full pipeline runs and produces results."""
    run = engine.run(sample_bank_records, sample_ledger_records, sample_payment_records)

    assert run is not None
    assert run.run_id is not None
    assert run.timestamp is not None
    assert len(run.results) > 0
    assert run.metrics.total_records > 0


def test_reconciliation_metrics(engine, sample_bank_records, sample_ledger_records, sample_payment_records):
    """Test that reconciliation metrics are calculated correctly."""
    run = engine.run(sample_bank_records, sample_ledger_records, sample_payment_records)
    metrics = run.metrics

    assert metrics.total_records > 0
    assert metrics.matched >= 0
    assert metrics.match_rate >= 0
    assert metrics.processing_time > 0
    assert metrics.records_per_second > 0
    # Total should add up
    assert metrics.matched + metrics.likely_matches + metrics.manual_review + metrics.mismatches + metrics.duplicates + metrics.missing == metrics.total_records


def test_exact_match_in_pipeline(engine):
    """Test that identical records produce exact matches."""
    bank = [BankTransaction(
        bank_transaction_id="BNK-100",
        transaction_date="2026-08-15",
        amount=5000.00,
        currency="INR",
        description="Test Vendor",
        reference="INV-100"
    )]
    ledger = [LedgerEntry(
        ledger_id="LED-100",
        posting_date="2026-08-15",
        amount=5000.00,
        currency="INR",
        vendor="Test Vendor",
        invoice_number="INV-100",
        account="AP"
    )]

    run = engine.run(bank, ledger, [])
    matched = [r for r in run.results if r.status == MatchStatus.MATCHED]
    assert len(matched) >= 1


def test_missing_detection_in_pipeline(engine):
    """Test that missing transactions are detected."""
    bank = [BankTransaction(
        bank_transaction_id="BNK-200",
        transaction_date="2026-08-15",
        amount=5000.00,
        currency="INR",
        description="Lonely Transaction",
        reference="REF-LONELY"
    )]

    run = engine.run(bank, [], [])
    missing = [r for r in run.results if r.status == MatchStatus.MISSING]
    assert len(missing) >= 1


def test_ground_truth_evaluation(engine, sample_bank_records, sample_ledger_records):
    """Test that ground truth accuracy evaluation works."""
    ground_truth = [
        {"source_id": "BNK-001", "source_type": "BANK", "expected_target_id": "LED-001", "expected_target_type": "LEDGER", "expected_status": "MATCHED"}
    ]
    run = engine.run(sample_bank_records, sample_ledger_records, [], ground_truth=ground_truth)
    assert run.metrics.accuracy is not None
    assert run.metrics.accuracy >= 0.0
