"""CLI entry point for the scenario test harness.

Usage:
    python -m tests.scenarios.runner                  # all scenarios, parallel
    python -m tests.scenarios.runner --sequential     # serial, easier to debug
    python -m tests.scenarios.runner -k lobster       # filter by id substring
    python -m tests.scenarios.runner --workers 8      # override pool size
    python -m tests.scenarios.runner --no-judge       # skip LLM judge entirely
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

import yaml

from tests.scenarios.assertions import run_assertions
from tests.scenarios.driver import run_scenario
from tests.scenarios.judge import run_judge
from tests.scenarios.report import (
    ScenarioResult,
    make_run_id,
    transcript_to_result,
    write_scenario_json,
    write_summary_md,
)
from tests.scenarios.schema import Scenario

HERE = Path(__file__).resolve().parent
SCENARIOS_DIR = HERE / "scenarios"
REPORTS_DIR = HERE / "reports"


def load_scenarios(filter_substring: str | None) -> list[Scenario]:
    scenarios: list[Scenario] = []
    errors: list[str] = []
    for path in sorted(SCENARIOS_DIR.glob("*.yaml")):
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
            s = Scenario(**raw)
        except Exception as e:
            errors.append(f"{path.name}: {e}")
            continue
        if filter_substring and filter_substring not in s.id:
            continue
        scenarios.append(s)
    if errors:
        print("Scenario load errors:", file=sys.stderr)
        for e in errors:
            print(f"  {e}", file=sys.stderr)
        sys.exit(2)
    return scenarios


async def _execute_one(scenario: Scenario, skip_judge: bool) -> ScenarioResult:
    transcript = await run_scenario(scenario)
    assertion_results = run_assertions(scenario.assertions, transcript)

    judge_verdict = None
    if scenario.judge and not skip_judge and transcript.error is None:
        judge_verdict = await run_judge(
            scenario.judge, scenario.prompt, transcript.final_text
        )

    return transcript_to_result(scenario, transcript, assertion_results, judge_verdict)


async def _run_pool(
    scenarios: list[Scenario], workers: int, skip_judge: bool
) -> list[ScenarioResult]:
    sem = asyncio.Semaphore(workers)
    results: list[ScenarioResult] = []

    async def _guarded(s: Scenario):
        async with sem:
            print(f"  -> {s.id}")
            r = await _execute_one(s, skip_judge)
            mark = "PASS" if r.passed else "FAIL"
            print(f"  {mark}  {s.id}")
            results.append(r)

    await asyncio.gather(*[_guarded(s) for s in scenarios])
    results.sort(key=lambda r: r.scenario_id)
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="DreamBot MCP scenario test runner")
    parser.add_argument("-k", dest="filter", default=None, help="substring filter on scenario id")
    parser.add_argument("--sequential", action="store_true", help="force workers=1")
    parser.add_argument("--workers", type=int, default=4, help="parallel worker count")
    parser.add_argument("--no-judge", action="store_true", help="skip LLM judge entirely")
    args = parser.parse_args()

    scenarios = load_scenarios(args.filter)
    if not scenarios:
        print("No scenarios matched.", file=sys.stderr)
        return 1

    workers = 1 if args.sequential else max(1, args.workers)

    run_id = make_run_id()
    run_dir = REPORTS_DIR / run_id
    print(f"Run {run_id} - {len(scenarios)} scenarios, {workers} workers")

    results = asyncio.run(_run_pool(scenarios, workers, args.no_judge))

    for r in results:
        write_scenario_json(run_dir, r)
    summary_path = write_summary_md(run_dir, results)

    passed = sum(1 for r in results if r.passed)
    failed = len(results) - passed
    print(f"\nDone. {passed} passed, {failed} failed. Report: {summary_path}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
