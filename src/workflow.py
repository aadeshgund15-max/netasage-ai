import argparse
import csv
import os
from collections import Counter
from typing import Dict, List

from rule_checker import check_case


def _normalize(text: str) -> str:
    return (text or "").lower().strip()


def ai_diagnose(case: Dict[str, str]) -> Dict[str, object]:
    bag = " ".join([case.get("symptom", ""), case.get("show_outputs", "")]).lower()

    if "vlan" in bag or "trunk" in bag:
        root = "VLAN/trunk misconfiguration"
        next_cmd = "show interfaces trunk"
    elif "dhcp" in bag or "apipa" in bag:
        root = "DHCP scope or relay issue"
        next_cmd = "show ip dhcp pool"
    elif "dns" in bag:
        root = "DNS resolver or record issue"
        next_cmd = "show hosts"
    elif "acl" in bag:
        root = "ACL policy blocking traffic"
        next_cmd = "show access-lists"
    elif "nat" in bag or "translation" in bag:
        root = "NAT mapping or ACL mismatch"
        next_cmd = "show ip nat translations"
    elif "ospf" in bag or "route" in bag or "eigrp" in bag:
        root = "Routing path missing or incorrect"
        next_cmd = "show ip route"
    elif "wireless" in bag or "ssid" in bag or "wpa" in bag:
        root = "Wireless auth or VLAN mapping issue"
        next_cmd = "show wlan summary"
    else:
        root = "L3 addressing mismatch"
        next_cmd = "show ip interface brief"

    evidence = [
        f"Symptom observed: {case.get('symptom', '')}",
        f"Key show output clue: {case.get('show_outputs', '')[:160]}",
    ]

    return {
        "root_cause": root,
        "confidence": "medium",
        "evidence": evidence,
        "next_command": next_cmd,
        "fix_steps": [
            "Validate suspected fault with the next command",
            "Correct the configuration item related to root cause",
            "Re-test connectivity and service behavior",
        ],
    }


def compare_fault(expected_fault: str, ai_root_cause: str) -> bool:
    expected = _normalize(expected_fault)
    predicted = _normalize(ai_root_cause)
    if expected in predicted or predicted in expected:
        return True

    expected_tags = {
        "vlan": "vlan",
        "trunk": "vlan",
        "dhcp": "dhcp",
        "dns": "dns",
        "route": "routing",
        "ospf": "routing",
        "eigrp": "routing",
        "acl": "acl",
        "nat": "nat",
        "wireless": "wireless",
        "ssid": "wireless",
    }
    predicted_tags = expected_tags

    expected_family = next((v for k, v in expected_tags.items() if k in expected), "")
    predicted_family = next((v for k, v in predicted_tags.items() if k in predicted), "")
    return bool(expected_family and expected_family == predicted_family)


def load_reviews(path: str) -> Dict[str, Dict[str, str]]:
    reviews: Dict[str, Dict[str, str]] = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            reviews[row["case_id"]] = row
    return reviews


def run(cases_path: str, reviews_path: str, out_dir: str, dashboard_dir: str) -> None:
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(dashboard_dir, exist_ok=True)

    reviews = load_reviews(reviews_path)

    diagnoses_rows: List[Dict[str, str]] = []
    results_rows: List[Dict[str, str]] = []

    with open(cases_path, newline="", encoding="utf-8") as f:
        for case in csv.DictReader(f):
            ai = ai_diagnose(case)
            findings = check_case(case)
            case_id = case["case_id"]
            expected_fault = case["expected_fault"]
            agreement = compare_fault(expected_fault, str(ai["root_cause"]))

            review = reviews.get(case_id, {
                "review_status": "PENDING",
                "review_notes": "No reviewer decision yet",
                "final_fault": expected_fault,
            })

            diagnoses_rows.append(
                {
                    "case_id": case_id,
                    "root_cause": str(ai["root_cause"]),
                    "confidence": str(ai["confidence"]),
                    "evidence": " || ".join(ai["evidence"]),
                    "next_command": str(ai["next_command"]),
                    "fix_steps": " || ".join(ai["fix_steps"]),
                    "rule_flags": " | ".join(f["rule"] for f in findings),
                }
            )

            results_rows.append(
                {
                    "case_id": case_id,
                    "concept_tag": case["concept_tag"],
                    "severity": case["severity"],
                    "expected_fault": expected_fault,
                    "ai_root_cause": str(ai["root_cause"]),
                    "ai_expected_agreement": "yes" if agreement else "no",
                    "review_status": review.get("review_status", "PENDING"),
                    "review_notes": review.get("review_notes", ""),
                    "final_fault": review.get("final_fault", expected_fault),
                }
            )

    with open(os.path.join(out_dir, "ai_diagnoses.csv"), "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "case_id",
                "root_cause",
                "confidence",
                "evidence",
                "next_command",
                "fix_steps",
                "rule_flags",
            ],
        )
        writer.writeheader()
        writer.writerows(diagnoses_rows)

    with open(os.path.join(out_dir, "case_results.csv"), "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "case_id",
                "concept_tag",
                "severity",
                "expected_fault",
                "ai_root_cause",
                "ai_expected_agreement",
                "review_status",
                "review_notes",
                "final_fault",
            ],
        )
        writer.writeheader()
        writer.writerows(results_rows)

    by_concept = Counter(row["concept_tag"] for row in results_rows)
    by_severity = Counter(row["severity"] for row in results_rows)
    by_status = Counter(row["review_status"] for row in results_rows)
    ai_agreement = Counter(row["ai_expected_agreement"] for row in results_rows)

    summary_rows = []
    summary_rows.extend({"section": "issue_type", "key": k, "value": v} for k, v in sorted(by_concept.items()))
    summary_rows.extend({"section": "severity", "key": k, "value": v} for k, v in sorted(by_severity.items()))
    summary_rows.extend({"section": "review_status", "key": k, "value": v} for k, v in sorted(by_status.items()))
    summary_rows.extend({"section": "ai_vs_expected", "key": k, "value": v} for k, v in sorted(ai_agreement.items()))

    with open(os.path.join(dashboard_dir, "summary.csv"), "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["section", "key", "value"])
        writer.writeheader()
        writer.writerows(summary_rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run NetSage AI demo workflow")
    parser.add_argument("--cases", required=True)
    parser.add_argument("--reviews", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--dashboard", required=True)
    args = parser.parse_args()
    run(args.cases, args.reviews, args.out, args.dashboard)
    print("Workflow complete. Outputs written.")


if __name__ == "__main__":
    main()
