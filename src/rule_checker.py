import argparse
import csv
import json
from typing import Dict, List


REQUIRED_CHECKS = (
    "duplicate_ip",
    "wrong_mask",
    "gateway_mismatch",
    "interface_down",
    "missing_vlan",
    "missing_route",
)


def _split(field: str) -> List[str]:
    if not field:
        return []
    return [item.strip() for item in field.split("|") if item.strip()]


def check_case(case: Dict[str, str]) -> List[Dict[str, str]]:
    findings: List[Dict[str, str]] = []

    # 1. Duplicate IP Check
    ips = _split(case.get("assigned_ips", ""))
    seen = set()
    duplicates = set()
    for ip in ips:
        if ip in seen:
            duplicates.add(ip)
        seen.add(ip)
    if duplicates:
        dup_str = ", ".join(sorted(duplicates))
        findings.append({
            "rule": "duplicate_ip",
            "detail": f"Duplicate assigned IP(s): {dup_str}",
            "solution": f"1. Identify hosts configured with IP {dup_str}.\n2. Reconfigure static IP or clear DHCP lease reservation.\n3. Assign unique IP addresses within the subnet range."
        })

    # 2. Subnet Mask Check
    expected_mask = case.get("expected_mask", "").strip()
    for pair in _split(case.get("subnet_masks", "")):
        if "=" not in pair:
            continue
        host, mask = pair.split("=", 1)
        if expected_mask and mask.strip() != expected_mask:
            findings.append({
                "rule": "wrong_mask",
                "detail": f"{host.strip()} uses {mask.strip()} expected {expected_mask}",
                "solution": f"1. Access configuration on {host.strip()}.\n2. Update interface network subnet mask from {mask.strip()} to {expected_mask}.\n3. Verify local broadcast and gateway reachability."
            })

    # 3. Gateway Mismatch Check
    default_gw = case.get("default_gateway", "").strip()
    gateway_if = case.get("gateway_interface_ip", "").strip()
    if default_gw and gateway_if and default_gw != gateway_if:
        findings.append({
            "rule": "gateway_mismatch",
            "detail": f"Host gateway {default_gw} does not match interface {gateway_if}",
            "solution": f"1. On host/client settings, change default gateway to {gateway_if}, OR\n2. Reconfigure router subinterface IP to match expected gateway: ip address {default_gw} <subnet_mask>."
        })

    # 4. Down Interface Check
    down_ifaces = []
    for iface in _split(case.get("interface_status", "")):
        if ":" not in iface:
            continue
        name, state = iface.split(":", 1)
        if state.strip().lower() != "up":
            down_ifaces.append(name.strip())
    if down_ifaces:
        ifaces_str = ", ".join(down_ifaces)
        findings.append({
            "rule": "interface_down",
            "detail": f"Interface(s) down: {ifaces_str}",
            "solution": f"1. Access router/switch console.\n2. Enter interface configuration mode for interface(s) {ifaces_str}.\n3. Execute the 'no shutdown' command and verify physical link cables."
        })

    # 5. Missing VLAN Check
    required_vlans = set(_split(case.get("required_vlans", "")))
    configured_vlans = set(_split(case.get("configured_vlans", "")))
    missing_vlans = sorted(required_vlans - configured_vlans)
    if missing_vlans:
        vlans_str = ", ".join(missing_vlans)
        findings.append({
            "rule": "missing_vlan",
            "detail": f"Missing VLAN(s): {vlans_str}",
            "solution": f"1. Access trunking switch.\n2. Create missing VLAN(s) in database: vlan {vlans_str}.\n3. Add to trunk allowed list: switchport trunk allowed vlan add {vlans_str}."
        })

    # 6. Missing Route Check
    required_routes = set(_split(case.get("required_routes", "")))
    configured_routes = set(_split(case.get("configured_routes", "")))
    missing_routes = sorted(required_routes - configured_routes)
    if missing_routes:
        routes_str = ", ".join(missing_routes)
        findings.append({
            "rule": "missing_route",
            "detail": f"Missing route(s): {routes_str}",
            "solution": f"1. Log into edge/core router.\n2. Add static route or check routing protocol advertisement for {routes_str}.\n3. Syntax: ip route <destination_network> <subnet_mask> <next_hop_ip>."
        })

    return findings


def run_checks(cases_path: str) -> List[Dict[str, object]]:
    results: List[Dict[str, object]] = []
    with open(cases_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            results.append(
                {
                    "case_id": row["case_id"],
                    "expected_fault": row["expected_fault"],
                    "findings": check_case(row),
                }
            )
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="NetSage deterministic rule checker")
    parser.add_argument("--cases", required=True, help="Path to cases.csv")
    parser.add_argument("--limit", type=int, default=0, help="Print only first N cases")
    args = parser.parse_args()

    results = run_checks(args.cases)
    to_print = results[: args.limit] if args.limit else results
    print(json.dumps(to_print, indent=2))


if __name__ == "__main__":
    main()