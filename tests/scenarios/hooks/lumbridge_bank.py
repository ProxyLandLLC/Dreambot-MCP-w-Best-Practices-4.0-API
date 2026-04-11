"""Custom assertion: Lumbridge bank scenario must return the bank tile, not the
generic Lumbridge centre.
"""
from __future__ import annotations

from tests.scenarios.assertions import AssertionResult
from tests.scenarios.transcript import Transcript


def check(transcript: Transcript) -> list[AssertionResult]:
    text = transcript.final_text
    has_bank = "3208" in text and "3220" in text
    has_generic = "3239" in text and "3234" in text
    return [
        AssertionResult(
            "lumbridge_bank.has_bank_tile",
            has_bank,
            "expected bank tile (3208, 3220) in response",
        ),
        AssertionResult(
            "lumbridge_bank.not_generic_centre",
            not has_generic,
            "generic Lumbridge centre (3239, 3234) should not appear",
        ),
    ]
