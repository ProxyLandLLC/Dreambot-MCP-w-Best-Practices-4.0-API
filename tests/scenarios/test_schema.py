import yaml

from tests.scenarios.schema import Scenario


def test_minimal_scenario_loads():
    raw = yaml.safe_load(
        """
        id: smoke
        description: say hello
        prompt: "Say hello."
        assertions:
          response_contains:
            - hello
        """
    )
    s = Scenario(**raw)
    assert s.id == "smoke"
    assert s.assertions.response_contains == ["hello"]
    assert s.judge is None


def test_scenario_with_judge():
    raw = yaml.safe_load(
        """
        id: script
        description: write a script
        prompt: "Write a script."
        assertions:
          tool_called:
            - dreambot_item
        judge:
          rubric: "Is it good?"
        """
    )
    s = Scenario(**raw)
    assert s.judge is not None
    assert s.judge.model == "claude-sonnet-4-6"
    assert s.judge.pass_threshold == 7
