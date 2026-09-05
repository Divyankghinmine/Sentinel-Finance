"""FastAPI routes for the AI Finance Controller API."""
from fastapi import APIRouter, HTTPException
from typing import Optional, List
from app.agent.controller import FinanceController
from app.data.generator import generate_all
from app.models.schemas import ReconciliationRun, ReconciliationResult, ReconciliationMetrics, MatchStatus

router = APIRouter()

# Module-level state for latest run
_latest_run: Optional[ReconciliationRun] = None


@router.post("/generate-data")
def generate_data():
    """Generate synthetic demo data."""
    try:
        paths = generate_all()
        return {"message": "Demo data generated successfully", "success": True, "files": [str(p) for p in paths]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating data: {str(e)}")


@router.post("/reconcile")
def reconcile():
    """Run the full reconciliation pipeline."""
    global _latest_run
    try:
        controller = FinanceController()
        _latest_run = controller.run_pipeline()
        return _latest_run.model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Reconciliation failed: {str(e)}")


@router.get("/transactions")
def get_transactions():
    """Get all reconciliation results from the latest run."""
    if _latest_run is None:
        raise HTTPException(status_code=404, detail="No reconciliation run found. POST /reconcile first.")
    return [r.model_dump() for r in _latest_run.results]


@router.get("/exceptions")
def get_exceptions():
    """Get only exception records from the latest run."""
    if _latest_run is None:
        raise HTTPException(status_code=404, detail="No reconciliation run found. POST /reconcile first.")
    exceptions = [r for r in _latest_run.results if r.status != MatchStatus.MATCHED]
    return [r.model_dump() for r in exceptions]


@router.get("/metrics")
def get_metrics():
    """Get reconciliation metrics from the latest run."""
    if _latest_run is None:
        raise HTTPException(status_code=404, detail="No reconciliation run found. POST /reconcile first.")
    return _latest_run.metrics.model_dump()


@router.get("/transaction/{transaction_id}")
def get_transaction(transaction_id: str):
    """Get a specific transaction result."""
    if _latest_run is None:
        raise HTTPException(status_code=404, detail="No reconciliation run found. POST /reconcile first.")
    result = next((r for r in _latest_run.results if r.source_id == transaction_id), None)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Transaction {transaction_id} not found.")
    return result.model_dump()
