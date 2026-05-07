"""Tests for Task 4 — Hook options (3 variants, auto-select strongest)."""
import sys, os, json, asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from pathlib import Path

os.environ.setdefault("OPENAI_API_KEY", "sk-test-dummy")
os.environ.setdefault("SLACK_BOT_TOKEN", "xoxb-dummy")
os.environ.setdefault("SLACK_APP_TOKEN", "xapp-dummy")

sys.path.insert(0, str(Path(__file__).parent / "CoverLetter"))
sys.path.insert(0, str(Path(__file__).parent))

import cover_letter_generator as clg

# Stub slack_bolt before importing slack_bot so App() doesn't call auth.test
from unittest.mock import MagicMock as _MM
import sys as _sys
_sys.modules.setdefault("slack_bolt", _MM(App=_MM(return_value=_MM())))
_sys.modules.setdefault("slack_bolt.adapter.socket_mode", _MM(SocketModeHandler=_MM()))


def make_openai_response(content: dict):
    r = MagicMock()
    r.choices = [MagicMock()]
    r.choices[0].message.content = json.dumps(content)
    return r


HOOK_OPTIONS = [
    {"text": "From what I see, your biggest risk is shipping ML features without a data pipeline that can keep up.", "specificity_score": 9},
    {"text": "Let me be honest — most RAG implementations I review are slow because the retrieval layer was bolted on last.", "specificity_score": 7},
    {"text": "To be direct: building a reliable LLM product is 20% model and 80% infrastructure.", "specificity_score": 6},
]

MOCK_EVAL_WITH_HOOKS = {
    "job_evaluation": {"decision": "PASS", "reasoning": "Good AI fit", "flags": ""},
    "selected_profile": {"name": "Tilek Chubakov", "reasoning": "AI match"},
    "selected_cases": [
        {"case_id": "case_scale_ai", "name": "Scale AI", "link": "https://scale.com", "reasoning": "ML fit"},
        {"case_id": "case_deverus", "name": "Deverus", "link": "", "reasoning": "data fit"},
    ],
    "hook_options": HOOK_OPTIONS,
    "selected_hook": HOOK_OPTIONS[0]["text"],  # highest score = 9
    "cover_letter": "From what I see, your biggest risk is shipping ML features without a data pipeline that can keep up.\n\nHere is the rest of the letter.",
    "screening_answers": "",
}

MOCK_CASES = [{"id": "case_scale_ai", "name": "Scale AI", "link": "https://scale.com", "score": 0.9}]


async def run_tests():
    passed = 0

    # TEST 1 — hook_options present in JSON schema prompt
    captured = {}

    async def capture_create(**kwargs):
        captured["prompt"] = kwargs["messages"][1]["content"]
        return make_openai_response(MOCK_EVAL_WITH_HOOKS)

    with patch("cover_letter_generator.AsyncOpenAI") as MockOAI:
        inst = MagicMock()
        inst.chat.completions.create = capture_create
        MockOAI.return_value = inst
        await clg.evaluate_job_and_generate(
            rag_query="We need an ML engineer with LLM/RAG/Python skills.",
            best_cases_with_content=[],
            user_profiles=clg.user_profiles,
            selection_rules=clg.selection_rules,
            cover_letter_rules=clg.cover_letter_rules,
            letter_template=clg.letter_template,
            api_key="sk-test",
        )

    assert "hook_options" in captured["prompt"], "hook_options should appear in prompt schema"
    assert "selected_hook" in captured["prompt"], "selected_hook should appear in prompt schema"
    assert "specificity_score" in captured["prompt"], "specificity_score should appear in prompt"
    assert "Hook Generation" in captured["prompt"], "Step 4 Hook Generation should be in prompt"
    print("TEST 1 PASSED: hook_options, selected_hook, specificity_score appear in LLM prompt")
    passed += 1

    # TEST 2 — hook_options step instructs LLM to generate 3 hooks and auto-select
    assert "exactly 3 distinct hook" in captured["prompt"], "Prompt should request exactly 3 hooks"
    assert "Auto-select" in captured["prompt"], "Prompt should instruct auto-selection"
    assert "Never starts with" in captured["prompt"] or "never start" in captured["prompt"].lower(), \
        "Hook rules about 'Most...' should be in prompt"
    print("TEST 2 PASSED: hook generation step instructs 3 hooks, auto-select, and hook rules")
    passed += 1

    # TEST 3 — step 5 references selected_hook for Block 1
    assert "selected_hook" in captured["prompt"] and "Block 1" in captured["prompt"], \
        "Step 5 should instruct LLM to use selected_hook as Block 1"
    print("TEST 3 PASSED: Cover Letter step references selected_hook as Block 1")
    passed += 1

    # TEST 4 — evaluate_job_and_generate returns hook_options and selected_hook
    with patch("cover_letter_generator.AsyncOpenAI") as MockOAI:
        inst = MagicMock()
        inst.chat.completions.create = AsyncMock(return_value=make_openai_response(MOCK_EVAL_WITH_HOOKS))
        MockOAI.return_value = inst
        result = await clg.evaluate_job_and_generate(
            rag_query="test",
            best_cases_with_content=[],
            user_profiles=clg.user_profiles,
            selection_rules=clg.selection_rules,
            cover_letter_rules=clg.cover_letter_rules,
            letter_template=clg.letter_template,
            api_key="sk-test",
        )

    assert "hook_options" in result, "Result should contain hook_options"
    assert len(result["hook_options"]) == 3, f"Expected 3 hooks, got {len(result['hook_options'])}"
    assert "selected_hook" in result, "Result should contain selected_hook"
    assert result["selected_hook"] == HOOK_OPTIONS[0]["text"], "selected_hook should be the highest-scoring hook"
    print("TEST 4 PASSED: evaluate_job_and_generate returns 3 hook_options and selected_hook")
    passed += 1

    # TEST 5 — process_job single mode surfaces hook_options in result
    with (
        patch("cover_letter_generator.rag") as mock_rag,
        patch("cover_letter_generator.detect_dual_profile", AsyncMock(return_value=False)),
        patch("cover_letter_generator.evaluate_job_and_generate", AsyncMock(return_value=MOCK_EVAL_WITH_HOOKS)),
        patch("cover_letter_generator.load_case_content", AsyncMock(return_value="content")),
        patch("cover_letter_generator.append_to_google_sheet"),
    ):
        mock_rag.retrieve_cases = AsyncMock(return_value=MOCK_CASES)
        result = await clg.process_job("We need an ML engineer.")

    assert result.get("hook_options"), "process_job result should contain hook_options"
    assert result.get("selected_hook") == HOOK_OPTIONS[0]["text"]
    print("TEST 5 PASSED: process_job surfaces hook_options and selected_hook in single mode")
    passed += 1

    # TEST 6 — slack format_result_message renders hook options block
    import slack_bot
    msg = slack_bot.format_result_message(MOCK_EVAL_WITH_HOOKS)
    assert "🪝" in msg, "Hook options block should start with 🪝"
    assert "✅" in msg, "Selected hook should be marked with ✅"
    assert "score: 9" in msg, "Highest specificity score should be shown"
    assert "score: 7" in msg and "score: 6" in msg, "All hook scores should be shown"
    # The selected hook (score 9) must be ✅, others must not be
    lines = [l for l in msg.splitlines() if "score:" in l]
    assert len(lines) == 3, f"Expected 3 hook lines, got {len(lines)}"
    selected_lines = [l for l in lines if "✅" in l]
    assert len(selected_lines) == 1, "Exactly one hook should be marked selected"
    assert "score: 9" in selected_lines[0], "The ✅ hook should be the one with score 9"
    print("TEST 6 PASSED: slack format_result_message renders 3 hooks with checkmark on the auto-selected one")
    passed += 1

    # TEST 7 — hook block appears before the cover letter in the Slack message
    hook_pos = msg.find("🪝")
    letter_pos = msg.find("📝")
    assert hook_pos < letter_pos, "Hook options block should appear before the cover letter"
    print("TEST 7 PASSED: hook options block appears before the cover letter in Slack message")
    passed += 1

    # TEST 8 — when hook_options absent, no hook block rendered (backwards compat)
    result_no_hooks = {k: v for k, v in MOCK_EVAL_WITH_HOOKS.items() if k not in ("hook_options", "selected_hook")}
    msg_no_hooks = slack_bot.format_result_message(result_no_hooks)
    assert "🪝" not in msg_no_hooks, "No hook block should appear when hook_options is absent"
    print("TEST 8 PASSED: no hook block rendered when hook_options absent (backwards compat)")
    passed += 1

    print(f"\n{'='*50}")
    print(f"All {passed} tests passed.")


asyncio.run(run_tests())
