# NetSage AI

NetSage AI is a prototype troubleshooting helper for Cisco-style Packet Tracer/lab networks. It combines deterministic configuration checks with an AI-style diagnosis layer and requires human review (`Accepted`, `Edited`, or `Rejected`) for each case.

> **Prototype note:** The current diagnosis layer is a deterministic, keyword-based demonstrator rather than a trained or hosted LLM. The project is designed to demonstrate the troubleshooting workflow and human-in-the-loop validation.

## Project structure

- `data/cases.csv` - 32 troubleshooting lab cases
- `prompts/diagnose_prompt.md` - structured diagnosis prompt library with JSON schema and examples
- `src/rule_checker.py` - deterministic rule checker CLI
- `src/workflow.py` - end-to-end demo workflow
- `data/human_review_log.csv` - human review statuses and rationale
- `outputs/ai_diagnoses.csv` - generated diagnosis results
- `outputs/case_results.csv` - case-level evaluation results
- `dashboard/summary.csv` - issue/severity/agreement summary
- `submission/` - final report, presentation, and verification log

## Quick demo

Run these commands from the project root:

```bash
python src/rule_checker.py --cases data/cases.csv --limit 3

python src/workflow.py \
  --cases data/cases.csv \
  --reviews data/human_review_log.csv \
  --out outputs \
  --dashboard dashboard
```

## Testing

```bash
python -m unittest discover -s tests -p 'test_*.py'
```

Expected result: all included tests pass.

## Browser UI + Python backend

NetSage includes a dependency-free local web UI connected to the existing Python diagnosis and rule-checking modules.

### Run the UI

From the project root:

```bash
python src/server.py
```

Then open **http://127.0.0.1:8000** in a browser.

The UI provides:
- 32-case library with search and case details
- live diagnosis through the existing `workflow.py` diagnosis function
- deterministic rule findings from `rule_checker.py`
- evidence, next Cisco command, and recommended fix steps
- human review controls (Accepted / Edited / Rejected)
- dashboard metrics from `dashboard/summary.csv`
- custom symptom + `show` output diagnosis

No third-party Python packages are required for the UI server.

> **Prototype note:** The current diagnosis layer is a deterministic AI-style demonstrator, not a trained/hosted LLM. The UI does not claim otherwise; the human-review step remains part of the prototype workflow.
