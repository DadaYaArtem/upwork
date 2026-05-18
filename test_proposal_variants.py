"""Smoke tests for proposal variant formatting and sheet payloads."""
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

os.environ.setdefault("OPENAI_API_KEY", "sk-test-dummy")
os.environ.setdefault("SLACK_BOT_TOKEN", "xoxb-dummy")
os.environ.setdefault("SLACK_APP_TOKEN", "xapp-dummy")

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "CoverLetter"))
sys.path.insert(0, str(ROOT))

sys.modules.setdefault("slack_bolt", MagicMock(App=MagicMock(return_value=MagicMock())))
sys.modules.setdefault("slack_bolt.adapter.socket_mode", MagicMock(SocketModeHandler=MagicMock()))

import cover_letter_generator as clg
import slack_bot


VARIANTS = [
    {
        "structure_name": "Risk / Ownership",
        "angle": "Frames the work around the highest production risk.",
        "when_to_use": "Use when the job mentions brittle systems or compliance.",
        "cover_letter": "Risk letter\n\nBest,\nViktoryia",
    },
    {
        "structure_name": "Architecture / Approach",
        "angle": "Shows the build plan before the proof.",
        "when_to_use": "Use when the client asks for stack or implementation plan.",
        "cover_letter": "Architecture letter\n\nBest,\nViktoryia",
    },
    {
        "structure_name": "Case-Led Proof",
        "angle": "Leads with the closest comparable case.",
        "when_to_use": "Use when the selected case is a very close match.",
        "cover_letter": "Case letter\n\nBest,\nViktoryia",
    },
]


RESULT = {
    "job_evaluation": {"decision": "PASS", "reasoning": "Good fit", "flags": ""},
    "selected_profile": {"name": "Victoria", "reasoning": "Full-stack match"},
    "selected_cases": [],
    "cover_letter": "Main letter\n\nBest,\nViktoryia",
    "screening_answers": "",
    "proposal_variants": VARIANTS,
}


def test_slack_variant_messages_are_separate_and_complete():
    main_msg = slack_bot.format_result_message(RESULT)
    variant_msgs = slack_bot.format_proposal_variant_messages(RESULT)

    assert "Proposal variants" not in main_msg
    assert len(variant_msgs) == 3
    assert "Risk / Ownership" in variant_msgs[0]
    assert "Architecture letter" in variant_msgs[1]
    assert "Case-Led Proof" in variant_msgs[2]
    assert all(len(msg) <= 4000 for msg in variant_msgs)


def test_malformed_variants_do_not_crash_slack_formatting():
    result = {"proposal_variants": [None, {"structure_name": "No letter"}, {"cover_letter": "OK"}]}
    variant_msgs = slack_bot.format_proposal_variant_messages(result)

    assert len(variant_msgs) == 1
    assert "OK" in variant_msgs[0]


def test_sheet_payload_includes_main_letter_and_all_variants():
    payload = clg.format_cover_letter_for_sheet(RESULT["cover_letter"], RESULT["proposal_variants"])

    assert "MAIN COVER LETTER" in payload
    assert "Main letter" in payload
    assert "VARIANT 1: Risk / Ownership" in payload
    assert "VARIANT 2: Architecture / Approach" in payload
    assert "VARIANT 3: Case-Led Proof" in payload


def test_normalize_proposal_variants_fixes_newlines_and_filters_bad_entries():
    result = {
        "proposal_variants": [
            {"structure_name": "Risk / Ownership", "cover_letter": "Line 1\\n\\n\\nLine 2"},
            {"structure_name": "Bad"},
            "not a dict",
        ]
    }

    clg.normalize_proposal_variants(result)

    assert len(result["proposal_variants"]) == 1
    assert result["proposal_variants"][0]["cover_letter"] == "Line 1\n\nLine 2"


def test_main_prompt_requires_three_proposal_variants():
    prompt = clg._build_main_prompt(
        job_description="Build a React and Node.js SaaS with an implementation plan.",
        cases_text="CASE",
        profiles_to_use=clg.user_profiles[:1],
        selection_rules=clg.selection_rules,
        screening_questions=[],
        forbidden_case_ids=None,
        examples_block="EXAMPLES",
    )

    assert "PROPOSAL VARIANT RULES" in prompt
    assert "Generate exactly 3 additional full proposal variants" in prompt
    assert '"proposal_variants"' in prompt
    assert "Risk / Ownership" in prompt
    assert "Architecture / Approach" in prompt
    assert "Case-Led Proof" in prompt
