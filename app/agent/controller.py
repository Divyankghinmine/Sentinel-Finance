"""AI Finance Controller - Main pipeline orchestrator."""
import sqlite3
import json
import os
import csv
from typing import Optional, List
from datetime import datetime

from app.models.schemas import ReconciliationRun, ReconciliationResult, MatchStatus
from app.data.loader import load_all_data, load_ground_truth
from app.data.generator import generate_all
from app.reconciliation.engine import ReconciliationEngine
from app.agent.explainer import FinanceExplainer
from app.core.config import DB_PATH, DATA_DIR
from app.core.logging import get_logger

logger = get_logger(__name__)


class FinanceController:
    """AI Finance Controller agent that runs the full reconciliation pipeline."""

    def __init__(self):
        self.engine = ReconciliationEngine()
        self.explainer = FinanceExplainer()
        self._init_db()

    def _init_db(self):
        """Initialize SQLite database for persistence."""
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        conn = sqlite3.connect(str(DB_PATH))
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS runs (
            run_id TEXT PRIMARY KEY,
            timestamp TEXT NOT NULL,
            metrics_json TEXT NOT NULL
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            source_id TEXT NOT NULL,
            source_type TEXT,
            target_id TEXT,
            target_type TEXT,
            status TEXT NOT NULL,
            score REAL,
            amount_difference REAL,
            date_difference INTEGER,
            exception_type TEXT,
            reason TEXT,
            recommended_action TEXT,
            confidence REAL,
            FOREIGN KEY (run_id) REFERENCES runs(run_id)
        )''')
        conn.commit()
        conn.close()

    def run_pipeline(self) -> ReconciliationRun:
        """Execute the full 7-step reconciliation pipeline."""
        logger.info("="*60)
        logger.info("STEP 1/7: INGEST - Loading financial data...")
        logger.info("="*60)

        # Ensure data exists
        bank_path = DATA_DIR / "bank.csv"
        if not bank_path.exists():
            logger.info("No data found. Generating synthetic demo data...")
            generate_all()

        bank, ledger, payments = load_all_data()
        logger.info(f"Loaded: {len(bank)} bank, {len(ledger)} ledger, {len(payments)} payment records")

        # Load ground truth if available
        gt_path = DATA_DIR / "ground_truth.csv"
        ground_truth = None
        if gt_path.exists():
            ground_truth = load_ground_truth(str(gt_path))
            logger.info(f"Loaded {len(ground_truth)} ground truth records for evaluation")

        logger.info("STEP 2/7: NORMALIZE - Standardizing data formats...")
        logger.info("STEP 3/7: RECONCILE - Running matching engine...")
        logger.info("STEP 4/7: VALIDATE - Checking for exceptions...")
        logger.info("STEP 5/7: CLASSIFY - Assigning match statuses...")

        # Run reconciliation engine (handles steps 2-5 internally)
        run = self.engine.run(bank, ledger, payments, ground_truth=ground_truth)

        logger.info("STEP 6/7: EXPLAIN - Generating explanations...")
        # Enhance explanations using explainer
        summary = self.explainer.generate_summary(run.metrics, run.results)
        logger.info(f"Summary: {summary}")

        logger.info("STEP 7/7: REPORT - Saving results...")
        self.save_results(run)
        self._save_exceptions_csv(run)

        logger.info("="*60)
        logger.info(f"Pipeline complete: {run.metrics.matched}/{run.metrics.total_records} matched ({run.metrics.match_rate}%)")
        logger.info("="*60)

        return run

    def save_results(self, run: ReconciliationRun) -> None:
        """Save reconciliation results to SQLite."""
        try:
            conn = sqlite3.connect(str(DB_PATH))
            c = conn.cursor()
            c.execute(
                "INSERT OR REPLACE INTO runs VALUES (?, ?, ?)",
                (run.run_id, run.timestamp, json.dumps(run.metrics.model_dump()))
            )
            for res in run.results:
                c.execute(
                    "INSERT INTO results (run_id, source_id, source_type, target_id, target_type, status, score, amount_difference, date_difference, exception_type, reason, recommended_action, confidence) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        run.run_id, res.source_id,
                        res.source_type.value if res.source_type else None,
                        res.target_id,
                        res.target_type.value if res.target_type else None,
                        res.status.value, res.score,
                        res.amount_difference, res.date_difference,
                        res.exception_type.value if res.exception_type else None,
                        res.reason, res.recommended_action, res.confidence
                    )
                )
            conn.commit()
            conn.close()
            logger.info(f"Saved {len(run.results)} results to database")
        except Exception as e:
            logger.error(f"Error saving to database: {e}")

    def _save_exceptions_csv(self, run: ReconciliationRun) -> None:
        """Save exceptions to CSV for audit trail."""
        exceptions = [r for r in run.results if r.status not in (MatchStatus.MATCHED,)]
        if not exceptions:
            return

        exceptions_path = DATA_DIR / "exceptions.csv"
        fieldnames = [
            "transaction_id", "exception_type", "source", "candidate_target",
            "match_score", "amount_difference", "date_difference",
            "confidence", "reason", "recommended_action"
        ]
        with open(exceptions_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in exceptions:
                writer.writerow({
                    "transaction_id": r.source_id,
                    "exception_type": r.exception_type.value if r.exception_type else r.status.value,
                    "source": r.source_type.value if r.source_type else "",
                    "candidate_target": r.target_id or "",
                    "match_score": r.score,
                    "amount_difference": r.amount_difference,
                    "date_difference": r.date_difference,
                    "confidence": r.confidence,
                    "reason": r.reason,
                    "recommended_action": r.recommended_action
                })
        logger.info(f"Saved {len(exceptions)} exceptions to {exceptions_path}")

    def get_latest_run(self) -> Optional[ReconciliationRun]:
        """Load the latest reconciliation run from the database."""
        try:
            conn = sqlite3.connect(str(DB_PATH))
            c = conn.cursor()
            c.execute("SELECT run_id, timestamp, metrics_json FROM runs ORDER BY timestamp DESC LIMIT 1")
            row = c.fetchone()
            if not row:
                conn.close()
                return None

            run_id, timestamp, metrics_json = row
            conn.close()
            return None  # Full reconstruction would require serializing results; use run_pipeline for fresh data
        except Exception:
            return None
