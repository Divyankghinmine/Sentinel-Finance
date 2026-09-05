from typing import List
from app.models.schemas import BankTransaction, LedgerEntry, PaymentRecord, NormalizedTransaction, Source

def normalize_bank(transactions: List[BankTransaction]) -> List[NormalizedTransaction]:
    return [
        NormalizedTransaction(
            id=t.bank_transaction_id,
            source=Source.BANK,
            date=t.transaction_date,
            amount=t.amount,
            currency=t.currency.upper(),
            entity_name=t.description.strip().upper(),
            reference=t.reference.strip().upper(),
            original_data=t.model_dump()
        ) for t in transactions
    ]

def normalize_ledger(entries: List[LedgerEntry]) -> List[NormalizedTransaction]:
    return [
        NormalizedTransaction(
            id=t.ledger_id,
            source=Source.LEDGER,
            date=t.posting_date,
            amount=t.amount,
            currency=t.currency.upper(),
            entity_name=t.vendor.strip().upper(),
            reference=t.invoice_number.strip().upper(),
            original_data=t.model_dump()
        ) for t in entries
    ]

def normalize_payment(records: List[PaymentRecord]) -> List[NormalizedTransaction]:
    return [
        NormalizedTransaction(
            id=t.payment_id,
            source=Source.PAYMENT,
            date=t.settlement_date,
            amount=t.amount,
            currency=t.currency.upper(),
            entity_name=t.merchant.strip().upper(),
            reference=t.payment_reference.strip().upper(),
            original_data=t.model_dump()
        ) for t in records
    ]

def normalize_all(bank: List[BankTransaction], ledger: List[LedgerEntry], payments: List[PaymentRecord]) -> List[NormalizedTransaction]:
    return normalize_bank(bank) + normalize_ledger(ledger) + normalize_payment(payments)
