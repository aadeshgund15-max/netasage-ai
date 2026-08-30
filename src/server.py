"""NetSage AI local web server.

Serves the browser UI and exposes a small JSON API backed by the existing
workflow/rule-checker modules. No third-party Python packages are required.
"""
import csv
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UI_DIR = os.path.join(ROOT, "ui")
DATA_DIR = os.path.join(ROOT, "data")
OUT_DIR = os.path.join(ROOT, "outputs")
DASHBOARD_DIR = os.path.join(ROOT, "dashboard")

sys.path.insert(0, os.path.join(ROOT, "src"))
from workflow import ai_diagnose, compare_fault, load_reviews  # noqa: E402
from rule_checker import check_case  # noqa: E402

CASES_PATH = os.path.join(DATA_DIR, "cases.csv")
REVIEWS_PATH = os.path.join(DATA_DIR, "human_review_log.csv")


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def json_bytes(payload):
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")


def public_case(row):
    return {
        "case_id": row.get("case_id", ""),
        "symptom": row.get("symptom", ""),
        "topology_note": row.get("topology_note", ""),
        "show_outputs": row.get("show_outputs", ""),
        "expected_fault": row.get("expected_fault", ""),
        "osi_layer": row.get("osi_layer", ""),
        "concept_tag": row.get("concept_tag", ""),
        "severity": row.get("severity", ""),
        "assigned_ips": row.get("assigned_ips", ""),
        "subnet_masks": row.get("subnet_masks", ""),
        "expected_mask": row.get("expected_mask", ""),
        "default_gateway": row.get("default_gateway", ""),
        "gateway_interface_ip": row.get("gateway_interface_ip", ""),
        "interface_status": row.get("interface_status", ""),
        "required_vlans": row.get("required_vlans", ""),
        "configured_vlans": row.get("configured_vlans", ""),
        "required_routes": row.get("required_routes", ""),
        "configured_routes": row.get("configured_routes", ""),
    }


def diagnose_case(case):
    ai = ai_diagnose(case)
    findings = check_case(case)
    expected = case.get("expected_fault", "")
    agreement = compare_fault(expected, str(ai["root_cause"])) if expected else None
    return {
        "case": public_case(case),
        "diagnosis": ai,
        "rule_findings": findings,
        "agreement": agreement,
    }


def summary():
    path = os.path.join(DASHBOARD_DIR, "summary.csv")
    if os.path.exists(path):
        return read_csv(path)
    return []


def save_review(payload):
    case_id = str(payload.get("case_id", "")).strip()
    status = str(payload.get("review_status", "")).strip()
    notes = str(payload.get("review_notes", "")).strip()
    final_fault = str(payload.get("final_fault", "")).strip()
    if not case_id or status not in {"Accepted", "Edited", "Rejected"}:
        raise ValueError("case_id and a valid review_status are required")

    rows = read_csv(REVIEWS_PATH) if os.path.exists(REVIEWS_PATH) else []
    found = False
    for row in rows:
        if row.get("case_id") == case_id:
            row.update({"review_status": status, "review_notes": notes, "final_fault": final_fault})
            found = True
            break
    if not found:
        rows.append({"case_id": case_id, "review_status": status, "review_notes": notes, "final_fault": final_fault})

    with open(REVIEWS_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["case_id", "review_status", "review_notes", "final_fault"])
        writer.writeheader()
        writer.writerows(rows)

    # Refresh reproducible output files after a review change.
    from workflow import run
    run(CASES_PATH, REVIEWS_PATH, OUT_DIR, DASHBOARD_DIR)
    return True


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _send(self, status, payload, content_type="application/json; charset=utf-8"):
        body = payload if isinstance(payload, bytes) else payload.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status, payload):
        self._send(status, json_bytes(payload))

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        try:
            if path == "/api/health":
                return self._json(200, {"ok": True, "service": "NetSage AI backend"})
            if path == "/api/cases":
                return self._json(200, {"cases": [public_case(x) for x in read_csv(CASES_PATH)]})
            if path == "/api/summary":
                return self._json(200, {"summary": summary()})
            if path.startswith("/api/cases/"):
                case_id = path.rsplit("/", 1)[-1]
                for row in read_csv(CASES_PATH):
                    if row.get("case_id") == case_id:
                        return self._json(200, diagnose_case(row))
                return self._json(404, {"error": "Case not found"})
            return self._serve_ui(path)
        except Exception as exc:
            return self._json(500, {"error": str(exc)})

    def do_POST(self):
        parsed = urlparse(self.path)
        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length) if length else b"{}"
            payload = json.loads(raw.decode("utf-8"))
            if parsed.path == "/api/diagnose":
                case = dict(payload)
                return self._json(200, diagnose_case(case))
            if parsed.path == "/api/review":
                save_review(payload)
                return self._json(200, {"ok": True, "message": "Review saved and outputs refreshed."})
            return self._json(404, {"error": "Endpoint not found"})
        except Exception as exc:
            return self._json(400, {"error": str(exc)})

    def _serve_ui(self, path):
        rel = "index.html" if path in {"/", ""} else path.lstrip("/")
        target = os.path.abspath(os.path.join(UI_DIR, rel))
        if not target.startswith(os.path.abspath(UI_DIR)) or not os.path.isfile(target):
            return self._json(404, {"error": "Not found"})
        ext = os.path.splitext(target)[1].lower()
        types = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8", ".js": "text/javascript; charset=utf-8"}
        with open(target, "rb") as f:
            body = f.read()
        return self._send(200, body, types.get(ext, "application/octet-stream"))

    def log_message(self, fmt, *args):
        print("[NetSage] " + fmt % args)


def main():
    port = int(os.environ.get("NETSAGE_PORT", "8000"))
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"NetSage AI UI running at http://127.0.0.1:{port}")
    print("Press Ctrl+C to stop the server.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping NetSage AI server...")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
