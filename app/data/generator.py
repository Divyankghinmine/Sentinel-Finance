import csv
import random
import os
from datetime import datetime, timedelta
from app.core.config import DATA_DIR, RANDOM_SEED, NUM_BASE_TRANSACTIONS

random.seed(RANDOM_SEED)

def generate_base_transactions():
    companies = [
        "Acme Supplies", "TCS Technologies", "Wipro Solutions", 
        "Infosys Ltd", "Reliance Retail", "HDFC Bank", 
        "Amazon India", "Flipkart", "Zomato", "Swiggy"
    ]
    currencies = ["INR", "INR", "INR", "INR", "USD"]
    
    base_txns = []
    base_date = datetime(2026, 8, 1)
    
    for i in range(1, NUM_BASE_TRANSACTIONS + 1):
        txn_date = base_date + timedelta(days=random.randint(0, 60))
        amount = round(random.uniform(100.0, 10000.0), 2)
        company = random.choice(companies)
        currency = random.choice(currencies)
        
        base_txns.append({
            "base_id": i,
            "date": txn_date,
            "amount": amount,
            "company": company,
            "currency": currency,
            "inv_ref": f"INV-{1000+i}",
            "bank_ref": f"BNK-TXN-{i:03d}",
            "ledger_id": f"LED-{i:03d}",
            "payment_id": f"PAY-{i:03d}"
        })
    return base_txns

def generate_all():
    os.makedirs(DATA_DIR, exist_ok=True)
    
    base_txns = generate_base_transactions()
    
    bank_data = []
    ledger_data = []
    payment_data = []
    ground_truth = []
    
    # Track indices for discrepancies
    exact_idx = set(range(22))
    amount_miss_idx = set(range(22, 26))
    date_miss_idx = set(range(26, 29))
    dup_idx = set(range(29, 31))
    missing_idx = set(range(31, 34))
    vendor_miss_idx = set(range(31, 35)) # overlapping somewhat or just use separate
    
    for i, txn in enumerate(base_txns):
        b_amt, l_amt, p_amt = txn["amount"], txn["amount"], txn["amount"]
        b_date, l_date, p_date = txn["date"], txn["date"], txn["date"]
        b_comp, l_comp, p_comp = txn["company"], txn["company"], txn["company"]
        b_curr, l_curr, p_curr = txn["currency"], txn["currency"], txn["currency"]
        b_ref, l_ref, p_ref = txn["inv_ref"], txn["inv_ref"], txn["inv_ref"]
        
        expected_status = "MATCHED"
        
        if i in amount_miss_idx:
            l_amt += round(random.uniform(5.0, 200.0), 2)
            expected_status = "MANUAL_REVIEW"
        if i in date_miss_idx:
            b_date += timedelta(days=random.randint(2, 5))
            expected_status = "LIKELY_MATCH"
        if i in vendor_miss_idx:
            l_comp = l_comp.upper()
            p_comp = l_comp + " PVT LTD"
            expected_status = "LIKELY_MATCH"
            
        b_txn = {
            "bank_transaction_id": txn["bank_ref"],
            "transaction_date": b_date.strftime("%Y-%m-%d"),
            "amount": b_amt,
            "currency": b_curr,
            "description": b_comp,
            "reference": b_ref
        }
        l_txn = {
            "ledger_id": txn["ledger_id"],
            "posting_date": l_date.strftime("%Y-%m-%d"),
            "amount": l_amt,
            "currency": l_curr,
            "vendor": l_comp,
            "invoice_number": l_ref,
            "account": "Accounts Payable"
        }
        p_txn = {
            "payment_id": txn["payment_id"],
            "settlement_date": p_date.strftime("%Y-%m-%d"),
            "amount": p_amt,
            "currency": p_curr,
            "merchant": p_comp,
            "payment_reference": p_ref,
            "status": "COMPLETED"
        }
        
        include_bank = True
        include_ledger = True
        include_payment = True
        
        if i in missing_idx:
            if i % 2 == 0:
                include_bank = False
                expected_status = "MISSING"
            else:
                include_ledger = False
                expected_status = "MISSING"
                
        if include_bank: bank_data.append(b_txn)
        if include_ledger: ledger_data.append(l_txn)
        if include_payment: payment_data.append(p_txn)
        
        if i in dup_idx:
            dup_b = b_txn.copy()
            dup_b["bank_transaction_id"] = b_txn["bank_transaction_id"] + "-DUP"
            bank_data.append(dup_b)
            expected_status = "DUPLICATE"
            
        # Add to ground truth
        if include_bank and include_ledger:
            ground_truth.append({
                "source_id": b_txn["bank_transaction_id"],
                "source_type": "BANK",
                "expected_target_id": l_txn["ledger_id"],
                "expected_target_type": "LEDGER",
                "expected_status": expected_status
            })
            
    # Write CSVs
    bank_path = DATA_DIR / "bank.csv"
    with open(bank_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["bank_transaction_id", "transaction_date", "amount", "currency", "description", "reference"])
        writer.writeheader()
        writer.writerows(bank_data)
        
    ledger_path = DATA_DIR / "ledger.csv"
    with open(ledger_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["ledger_id", "posting_date", "amount", "currency", "vendor", "invoice_number", "account"])
        writer.writeheader()
        writer.writerows(ledger_data)
        
    payment_path = DATA_DIR / "payments.csv"
    with open(payment_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["payment_id", "settlement_date", "amount", "currency", "merchant", "payment_reference", "status"])
        writer.writeheader()
        writer.writerows(payment_data)
        
    gt_path = DATA_DIR / "ground_truth.csv"
    with open(gt_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["source_id", "source_type", "expected_target_id", "expected_target_type", "expected_status"])
        writer.writeheader()
        writer.writerows(ground_truth)
        
    return bank_path, ledger_path, payment_path, gt_path

if __name__ == "__main__":
    generate_all()
    print("Data generated successfully.")
