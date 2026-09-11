#!/usr/bin/env python3
"""
Aggregate metrics from ledger into ROI dashboard.

This script reads the ledger file, processes all receipts with pricing and baselines,
and generates a dashboard report showing usage statistics and ROI.
"""

import os
import sys
import json
import traceback
from pathlib import Path
from datetime import datetime
from collections import defaultdict, Counter

# Add metrics/lib to path so we can import receipts utilities
sys.path.insert(0, str(Path(__file__).parent / 'lib'))

from receipts import compute_cost, compute_time_saved, compute_roi


def main():
    """Main entry point"""
    # Load configurations
    try:
        config = load_config("metrics/config.json")
        rates = load_rates("metrics/rates.json")
        baselines = load_baselines("metrics/baselines.json")
        receipts = read_ledger("metrics/ledger.jsonl")
        
        # Aggregate metrics
        aggregate_data = aggregate_metrics(receipts, baselines, rates)
        
        # Generate dashboard
        dashboard = generate_dashboard(aggregate_data)
        
        print(dashboard)
        
        # Write to output file
        with open("logs/dashboard.txt", "w") as f:
            f.write(dashboard)
        
        return 0
        
    except Exception as e:
        print(f"Error during aggregation: {e}", file=sys.stderr)
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())