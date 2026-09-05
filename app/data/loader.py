import csv
from typing import List, Dict, Any, Tuple
from app.models.schemas import BankTransaction, LedgerEntry, PaymentRecord
from app.core.config import DATA_DIR

def load_bank_transactions(path: str) -> List[BankTransaction]:
    results = []
    with open(path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            results.append(BankTransaction(
                bank_transaction_id=row["bank_transaction_id"],
                transaction_date=row["transaction_date"],
                amount=float(row["amount"]),
                currency=row["currency"],
                description=row["description"],
                reference=row["reference"]
            ))
    return results

def load_ledger_entries(path: str) -> List[LedgerEntry]:
    results = []
    with open(path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            results.append(LedgerEntry(
                ledger_id=row["ledger_id"],
                posting_date=row["posting_date"],
                amount=float(row["amount"]),
                currency=row["currency"],
                vendor=row["vendor"],
                invoice_number=row["invoice_number"],
                account=row["account"]
            ))
    return results

def load_payment_records(path: str) -> List[PaymentRecord]:
    results = []
    with open(path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            results.append(PaymentRecord(
                payment_id=row["payment_id"],
                settlement_date=row["settlement_date"],
                amount=float(row["amount"]),
                currency=row["currency"],
                merchant=row["merchant"],
                payment_reference=row["payment_reference"],
                status=row["status"]
            ))
    return results

def load_ground_truth(path: str) -> List[Dict[str, Any]]:
    results = []
    with open(path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            results.append(dict(row))
    return results

def load_all_data() -> Tuple[List[BankTransaction], List[LedgerEntry], List[PaymentRecord]]:
    b = load_bank_transactions(DATA_DIR / "bank.csv")
    l = load_ledger_entries(DATA_DIR / "ledger.csv")
    p = load_payment_records(DATA_DIR / "payments.csv")
    return b, l, p
