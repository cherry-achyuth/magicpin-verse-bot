# Detailed sample output inspector and validator tester.

from __future__ import annotations

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from submission.composer import Composer
from submission.validators import (
    check_cta_position,
    check_no_fabrication,
    check_no_raw_urls,
    check_single_cta,
    validate_message,
)


def inspect_samples():
    composer = Composer()

    # Scenario 1: Dr. Meera Research Digest
    cat_dentists = json.loads(Path("dataset/expanded/categories/dentists.json").read_text())
    mer_meera = json.loads(Path("dataset/expanded/merchants/m_001_drmeera_dentist_delhi.json").read_text())
    trg_digest = json.loads(Path("dataset/expanded/triggers/trg_001_research_digest_dentists.json").read_text())

    out1 = composer.compose(cat_dentists, mer_meera, trg_digest)

    print("==================================================")
    print("SCENARIO 1: Dr. Meera (Research Digest - Dentists)")
    print("==================================================")
    print(f"Send As: {out1.get('send_as')}")
    print(f"CTA Type: {out1.get('cta')}")
    print(f"Rationale: {out1.get('rationale')}")
    print("\nFULL MESSAGE BODY:")
    print(out1.get("body"))
    print("\nVALIDATOR CHECKS:")
    print(f"- No Raw URLs: {check_no_raw_urls(out1['body'])[0]}")
    print(f"- Single CTA: {check_single_cta(out1['body'])[0]}")
    print(f"- CTA at End: {check_cta_position(out1['body'])[0]}")
    print(f"- Grounded / No Fabrication: {check_no_fabrication(out1['body'], cat_dentists, mer_meera, trg_digest)[0]}")
    print(f"- Overall Validated: {validate_message(out1['body'], out1['cta'], cat_dentists, mer_meera, trg_digest)[0]}")

    # Scenario 2: Priya Recall Due (Customer-Facing)
    cust_priya = json.loads(Path("dataset/expanded/customers/c_001_priya_for_m001.json").read_text())
    trg_recall = json.loads(Path("dataset/expanded/triggers/trg_003_recall_due_priya.json").read_text())

    out2 = composer.compose(cat_dentists, mer_meera, trg_recall, customer=cust_priya)

    print("\n==================================================")
    print("SCENARIO 2: Priya Recall Due (Customer-Facing)")
    print("==================================================")
    print(f"Send As: {out2.get('send_as')}")
    print(f"CTA Type: {out2.get('cta')}")
    print(f"Rationale: {out2.get('rationale')}")
    print("\nFULL MESSAGE BODY:")
    print(out2.get("body"))
    print("\nVALIDATOR CHECKS:")
    print(f"- No Raw URLs: {check_no_raw_urls(out2['body'])[0]}")
    print(f"- Single CTA: {check_single_cta(out2['body'])[0]}")
    print(f"- CTA at End: {check_cta_position(out2['body'])[0]}")
    print(f"- Grounded / No Fabrication: {check_no_fabrication(out2['body'], cat_dentists, mer_meera, trg_recall, cust_priya)[0]}")
    print(f"- Overall Validated: {validate_message(out2['body'], out2['cta'], cat_dentists, mer_meera, trg_recall, cust_priya)[0]}")

    # Scenario 3: Performance Dip
    mer_salon = json.loads(Path("dataset/expanded/merchants/m_022_renu_salon_ahmedabad.json").read_text())
    cat_salons = json.loads(Path("dataset/expanded/categories/salons.json").read_text())
    trg_dip = json.loads(Path("dataset/expanded/triggers/trg_033_perf_dip_m_022_renu_salon_ahm.json").read_text())

    out3 = composer.compose(cat_salons, mer_salon, trg_dip)

    print("\n==================================================")
    print("SCENARIO 3: Performance Dip (Renu Salon)")
    print("==================================================")
    print(f"Send As: {out3.get('send_as')}")
    print(f"CTA Type: {out3.get('cta')}")
    print(f"Rationale: {out3.get('rationale')}")
    print("\nFULL MESSAGE BODY:")
    print(out3.get("body"))
    print("\nVALIDATOR CHECKS:")
    print(f"- No Raw URLs: {check_no_raw_urls(out3['body'])[0]}")
    print(f"- Single CTA: {check_single_cta(out3['body'])[0]}")
    print(f"- CTA at End: {check_cta_position(out3['body'])[0]}")
    print(f"- Grounded / No Fabrication: {check_no_fabrication(out3['body'], cat_salons, mer_salon, trg_dip)[0]}")
    print(f"- Overall Validated: {validate_message(out3['body'], out3['cta'], cat_salons, mer_salon, trg_dip)[0]}")


if __name__ == "__main__":
    inspect_samples()
