import pytest
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models.schemas import NormalizedTransaction, Source


@pytest.fixture
def sample_bank_transaction():
    return NormalizedTransaction(
        id="BNK-TXN-001",
        source=Source.BANK,
        date="2026-08-15",
        amount=12500.00,
        currency="INR",
        entity_name="Acme Supplies Pvt Ltd",
        reference="INV-1001",
        original_data={}
    )


@pytest.fixture
def sample_ledger_transaction():
    return NormalizedTransaction(
        id="LED-001",
        source=Source.LEDGER,
        date="2026-08-15",
        amount=12500.00,
        currency="INR",
        entity_name="ACME SUPPLIES PVT LTD",
        reference="INV-1001",
        original_data={}
    )


@pytest.fixture
def mismatched_transaction():
    return NormalizedTransaction(
        id="PAY-001",
        source=Source.PAYMENT,
        date="2026-08-18",
        amount=12625.00,
        currency="INR",
        entity_name="Acme Supply",
        reference="INV-1001-A",
        original_data={}
    )


@pytest.fixture
def different_currency_transaction():
    return NormalizedTransaction(
        id="PAY-002",
        source=Source.PAYMENT,
        date="2026-08-15",
        amount=12500.00,
        currency="USD",
        entity_name="Acme Supplies Pvt Ltd",
        reference="INV-1001",
        original_data={}
    )
