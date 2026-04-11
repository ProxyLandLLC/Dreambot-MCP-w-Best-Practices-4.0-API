from tests.scenarios.transcript import ToolCall, Transcript


def test_transcript_helpers():
    t = Transcript(
        prompt="hi",
        final_text="done",
        tool_calls=[
            ToolCall("dreambot_search", {"query": "Bank"}, "Bank.open()"),
            ToolCall("dreambot_item", {"query": "lobster"}, "379"),
            ToolCall("dreambot_search", {"query": "Walking"}, "Walking.walk()"),
        ],
    )
    assert t.tool_names() == ["dreambot_search", "dreambot_item", "dreambot_search"]
    assert len(t.calls_for("dreambot_search")) == 2
    assert len(t.calls_for("dreambot_tile")) == 0
