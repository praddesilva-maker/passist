#!/usr/bin/env python3
"""
Ingest Run Receipts into the metrics ledger.

This script reads run receipts from the inbox directory and appends them 
to the ledger.jsonl file, deduplicating on run_id.
"""

import os
import sys
import json
import traceback
from pathlib import Path
from typing import Dict, List

# Add metrics/lib to path so we can import receipts utilities
sys.path.insert(0, str(Path(__file__).parent / 'lib'))

from receipts import validate_receipt


def read_ledger(ledger_path: str) -> Dict[str, str]:
    """
    Read existing ledger entries into a set of run_ids for deduplication.
    
    Args:
        ledger_path: Path to the ledger file
        
    Returns:
        Set of run_ids already in ledger
    """
    existing_run_ids = set()
    
    if os.path.exists(ledger_path):
        try:
            with open(ledger_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        entry = json.loads(line)
                        existing_run_ids.add(entry['run_id'])
        except Exception as e:
            print(f"Warning: Could not read ledger file {ledger_path}: {e}", file=sys.stderr)
            
    return existing_run_ids


def ingest_receipts(inbox_dir: str, ledger_path: str) -> int:
    """
    Ingest all receipts from the inbox directory into the ledger.
    
    Args:
        inbox_dir: Directory containing receipt files
        ledger_path: Path to the ledger file
        
    Returns:
        Number of new entries added
    """
    if not os.path.exists(inbox_dir):
        print(f"Warning: Inbox directory {inbox_dir} does not exist", file=sys.stderr)
        return 0
        
    # Read existing run_ids for deduplication
    existing_run_ids = read_ledger(ledger_path)
    
    new_entries = 0
    
    # Find all receipt files in inbox
    receipt_files = [f for f in os.listdir(inbox_dir) 
                     if f.endswith('.json') and os.path.isfile(os.path.join(inbox_dir, f))]
    
    with open(ledger_path, 'a') as ledger_file:
        for receipt_file in receipt_files:
            receipt_path = os.path.join(inbox_dir, receipt_file)
            
            try:
                # Read the receipt
                with open(receipt_path, 'r') as f:
                    receipt_data = json.load(f)
                
                # Skip if already in ledger (deduplication)
                if receipt_data.get('run_id') in existing_run_ids:
                    continue
                    
                # Validate receipt before adding
                if not validate_receipt(receipt_data):
                    print(f"Warning: Invalid receipt in {receipt_file}, skipping", file=sys.stderr)
                    continue
                
                # Add to ledger
                ledger_file.write(json.dumps(receipt_data) + '\n')
                ledger_file.flush()  # Ensure immediate write
                new_entries += 1
                
                # Update existing_run_ids for next iterations
                existing_run_ids.add(receipt_data['run_id'])
                
            except Exception as e:
                print(f"Error processing {receipt_file}: {e}", file=sys.stderr)
                traceback.print_exc()
                continue
    
    return new_entries


def main():
    """Main entry point"""
    inbox_dir = "metrics/inbox"
    ledger_path = "metrics/ledger.jsonl"
    
    try:
        count = ingest_receipts(inbox_dir, ledger_path)
        print(f"Successfully ingested {count} new receipt(s)", file=sys.stderr)
        return 0
    except Exception as e:
        print(f"Error during ingestion: {e}", file=sys.stderr)
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())