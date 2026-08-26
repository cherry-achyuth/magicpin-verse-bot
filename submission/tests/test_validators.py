# Unit tests for message validators.

from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from submission.validators import (
    check_anti_repetition,
    check_no_fabrication,
    check_no_raw_urls,
    check_single_cta,
    validate_message,
)


def test_validator_rules():
    # 1. URL check
    ok, err = check_no_raw_urls("Check out https://magicpin.in/deals for 20% off")
    assert ok is False
    assert "https://magicpin.in/deals" in err

    # 2. Multiple CTAs check
    ok, err = check_single_cta("Would you like to try this? Or would you prefer next week?")
    assert ok is False
    assert "Contains 2 questions" in err

    # 3. Anti-repetition check
    ok, err = check_anti_repetition(
        "Hi Dr. Meera, your CTR dropped by 15% this month.",
        ["Hi Dr. Meera, your CTR dropped by 15% this month."],
    )
    assert ok is False
    assert "Exact match" in err

    # 4. Fabrication check (38% not in context)
    dummy_cat = {"slug": "dentists"}
    dummy_mer = {"identity": {"name": "Smile Clinic"}, "performance": {"views": 100}}
    dummy_trg = {"kind": "perf_dip", "payload": {"views_dip_pct": 15}}

    ok, err = check_no_fabrication(
        "Your views dropped by 38% this week.",
        dummy_cat,
        dummy_mer,
        dummy_trg,
    )
    assert ok is False
    assert "38%" in err

    # 5. Valid message check
    valid_ok, valid_reasons = validate_message(
        "Hi Dr. Meera, your views dropped by 15% this week. Would you like us to refresh your active offer?",
        "binary_yes_no",
        dummy_cat,
        dummy_mer,
        dummy_trg,
    )
    assert valid_ok is True
    assert len(valid_reasons) == 0

    print("All validator unit tests passed successfully!")


if __name__ == "__main__":
    test_validator_rules()
