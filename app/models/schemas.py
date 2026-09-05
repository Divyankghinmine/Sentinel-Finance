from enum import Enum
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class MatchStatus(str, Enum):
    MATCHED = "MATCHED"
    LIKELY_MATCH = "LIKELY_MATCH"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    MISMATCH = "MISMATCH"
    DUPLICATE = "DUPLICATE"
    MISSING = "MISSING"

class ExceptionType(str, Enum):
    AMOUNT_MISMATCH = "AMOUNT_MISMATCH"
    DATE_MISMATCH = "DATE_MISMATCH"
    DUPLICATE = "DUPLICATE"
    MISSING_TRANSACTION = "MISSING_TRANSACTION"
    CURRENCY_MISMATCH = "CURRENCY_MISMATCH"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    MULTIPLE_CANDIDATES = "MULTIPLE_CANDIDATES"
    VENDOR_MISMATCH = "VENDOR_MISMATCH"

class Source(str, Enum):
    BANK = "BANK"
    LEDGER = "LEDGER"
    PAYMENT = "PAYMENT"

class BankTransaction(BaseModel):
    bank_transaction_id: str
    transaction_date: str
    amount: float
    currency: str
    description: str
    reference: str

class LedgerEntry(BaseModel):
    ledger_id: str
    posting_date: str
    amount: float
    currency: str
    vendor: str
    invoice_number: str
    account: str

class PaymentRecord(BaseModel):
    payment_id: str
    settlement_date: str
    amount: float
    currency: str
    merchant: str
    payment_reference: str
    status: str

class NormalizedTransaction(BaseModel):
    id: str
    source: Source
    date: str
    amount: float
    currency: str
    entity_name: str
    reference: str
    original_data: dict

class ScoreBreakdown(BaseModel):
    reference_score: float
    amount_score: float
    date_score: float
    vendor_score: float
    currency_score: float
    total_score: float

class ReconciliationResult(BaseModel):
    source_id: str
    source_type: Source
    target_id: Optional[str] = None
    target_type: Optional[Source] = None
    status: MatchStatus
    score: float
    score_breakdown: Optional[ScoreBreakdown] = None
    amount_difference: float = 0.0
    date_difference: int = 0
    exception_type: Optional[ExceptionType] = None
    reason: str = ""
    recommended_action: str = ""
    confidence: float = 0.0

class ReconciliationMetrics(BaseModel):
    total_records: int
    matched: int
    likely_matches: int
    manual_review: int
    mismatches: int
    duplicates: int
    missing: int
    match_rate: float
    average_confidence: float
    total_amount_discrepancy: float
    processing_time: float
    records_per_second: float
    accuracy: Optional[float] = None

class ReconciliationRun(BaseModel):
    run_id: str
    timestamp: str
    metrics: ReconciliationMetrics
    results: list[ReconciliationResult]
