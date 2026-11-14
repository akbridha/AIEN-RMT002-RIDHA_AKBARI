from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import httpx


ROOT = Path(__file__).resolve().parents[1]


def run(base_url: str, token: str) -> dict[str, Any]:
    """Run all 15 cases and write outputs/evaluation_report.json with release decision."""
    cases_path = ROOT / "data" / "evaluation_cases.json"
    with open(cases_path, "r", encoding="utf-8") as f:
        cases: list[dict[str, Any]] = json.load(f)

    headers = {"Authorization": f"Bearer {token}"}
    client = httpx.Client(base_url=base_url, timeout=40.0)

    results: list[dict[str, Any]] = []
    hard_gate_failures = 0
    total_passed = 0

    for case in cases:
        case_id = case["case_id"]
        inp = case["input"]
        hard_gate = case.get("hard_gate", False)
        expected_docs = case.get("expected_documents", [])
        expected_tools = case.get("expected_tools", [])
        expected_outcome = case.get("expected_outcome")
        forbidden = case.get("forbidden_facts", [])

        passed = True
        reasons: list[str] = []

        try:
            res = client.post("/api/v1/chat", headers=headers, json={"message": inp})
            if res.status_code != 200:
                passed = False
                reasons.append(f"HTTP {res.status_code}: {res.text}")
            else:
                payload = res.json()
                answer = payload.get("answer", "")
                outcome = payload.get("outcome")
                tool_names = [tc["name"] for tc in payload.get("tool_calls", [])]
                cited_docs = [c["document_id"] for c in payload.get("citations", [])]

                if expected_outcome and outcome != expected_outcome:
                    passed = False
                    reasons.append(f"Expected outcome '{expected_outcome}', got '{outcome}'")

                for doc in expected_docs:
                    if doc not in cited_docs:
                        passed = False
                        reasons.append(f"Missing expected citation: {doc}")

                for tool in expected_tools:
                    if tool not in tool_names:
                        passed = False
                        reasons.append(f"Expected tool '{tool}' not called")

                for fact in forbidden:
                    if fact.lower() in answer.lower():
                        passed = False
                        reasons.append(f"Forbidden fact '{fact}' found in response")

        except Exception as e:
            passed = False
            reasons.append(f"Exception: {e}")

        if not passed and hard_gate:
            hard_gate_failures += 1
        if passed:
            total_passed += 1

        results.append({
            "case_id": case_id,
            "category": case.get("category"),
            "hard_gate": hard_gate,
            "passed": passed,
            "reasons": reasons,
        })

    pass_rate = total_passed / len(cases) if cases else 0.0
    ready_for_release = (hard_gate_failures == 0) and (pass_rate >= 0.8)

    report = {
        "total_cases": len(cases),
        "total_passed": total_passed,
        "pass_rate": pass_rate,
        "hard_gate_failures": hard_gate_failures,
        "release_decision": "GO" if ready_for_release else "NO-GO",
        "results": results,
    }

    out_dir = ROOT / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "evaluation_report.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"Evaluation complete: {total_passed}/{len(cases)} passed ({pass_rate:.1%}). Release: {report['release_decision']}")
    return report


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
    tok = sys.argv[2] if len(sys.argv) > 2 else "token-alya"
    run(url, tok)

