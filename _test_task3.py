"""End-to-end tests for Task 3 (dual-profile mode) using mocks only — no real API calls."""
import sys, os, json, asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from pathlib import Path

os.environ.setdefault("OPENAI_API_KEY", "sk-test-dummy")
os.environ.setdefault("SLACK_BOT_TOKEN", "xoxb-dummy")
os.environ.setdefault("SLACK_APP_TOKEN", "xapp-dummy")

sys.path.insert(0, str(Path(__file__).parent / "CoverLetter"))
sys.path.insert(0, str(Path(__file__).parent))

import cover_letter_generator as clg


def make_openai_response(content: dict):
    r = MagicMock()
    r.choices = [MagicMock()]
    r.choices[0].message.content = json.dumps(content)
    return r


DUAL_JOB = "We need an ML engineer with Python/RAG/LLM AND React/Node.js full-stack developer."
SINGLE_JOB = "We need a React developer for our SaaS product."

MOCK_TILEK_EVAL = {
    "job_evaluation": {"decision": "PASS", "reasoning": "AI match", "flags": ""},
    "selected_profile": {"name": "Tilek Chubakov", "reasoning": "AI match"},
    "selected_cases": [
        {"case_id": "case_scale_ai", "name": "Scale AI", "link": "https://scale.com", "reasoning": "ML fit"},
        {"case_id": "case_deverus", "name": "Deverus", "link": "", "reasoning": "data fit"},
    ],
    "cover_letter": "Tilek test letter.",
    "screening_answers": "",
}

MOCK_VICTORIA_EVAL = {
    "job_evaluation": {"decision": "PASS", "reasoning": "Fullstack match", "flags": ""},
    "selected_profile": {"name": "Victoria", "reasoning": "fullstack match"},
    "selected_cases": [
        {"case_id": "case_classful", "name": "Classful", "link": "https://classful.com", "reasoning": "SaaS fit"},
        {"case_id": "case_flink", "name": "Flink", "link": "", "reasoning": "Node fit"},
    ],
    "cover_letter": "Victoria test letter.",
    "screening_answers": "",
}

MOCK_CASES = [{"id": "case_scale_ai", "name": "Scale AI", "link": "https://scale.com", "score": 0.9}]


async def run_tests():
    passed = 0

    # TEST 1 — detect_dual_profile returns True
    with patch("cover_letter_generator.AsyncOpenAI") as MockOAI:
        inst = MagicMock()
        inst.chat.completions.create = AsyncMock(
            return_value=make_openai_response({"dual_profile": True})
        )
        MockOAI.return_value = inst
        result = await clg.detect_dual_profile(DUAL_JOB, "sk-test")
    assert result is True, f"Expected True, got {result}"
    print("TEST 1 PASSED: detect_dual_profile returns True for dual job")
    passed += 1

    # TEST 2 — detect_dual_profile returns False
    with patch("cover_letter_generator.AsyncOpenAI") as MockOAI:
        inst = MagicMock()
        inst.chat.completions.create = AsyncMock(
            return_value=make_openai_response({"dual_profile": False})
        )
        MockOAI.return_value = inst
        result = await clg.detect_dual_profile(SINGLE_JOB, "sk-test")
    assert result is False, f"Expected False, got {result}"
    print("TEST 2 PASSED: detect_dual_profile returns False for single job")
    passed += 1

    # TEST 3 — allowed_profiles filters the profiles sent to the LLM
    captured = {}

    async def capture_create(**kwargs):
        captured["prompt"] = kwargs["messages"][1]["content"]
        return make_openai_response(MOCK_TILEK_EVAL)

    with patch("cover_letter_generator.AsyncOpenAI") as MockOAI:
        inst = MagicMock()
        inst.chat.completions.create = capture_create
        MockOAI.return_value = inst
        await clg.evaluate_job_and_generate(
            rag_query="test",
            best_cases_with_content=[],
            user_profiles=clg.user_profiles,
            selection_rules=clg.selection_rules,
            cover_letter_rules=clg.cover_letter_rules,
            letter_template=clg.letter_template,
            api_key="sk-test",
            allowed_profiles=["Tilek Chubakov"],
        )
    # Victoria's unique field only appears when her profile is included in the JSON
    assert "min_salary_agency_usd" not in captured["prompt"], \
        "Victoria's profile (min_salary_agency_usd) should be filtered out when allowed_profiles=['Tilek Chubakov']"
    assert "Tilek Chubakov" in captured["prompt"], "Tilek should be present in prompt"
    print("TEST 3 PASSED: allowed_profiles filters profiles sent to LLM")
    passed += 1

    # TEST 4 — forbidden_case_ids injected into prompt
    async def capture_victoria(**kwargs):
        captured["prompt"] = kwargs["messages"][1]["content"]
        return make_openai_response(MOCK_VICTORIA_EVAL)

    with patch("cover_letter_generator.AsyncOpenAI") as MockOAI:
        inst = MagicMock()
        inst.chat.completions.create = capture_victoria
        MockOAI.return_value = inst
        await clg.evaluate_job_and_generate(
            rag_query="test",
            best_cases_with_content=[],
            user_profiles=clg.user_profiles,
            selection_rules=clg.selection_rules,
            cover_letter_rules=clg.cover_letter_rules,
            letter_template=clg.letter_template,
            api_key="sk-test",
            allowed_profiles=["Victoria"],
            forbidden_case_ids=["case_scale_ai", "case_deverus"],
        )
    assert "case_scale_ai" in captured["prompt"], "Forbidden ID case_scale_ai missing from prompt"
    assert "case_deverus" in captured["prompt"], "Forbidden ID case_deverus missing from prompt"
    assert "do NOT select" in captured["prompt"], "Forbidden instruction missing from prompt"
    print("TEST 4 PASSED: forbidden_case_ids injected into LLM prompt")
    passed += 1

    # TEST 5 — process_job dual path returns correct structure
    call_count = [0]

    async def mock_eval(**kwargs):
        call_count[0] += 1
        if kwargs.get("allowed_profiles") == ["Tilek Chubakov"]:
            return MOCK_TILEK_EVAL
        return MOCK_VICTORIA_EVAL

    with (
        patch("cover_letter_generator.rag") as mock_rag,
        patch("cover_letter_generator.detect_dual_profile", AsyncMock(return_value=True)),
        patch("cover_letter_generator.evaluate_job_and_generate", mock_eval),
        patch("cover_letter_generator.load_case_content", AsyncMock(return_value="content")),
        patch("cover_letter_generator.append_to_google_sheet"),
    ):
        mock_rag.retrieve_cases = AsyncMock(return_value=MOCK_CASES)
        result = await clg.process_job(DUAL_JOB)

    assert result.get("dual") is True, f"Expected dual=True, got {result.get('dual')}"
    assert "tilek" in result and "victoria" in result, "Missing tilek/victoria keys"
    assert result["tilek"]["selected_profile"]["name"] == "Tilek Chubakov"
    assert result["victoria"]["selected_profile"]["name"] == "Victoria"
    assert call_count[0] == 2, f"Expected 2 LLM calls, got {call_count[0]}"
    print("TEST 5 PASSED: process_job dual mode calls evaluate twice and returns dual structure")
    passed += 1

    # TEST 6 — process_job single path unchanged
    call_count[0] = 0

    async def mock_eval_single(**kwargs):
        call_count[0] += 1
        return MOCK_TILEK_EVAL

    with (
        patch("cover_letter_generator.rag") as mock_rag,
        patch("cover_letter_generator.detect_dual_profile", AsyncMock(return_value=False)),
        patch("cover_letter_generator.evaluate_job_and_generate", mock_eval_single),
        patch("cover_letter_generator.load_case_content", AsyncMock(return_value="content")),
        patch("cover_letter_generator.append_to_google_sheet"),
    ):
        mock_rag.retrieve_cases = AsyncMock(return_value=MOCK_CASES)
        result = await clg.process_job(SINGLE_JOB)

    assert "dual" not in result, "Single mode should NOT have dual key"
    assert result["selected_profile"]["name"] == "Tilek Chubakov"
    assert call_count[0] == 1, f"Expected 1 LLM call, got {call_count[0]}"
    print("TEST 6 PASSED: process_job single mode runs one LLM call, no dual key")
    passed += 1

    # TEST 7 — Tilek's selected case IDs are passed as forbidden to Victoria
    victoria_forbidden = []

    async def mock_eval_capture(**kwargs):
        if kwargs.get("allowed_profiles") == ["Tilek Chubakov"]:
            return MOCK_TILEK_EVAL
        victoria_forbidden.extend(kwargs.get("forbidden_case_ids") or [])
        return MOCK_VICTORIA_EVAL

    with (
        patch("cover_letter_generator.rag") as mock_rag,
        patch("cover_letter_generator.detect_dual_profile", AsyncMock(return_value=True)),
        patch("cover_letter_generator.evaluate_job_and_generate", mock_eval_capture),
        patch("cover_letter_generator.load_case_content", AsyncMock(return_value="content")),
        patch("cover_letter_generator.append_to_google_sheet"),
    ):
        mock_rag.retrieve_cases = AsyncMock(return_value=MOCK_CASES)
        await clg.process_job(DUAL_JOB)

    assert "case_scale_ai" in victoria_forbidden, "case_scale_ai should be forbidden for Victoria"
    assert "case_deverus" in victoria_forbidden, "case_deverus should be forbidden for Victoria"
    print("TEST 7 PASSED: Tilek selected case IDs passed as forbidden to Victoria call")
    passed += 1

    # TEST 8 — Tilek rate in user_profiles is $50
    tilek = next(p for p in clg.user_profiles if p["name"] == "Tilek Chubakov")
    assert tilek["min_salary_per_hour_usd"] == 50, f"Tilek rate should be 50, got {tilek['min_salary_per_hour_usd']}"
    print("TEST 8 PASSED: Tilek min_salary_per_hour_usd == 50")
    passed += 1

    # TEST 9 — Victoria solo rate $40, agency rate $35
    victoria = next(p for p in clg.user_profiles if p["name"] == "Victoria")
    assert victoria["min_salary_per_hour_usd"] == 40, f"Victoria solo rate should be 40, got {victoria['min_salary_per_hour_usd']}"
    assert victoria["min_salary_agency_usd"] == 35, f"Victoria agency rate should be 35, got {victoria.get('min_salary_agency_usd')}"
    print("TEST 9 PASSED: Victoria min_salary_per_hour_usd==40, min_salary_agency_usd==35")
    passed += 1

    print(f"\n{'='*50}")
    print(f"All {passed} tests passed.")


asyncio.run(run_tests())
