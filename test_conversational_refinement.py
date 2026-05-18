"""Tests for follow-up chat routing and targeted proposal edits."""
import copy
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault("OPENAI_API_KEY", "sk-test-dummy")
os.environ.setdefault("SLACK_BOT_TOKEN", "xoxb-dummy")
os.environ.setdefault("SLACK_APP_TOKEN", "xapp-dummy")

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "CoverLetter"))
sys.path.insert(0, str(ROOT))

sys.modules.setdefault("slack_bolt", MagicMock(App=MagicMock(return_value=MagicMock())))
sys.modules.setdefault("slack_bolt.adapter.socket_mode", MagicMock(SocketModeHandler=MagicMock()))

import slack_bot


def make_result() -> dict:
    return {
        "job_evaluation": {"decision": "PASS", "reasoning": "Good fit", "flags": ""},
        "selected_profile": {"name": "Victoria", "reasoning": "Full-stack match"},
        "cover_letter": "Main letter",
        "screening_answers": "1. Answer",
        "proposal_variants": [
            {"structure_name": "Risk / Ownership", "angle": "", "cover_letter": "Variant 1"},
            {"structure_name": "Architecture / Approach", "angle": "", "cover_letter": "Variant 2"},
            {"structure_name": "Case-Led Proof", "angle": "", "cover_letter": "Variant 3"},
        ],
    }


def make_dual_result() -> dict:
    return {
        "dual": True,
        "tilek": make_result() | {"selected_profile": {"name": "Tilek Chubakov"}},
        "victoria": make_result() | {"selected_profile": {"name": "Victoria"}},
    }


def test_target_parsing_for_variant_main_and_screening():
    result = make_result()

    route = slack_bot.classify_followup_message("сделай 3 вариант короче", result)
    assert route["action"] == "edit"
    assert route["target_type"] == "variant"
    assert route["variant_index"] == 2

    route = slack_bot.classify_followup_message("перепиши основной менее формально", result)
    assert route["action"] == "edit"
    assert route["target_type"] == "main"

    route = slack_bot.classify_followup_message("добавь деталей в ответы", result)
    assert route["action"] == "edit"
    assert route["target_type"] == "screening"

    route = slack_bot.classify_followup_message("сделай короче", result)
    assert route["action"] == "clarify"
    assert route["missing"] == "target"


def test_dual_mode_requires_profile_unless_profile_is_named():
    dual = make_dual_result()

    route = slack_bot.classify_followup_message("сделай 2 вариант короче", dual)
    assert route["action"] == "clarify"
    assert route["missing"] == "profile"

    route = slack_bot.classify_followup_message("сделай victoria 2 вариант короче", dual)
    assert route["action"] == "edit"
    assert route["profile_key"] == "victoria"
    assert route["target_type"] == "variant"
    assert route["variant_index"] == 1


def test_pending_target_clarification_resolves_to_edit():
    result = make_result()
    pending = slack_bot.classify_followup_message("сделай короче", result)

    route = slack_bot.resolve_pending_followup(pending, "вариант 3", result)

    assert route["action"] == "edit"
    assert route["target_type"] == "variant"
    assert route["variant_index"] == 2


def test_variant_edit_updates_only_target_variant():
    user_id = "U1"
    result = make_result()
    slack_bot._user_last_result[user_id] = copy.deepcopy(result)
    messages = []

    with patch("slack_bot.refine_letter", AsyncMock(return_value={
        "cover_letter": "Variant 3 shortened",
        "screening_answers": "",
    })):
        handled = slack_bot._handle_followup_route(user_id, {
            "action": "edit",
            "target_type": "variant",
            "variant_index": 2,
            "instruction": "Make it shorter.",
            "profile_key": None,
        }, messages.append)

    updated = slack_bot._user_last_result[user_id]
    assert handled is True
    assert updated["proposal_variants"][0]["cover_letter"] == "Variant 1"
    assert updated["proposal_variants"][1]["cover_letter"] == "Variant 2"
    assert updated["proposal_variants"][2]["cover_letter"] == "Variant 3 shortened"
    assert updated["cover_letter"] == "Main letter"
    assert any("Variant 3 shortened" in msg for msg in messages)


def test_question_route_answers_without_mutating_state():
    user_id = "U2"
    result = make_result()
    slack_bot._user_last_result[user_id] = copy.deepcopy(result)
    before = copy.deepcopy(slack_bot._user_last_result[user_id])
    messages = []

    with patch("slack_bot.answer_about_last_result", AsyncMock(return_value="Variant 2 is strongest.")):
        handled = slack_bot._handle_followup_route(user_id, {
            "action": "question",
            "question": "какой вариант лучше?",
        }, messages.append)

    assert handled is True
    assert slack_bot._user_last_result[user_id] == before
    assert messages[-1] == "Variant 2 is strongest."


def test_long_job_text_is_still_new_job():
    result = make_result()
    text = (
        "Job description\n"
        "We are looking for a senior React and Node.js developer.\n"
        "Requirements include PostgreSQL, Stripe, authentication, and scalable architecture.\n"
    ) * 8

    route = slack_bot.classify_followup_message(text, result)
    assert route["action"] == "new_job"
