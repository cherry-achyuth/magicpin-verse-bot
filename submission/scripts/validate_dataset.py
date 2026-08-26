# Script to validate all dataset files against submission Pydantic models.

from __future__ import annotations

import json
from pathlib import Path
import sys

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from submission.models import (
    CategoryContext,
    CustomerContext,
    MerchantContext,
    TriggerContext,
)


def validate_all():
    base_dir = Path(__file__).parent.parent.parent / "dataset" / "expanded"
    counts = {"categories": 0, "merchants": 0, "customers": 0, "triggers": 0}
    errors = 0

    for cat_file in (base_dir / "categories").glob("*.json"):
        data = json.loads(cat_file.read_text())
        try:
            CategoryContext.model_validate(data)
            counts["categories"] += 1
        except Exception as err:
            print(f"Category validation error in {cat_file.name}: {err}")
            errors += 1

    for mer_file in (base_dir / "merchants").glob("*.json"):
        data = json.loads(mer_file.read_text())
        try:
            MerchantContext.model_validate(data)
            counts["merchants"] += 1
        except Exception as err:
            print(f"Merchant validation error in {mer_file.name}: {err}")
            errors += 1

    for cust_file in (base_dir / "customers").glob("*.json"):
        data = json.loads(cust_file.read_text())
        try:
            CustomerContext.model_validate(data)
            counts["customers"] += 1
        except Exception as err:
            print(f"Customer validation error in {cust_file.name}: {err}")
            errors += 1

    for trg_file in (base_dir / "triggers").glob("*.json"):
        data = json.loads(trg_file.read_text())
        try:
            TriggerContext.model_validate(data)
            counts["triggers"] += 1
        except Exception as err:
            print(f"Trigger validation error in {trg_file.name}: {err}")
            errors += 1

    print(f"Validation complete: {counts}, total errors = {errors}")
    if errors > 0:
        sys.exit(1)


if __name__ == "__main__":
    validate_all()
