import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Project paths
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "finance_controller.db"

# AI Mode
AI_MODE = os.getenv("AI_MODE", "local")  # 'local' or 'openai'
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# Reconciliation thresholds
MATCHED_THRESHOLD = 0.90
LIKELY_MATCH_THRESHOLD = 0.75
MANUAL_REVIEW_THRESHOLD = 0.50

# Scoring weights
REFERENCE_WEIGHT = 0.30
AMOUNT_WEIGHT = 0.30
DATE_WEIGHT = 0.15
VENDOR_WEIGHT = 0.15
CURRENCY_WEIGHT = 0.10

# Data generation
RANDOM_SEED = 42
NUM_BASE_TRANSACTIONS = 35  # Will generate ~105 records across 3 sources

# Database
DATABASE_URL = f"sqlite:///{DB_PATH}"
