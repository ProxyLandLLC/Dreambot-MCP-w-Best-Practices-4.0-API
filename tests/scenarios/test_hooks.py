from tests.scenarios.hooks.lumbridge_bank import check
from tests.scenarios.transcript import Transcript


def test_lumbridge_hook_pass():
    t = Transcript(prompt="p", final_text="Lumbridge bank at 3208, 3220.")
    results = check(t)
    assert all(r.passed for r in results)


def test_lumbridge_hook_fail_generic():
    t = Transcript(prompt="p", final_text="Lumbridge at 3239, 3234.")
    results = check(t)
    assert any(not r.passed for r in results)
