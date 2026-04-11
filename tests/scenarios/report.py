"""Write scenario run reports to disk."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from tests.scenarios.assertions import AssertionResult
from tests.scenarios.judge import JudgeVerdict
from tests.scenarios.schema import Scenario
from tests.scenarios.transcript import Transcript


@dataclass
class ScenarioResult:
    scenario_id: str
    description: str
    passed: bool
    assertion_results: list[AssertionResult] = field(default_factory=list)
    judge_verdict: JudgeVerdict | None = None
    transcript_error: str | None = None
    tool_calls: list[dict] = field(default_factory=list)
    final_text: str = ""


def make_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")


def transcript_to_result(
    scenario: Scenario,
    transcript: Transcript,
    assertion_results: list[AssertionResult],
    judge_verdict: JudgeVerdict | None,
) -> ScenarioResult:
    structural_ok = all(a.passed for a in assertion_results) and transcript.error is None
    judge_ok = True if judge_verdict is None else judge_verdict.passed
    return ScenarioResult(
        scenario_id=scenario.id,
        description=scenario.description,
        passed=structural_ok and judge_ok,
        assertion_results=assertion_results,
        judge_verdict=judge_verdict,
        transcript_error=transcript.error,
        tool_calls=[{"name": c.name, "args": c.args} for c in transcript.tool_calls],
        final_text=transcript.final_text,
    )


def write_scenario_json(run_dir: Path, result: ScenarioResult) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / f"{result.scenario_id}.json"
    payload = {
        "scenario_id": result.scenario_id,
        "description": result.description,
        "passed": result.passed,
        "assertion_results": [asdict(a) for a in result.assertion_results],
        "judge_verdict": asdict(result.judge_verdict) if result.judge_verdict else None,
        "transcript_error": result.transcript_error,
        "tool_calls": result.tool_calls,
        "final_text": result.final_text,
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_summary_md(run_dir: Path, results: list[ScenarioResult]) -> Path:
    run_dir.mkdir(parents=True, exist_ok=True)
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    failed = total - passed

    lines = [
        f"# Scenario Run — {run_dir.name}",
        "",
        f"**Total:** {total}  |  **Passed:** {passed}  |  **Failed:** {failed}",
        "",
        "## Results",
        "",
        "| Scenario | Pass | Failing assertions | Judge |",
        "|---|---|---|---|",
    ]
    for r in results:
        mark = "PASS" if r.passed else "FAIL"
        fails = "; ".join(a.name for a in r.assertion_results if not a.passed) or "-"
        judge = ""
        if r.judge_verdict:
            jv = r.judge_verdict
            judge = f"{'pass' if jv.passed else 'fail'} ({jv.score}/10)"
        lines.append(f"| `{r.scenario_id}` | {mark} | {fails} | {judge} |")

    path = run_dir / "summary.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
