from tests.scenarios.assertions import run_assertions
from tests.scenarios.schema import Assertions, ToolCallWith
from tests.scenarios.transcript import ToolCall, Transcript


def _transcript():
    return Transcript(
        prompt="p",
        final_text="Bank.open() is the method. Lobster id 379.",
        tool_calls=[
            ToolCall("dreambot_search", {"query": "Bank.open"}),
            ToolCall("dreambot_item", {"query": "lobster"}),
        ],
    )


def test_tool_called_pass():
    a = Assertions(tool_called=["dreambot_search", "dreambot_item"])
    results = run_assertions(a, _transcript())
    assert all(r.passed for r in results)


def test_tool_called_fail():
    a = Assertions(tool_called=["dreambot_tile"])
    results = run_assertions(a, _transcript())
    assert any(not r.passed and "dreambot_tile" in r.message for r in results)


def test_tool_not_called_pass():
    a = Assertions(tool_not_called=["dreambot_tile"])
    results = run_assertions(a, _transcript())
    assert all(r.passed for r in results)


def test_tool_not_called_fail():
    a = Assertions(tool_not_called=["dreambot_search"])
    results = run_assertions(a, _transcript())
    assert any(not r.passed for r in results)


def test_tool_call_count():
    a = Assertions(tool_call_count={"dreambot_search": 1, "dreambot_item": 1})
    results = run_assertions(a, _transcript())
    assert all(r.passed for r in results)


def test_tool_called_with_args():
    a = Assertions(
        tool_called_with=[
            ToolCallWith(name="dreambot_search", args_contain={"query": "Bank.open"})
        ]
    )
    results = run_assertions(a, _transcript())
    assert all(r.passed for r in results)


def test_response_contains():
    a = Assertions(response_contains=["Bank.open()", "379"])
    results = run_assertions(a, _transcript())
    assert all(r.passed for r in results)


def test_response_not_contains():
    a = Assertions(response_not_contains=["deprecated"])
    results = run_assertions(a, _transcript())
    assert all(r.passed for r in results)


def test_response_matches_regex():
    a = Assertions(response_matches=[r"Lobster id \d+"])
    results = run_assertions(a, _transcript())
    assert all(r.passed for r in results)
