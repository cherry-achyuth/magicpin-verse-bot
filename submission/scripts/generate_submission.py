# Generates the 30 required test pair messages for final submission.
# Reads canonical test pairs from dataset/expanded/test_pairs.json,
# resolves all required context objects, runs the composer with live validation,
# and outputs submission/submission.jsonl.

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Add project root to python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from submission.composer import Composer
from submission.validators import validate_message


def generate_submission():
    base_dir = Path(__file__).parent.parent.parent
    dataset_dir = base_dir / "dataset" / "expanded"
    pairs_file = dataset_dir / "test_pairs.json"
    output_file = base_dir / "submission" / "submission.jsonl"

    if not pairs_file.exists():
        print(f"Error: {pairs_file} does not exist. Run generate_dataset.py first.")
        sys.exit(1)

    data = json.loads(pairs_file.read_text(encoding="utf-8"))
    pairs = data.get("pairs", [])
    print(f"Loaded {len(pairs)} test pairs from {pairs_file}")

    # Load existing valid results if any to resume
    existing_map = {}
    if output_file.exists():
        for line in output_file.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
                tid = row.get("test_id")
                rat = row.get("rationale", "")
                # Only preserve if it was a real generated message, not a fallback
                if tid and "fallback" not in rat.lower():
                    existing_map[tid] = row
            except Exception:
                pass

    print(f"Found {len(existing_map)} already-completed high-quality rows in {output_file}")

    composer = Composer()
    results = []

    for idx, pair in enumerate(pairs, start=1):
        test_id = pair["test_id"]
        trg_id = pair["trigger_id"]
        mer_id = pair["merchant_id"]
        cust_id = pair.get("customer_id")

        if test_id in existing_map:
            print(f"[{idx:02d}/{len(pairs)}] Skipping {test_id} (already completed).")
            results.append(existing_map[test_id])
            continue

        print(f"[{idx:02d}/{len(pairs)}] Composing for {test_id} (trigger: {trg_id}, merchant: {mer_id})...")

        # Load trigger context
        trg_file = dataset_dir / "triggers" / f"{trg_id}.json"
        if not trg_file.exists():
            print(f"Warning: Missing trigger file {trg_file}")
            continue
        trg_payload = json.loads(trg_file.read_text(encoding="utf-8"))

        # Load merchant context
        mer_file = dataset_dir / "merchants" / f"{mer_id}.json"
        if not mer_file.exists():
            print(f"Warning: Missing merchant file {mer_file}")
            continue
        mer_payload = json.loads(mer_file.read_text(encoding="utf-8"))

        # Load category context
        cat_slug = mer_payload.get("category_slug")
        cat_file = dataset_dir / "categories" / f"{cat_slug}.json"
        if not cat_file.exists():
            print(f"Warning: Missing category file {cat_file}")
            continue
        cat_payload = json.loads(cat_file.read_text(encoding="utf-8"))

        # Load optional customer context
        cust_payload = None
        if cust_id:
            cust_file = dataset_dir / "customers" / f"{cust_id}.json"
            if cust_file.exists():
                cust_payload = json.loads(cust_file.read_text(encoding="utf-8"))

        # Compose message
        composed = composer.compose(
            category=cat_payload,
            merchant=mer_payload,
            trigger=trg_payload,
            customer=cust_payload,
        )

        suppression_key = trg_payload.get("suppression_key", f"{trg_id}:{mer_id}")

        result_row = {
            "test_id": test_id,
            "body": composed["body"],
            "cta": composed["cta"],
            "send_as": composed["send_as"],
            "suppression_key": suppression_key,
            "rationale": composed["rationale"],
        }
        results.append(result_row)

        # Write progress incrementally after each item
        with open(output_file, "w", encoding="utf-8") as f:
            for row in results:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

        time.sleep(1.5)

    print(f"\nSuccessfully wrote {len(results)} rows to {output_file}")


if __name__ == "__main__":
    generate_submission()
