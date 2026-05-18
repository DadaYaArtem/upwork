# CoverLetter/slack_bot.py
# -----------------------------------------------------------------------------
# Изменения относительно прежней версии:
#  1. Per-user state: последний результат хранится в памяти бота.
#     Это позволяет команды "translate to english", "shorter", "more technical",
#     "regenerate hook" обрабатывать через refine_letter БЕЗ повторного RAG -
#     раньше любое сообщение запускало process_job с нуля и порождало
#     "новый пропоузал" вместо правки.
#  2. Команды распознаются явным префиксом или по ключевым словам.
#  3. Screening questions показываются в Slack как отдельный блок, чтобы было видно,
#     что бот их вообще нашёл.
# -----------------------------------------------------------------------------

import os
import sys
import asyncio
import logging
import re
from pathlib import Path
from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

ROOT_DIR = Path(__file__).parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from cover_letter_generator import process_job, refine_letter, answer_about_last_result, OPENAI_API_KEY


# -----------------------------------------------------------------------------
# Per-user state (in-memory). Достаточно для одного процесса бота.
# Если бот рестартует - юзер просто отправит вакансию ещё раз.
# -----------------------------------------------------------------------------
_user_last_result: dict[str, dict] = {}
_user_pending_clarification: dict[str, dict] = {}


def _save_last_result(user_id: str, result: dict) -> None:
    _user_last_result[user_id] = result


def _get_last_result(user_id: str) -> dict | None:
    return _user_last_result.get(user_id)


def _save_pending_clarification(user_id: str, pending: dict) -> None:
    _user_pending_clarification[user_id] = pending


def _pop_pending_clarification(user_id: str) -> dict | None:
    return _user_pending_clarification.pop(user_id, None)


# -----------------------------------------------------------------------------
# Распознавание команд-уточнений
# -----------------------------------------------------------------------------
REFINE_KEYWORDS = [
    # перевод
    ("translate", "Translate the letter and answers fully to English. Do not regenerate, only translate."),
    ("переведи", "Translate the letter and answers fully to English. Do not regenerate, only translate."),
    ("english", "Translate the letter and answers fully to English. Do not regenerate, only translate."),
    ("на англ", "Translate the letter and answers fully to English. Do not regenerate, only translate."),

    # короче
    ("shorter", "Make the letter shorter while keeping both cases and the closing intact. Aim for 140 words."),
    ("короче", "Make the letter shorter while keeping both cases and the closing intact. Aim for 140 words."),

    # длиннее
    ("longer", "Make the letter slightly longer (up to 200 words) by expanding the case descriptions with concrete technical detail."),
    ("длиннее", "Make the letter slightly longer (up to 200 words) by expanding the case descriptions with concrete technical detail."),

    # больше технических деталей
    ("more technical", "Add more concrete technical detail to the case descriptions and to the bridge sentence. Keep total length under 200 words."),
    ("more technical detail", "Add more concrete technical detail to the case descriptions and to the bridge sentence. Keep total length under 200 words."),
    ("техничнее", "Add more concrete technical detail to the case descriptions and to the bridge sentence. Keep total length under 200 words."),

    # менее формально
    ("less formal", "Make the tone more direct and conversational, drop any corporate phrasing."),
    ("менее формально", "Make the tone more direct and conversational, drop any corporate phrasing."),

    # перегенерировать hook
    ("regenerate hook", "Replace the opening hook with a new one that references a different concrete detail from the job description. Keep everything else."),
    ("другой hook", "Replace the opening hook with a new one that references a different concrete detail from the job description. Keep everything else."),
    ("новый hook", "Replace the opening hook with a new one that references a different concrete detail from the job description. Keep everything else."),
]


def detect_refine_instruction(text: str) -> str | None:
    """
    Если сообщение похоже на правку (короткое + содержит ключевое слово),
    возвращает английскую инструкцию для refine_letter. Иначе None.
    """
    t = text.strip().lower()
    if len(t) > 200:
        # длинное сообщение - скорее всего job description, не команда
        return None
    for kw, instruction in REFINE_KEYWORDS:
        if kw in t:
            return instruction
    # Универсальный fallback: если сообщение явно начинается с глагола-инструкции
    if re.match(r"^(make it|please make|сделай|перепиши|rewrite|adjust|change)\b", t):
        return text.strip()
    return None


def looks_like_new_job(text: str) -> bool:
    t = text.strip().lower()
    if len(t) > 700 or t.count("\n") >= 10:
        return True

    job_markers = [
        "job description", "we are looking", "we need", "looking for", "requirements",
        "responsibilities", "budget", "hourly", "fixed price", "upwork", "proposal",
        "about the role", "scope of work", "candidate", "developer needed",
    ]
    marker_count = sum(1 for marker in job_markers if marker in t)
    return len(t) > 250 and marker_count >= 2


def _profile_from_text(text: str) -> str | None:
    t = text.lower()
    if re.search(r"\b(tilek|тайлек)\b", t):
        return "tilek"
    if re.search(r"\b(victoria|vika|вика|виктория)\b", t):
        return "victoria"
    return None


def _target_from_text(text: str) -> dict:
    t = text.lower()

    variant_match = re.search(r"(?:вариант|variant)\s*([123])\b", t)
    if not variant_match:
        variant_match = re.search(r"\b([123])\s*(?:вариант|variant)\b", t)
    if variant_match:
        return {"target_type": "variant", "variant_index": int(variant_match.group(1)) - 1}

    if re.search(r"\b(main|основн\w*|обычн\w*)\b", t) or "письмо-отклик" in t:
        return {"target_type": "main", "variant_index": None}

    if re.search(r"\b(screening|answers?)\b", t) or re.search(r"\b(ответ\w*|вопрос\w*)\b", t):
        return {"target_type": "screening", "variant_index": None}

    return {"target_type": None, "variant_index": None}


def _edit_instruction_from_text(text: str) -> str | None:
    known = detect_refine_instruction(text)
    if known:
        return known

    t = text.lower()
    if "короч" in t:
        return "Make the selected text shorter and more concise. Keep the core cases, CTA, and signature."
    if "длинн" in t:
        return "Make the selected text slightly longer by adding concrete job-specific and technical detail."
    if "технич" in t or "детал" in t:
        return "Add more concrete technical detail while keeping the text concise and specific to the job."
    if "менее формаль" in t or "неформаль" in t or "разговорн" in t:
        return "Make the tone more direct and conversational, dropping corporate phrasing."
    if "формаль" in t:
        return "Make the tone more polished and professional without making it generic."
    if "переп" in t or "rewrite" in t:
        return text.strip()
    if re.search(r"\b(make|change|adjust|shorter|longer|improve|rewrite|add|remove)\b", t):
        return text.strip()
    if re.search(r"\b(сделай|измени|добавь|убери|улучши|сократи)\b", t):
        return text.strip()
    return None


def _is_question_about_result(text: str) -> bool:
    t = text.lower().strip()
    question_terms = [
        "?", "какой", "какая", "какие", "почему", "зачем", "что лучше", "лучше",
        "why", "which", "what", "explain", "объясни", "поясни",
    ]
    return any(term in t for term in question_terms)


def classify_followup_message(text: str, last_result: dict | None) -> dict:
    if looks_like_new_job(text) or not last_result:
        return {"action": "new_job"}

    instruction = _edit_instruction_from_text(text)
    if instruction:
        target = _target_from_text(text)
        profile_key = _profile_from_text(text)
        if target["target_type"] is None:
            return {
                "action": "clarify",
                "missing": "target",
                "instruction": instruction,
                "original_text": text,
                "message": "Что именно поправить: основное письмо, вариант 1/2/3 или ответы на вопросы?",
            }
        if last_result.get("dual") and not profile_key:
            return {
                "action": "clarify",
                "missing": "profile",
                "instruction": instruction,
                "original_text": text,
                "target_type": target["target_type"],
                "variant_index": target["variant_index"],
                "message": "Для какого профиля поправить: Tilek или Victoria?",
            }
        return {
            "action": "edit",
            "instruction": instruction,
            "target_type": target["target_type"],
            "variant_index": target["variant_index"],
            "profile_key": profile_key,
        }

    if _is_question_about_result(text):
        return {"action": "question", "question": text}

    return {"action": "new_job"}


def resolve_pending_followup(pending: dict, reply_text: str, last_result: dict | None) -> dict:
    if looks_like_new_job(reply_text):
        return {"action": "new_job"}

    merged_text = f"{pending.get('original_text', '')} {reply_text}".strip()
    route = classify_followup_message(merged_text, last_result)
    if route.get("action") == "edit":
        return route

    if pending.get("missing") == "target":
        target = _target_from_text(reply_text)
        profile_key = _profile_from_text(reply_text)
        if target["target_type"] is None:
            route["message"] = "Я всё ещё не понял цель. Напиши, например: `вариант 3`, `основное письмо` или `ответы`."
            return route
        if last_result and last_result.get("dual") and not profile_key:
            return {
                "action": "clarify",
                "missing": "profile",
                "instruction": pending["instruction"],
                "original_text": merged_text,
                "target_type": target["target_type"],
                "variant_index": target["variant_index"],
                "message": "Ок, понял цель. Теперь уточни профиль: Tilek или Victoria?",
            }
        return {
            "action": "edit",
            "instruction": pending["instruction"],
            "target_type": target["target_type"],
            "variant_index": target["variant_index"],
            "profile_key": profile_key,
        }

    if pending.get("missing") == "profile":
        profile_key = _profile_from_text(reply_text)
        if not profile_key:
            route["message"] = "Я всё ещё не понял профиль. Напиши `Tilek` или `Victoria`."
            return route
        return {
            "action": "edit",
            "instruction": pending["instruction"],
            "target_type": pending["target_type"],
            "variant_index": pending["variant_index"],
            "profile_key": profile_key,
        }

    return route


# -----------------------------------------------------------------------------
# Форматирование сообщения для Slack
# -----------------------------------------------------------------------------
def format_result_message(result: dict, header: str = "", show_screening_qs: bool = True) -> str:
    cover_letter = result.get("cover_letter")
    screening = result.get("screening_answers")
    job_eval = result.get("job_evaluation", {})
    screening_qs = result.get("_screening_questions") or []

    blocks = []
    if header:
        blocks.append(f"*{header}*")
    if job_eval.get("decision") == "PASS":
        blocks.append(f"✅ *Решение:* PASS\n_{job_eval.get('reasoning')}_")
    else:
        blocks.append(f"❌ *Решение:* SKIP\n_{job_eval.get('reasoning')}_")

    if show_screening_qs and screening_qs:
        qs_lines = "\n".join(f"{i+1}. {q}" for i, q in enumerate(screening_qs))
        blocks.append(f"📋 *Обнаруженные screening-вопросы ({len(screening_qs)}):*\n{qs_lines}")

    hook_options = result.get("hook_options", [])
    selected_hook = result.get("selected_hook", "")
    if hook_options:
        lines = []
        for i, h in enumerate(hook_options, 1):
            marker = "✅" if h.get("text") == selected_hook else "  "
            lines.append(f"{marker} {i}. _(score: {h.get('specificity_score', '?')})_ {h.get('text', '')}")
        blocks.append("🪝 *Hook options (✅ = auto-selected):*\n" + "\n".join(lines))

    if cover_letter:
        blocks.append(f"📝 *Письмо-отклик:*\n```{cover_letter}```")
    if screening:
        blocks.append(f"❓ *Ответы на вопросы:*\n```{screening}```")

    selected = result.get("selected_profile", {})
    if selected.get("name"):
        blocks.append(f"👤 *Выбранный профиль:* {selected['name']} – {selected.get('reasoning', '')}")

    cases = result.get("selected_cases", [])
    if cases:
        cases_text = "\n".join([f"• {c['name']} – {c.get('reasoning', '')}" for c in cases])
        blocks.append(f"📂 *Выбранные кейсы:*\n{cases_text}")

    msg = "\n\n".join(blocks)
    if len(msg) > 4000:
        msg = msg[:3950] + "\n... (сообщение обрезано)"
    return msg


def format_proposal_variant_messages(result: dict, header: str = "Proposal variants") -> list[str]:
    variants = result.get("proposal_variants") or []
    if not isinstance(variants, list):
        return []

    messages = []
    for idx, variant in enumerate(variants[:3], 1):
        if not isinstance(variant, dict):
            continue
        cover_letter = variant.get("cover_letter")
        if not cover_letter:
            continue

        structure = variant.get("structure_name") or f"Variant {idx}"
        angle = variant.get("angle") or ""
        when_to_use = variant.get("when_to_use") or ""

        blocks = [f"*{header} - {idx}. {structure}*"]
        if angle:
            blocks.append(f"*Angle:* {angle}")
        if when_to_use:
            blocks.append(f"*When to use:* {when_to_use}")
        blocks.append(f"```{cover_letter}```")

        msg = "\n\n".join(blocks)
        if len(msg) > 4000:
            msg = msg[:3950] + "\n... (variant message truncated)"
        messages.append(msg)

    return messages


def say_proposal_variants(result: dict, say, header: str = "Proposal variants") -> None:
    for msg in format_proposal_variant_messages(result, header=header):
        say(msg)


def format_single_variant_message(variant: dict, variant_index: int, header: str = "Updated proposal variant") -> str:
    structure = variant.get("structure_name") or f"Variant {variant_index + 1}"
    angle = variant.get("angle") or ""
    cover_letter = variant.get("cover_letter") or ""

    blocks = [f"*{header} - {variant_index + 1}. {structure}*"]
    if angle:
        blocks.append(f"*Angle:* {angle}")
    blocks.append(f"```{cover_letter}```")
    msg = "\n\n".join(blocks)
    if len(msg) > 4000:
        msg = msg[:3950] + "\n... (variant message truncated)"
    return msg


def _result_for_profile(last_result: dict, profile_key: str | None) -> dict | None:
    if not last_result.get("dual"):
        return last_result
    if profile_key in ("tilek", "victoria"):
        return last_result.get(profile_key, {})
    return None


def _handle_chat_edit(user_id: str, route: dict, say) -> None:
    last = _get_last_result(user_id)
    if not last:
        say("У меня нет предыдущего результата для правки. Отправь описание вакансии целиком.")
        return

    target_result = _result_for_profile(last, route.get("profile_key"))
    if target_result is None:
        say("Не понял профиль для правки. Напиши `Tilek` или `Victoria`.")
        return

    instruction = route["instruction"]
    target_type = route["target_type"]

    if target_type == "variant":
        variant_index = route.get("variant_index")
        variants = target_result.get("proposal_variants") or []
        if variant_index is None or variant_index < 0 or variant_index >= len(variants):
            say("Не нашёл такой вариант. Доступны варианты 1, 2 и 3.")
            return

        variant = variants[variant_index]
        say(f"Применяю правку к варианту {variant_index + 1}...")
        refined = _run_async(refine_letter(
            previous_letter=variant.get("cover_letter", ""),
            previous_screening="",
            user_instruction=instruction + "\nApply this only to this proposal variant. Return screening_answers as an empty string.",
            api_key=OPENAI_API_KEY,
        ))
        variant["cover_letter"] = refined.get("cover_letter", variant.get("cover_letter", ""))
        _save_last_result(user_id, last)
        say(format_single_variant_message(variant, variant_index))
        return

    if target_type == "screening":
        say("Применяю правку к ответам на вопросы...")
        refined = _run_async(refine_letter(
            previous_letter="",
            previous_screening=target_result.get("screening_answers", ""),
            user_instruction=instruction + "\nApply this only to screening_answers. Return cover_letter as an empty string.",
            api_key=OPENAI_API_KEY,
        ))
        target_result["screening_answers"] = refined.get("screening_answers", target_result.get("screening_answers", ""))
        _save_last_result(user_id, last)
        say(f"*Updated screening answers:*\n```{target_result.get('screening_answers', '')}```")
        return

    say("Применяю правку к основному письму...")
    refined = _run_async(refine_letter(
        previous_letter=target_result.get("cover_letter", ""),
        previous_screening=target_result.get("screening_answers", ""),
        user_instruction=instruction,
        api_key=OPENAI_API_KEY,
    ))
    target_result["cover_letter"] = refined.get("cover_letter", target_result.get("cover_letter", ""))
    if "screening_answers" in refined:
        target_result["screening_answers"] = refined.get("screening_answers", target_result.get("screening_answers", ""))
    _save_last_result(user_id, last)
    say(f"*Updated main letter:*\n```{target_result.get('cover_letter', '')}```")


def _handle_chat_question(user_id: str, question: str, say) -> None:
    last = _get_last_result(user_id)
    if not last:
        say("У меня нет предыдущего результата, по которому можно ответить. Отправь описание вакансии целиком.")
        return
    say("Смотрю последний результат...")
    answer = _run_async(answer_about_last_result(last, question, OPENAI_API_KEY))
    say(answer)


def _handle_followup_route(user_id: str, route: dict, say) -> bool:
    action = route.get("action")
    if action == "edit":
        _handle_chat_edit(user_id, route, say)
        return True
    if action == "question":
        _handle_chat_question(user_id, route.get("question", ""), say)
        return True
    if action == "clarify":
        _save_pending_clarification(user_id, route)
        say(route.get("message", "Уточни, что именно нужно поправить."))
        return True
    return False


load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
SLACK_APP_TOKEN = os.environ.get("SLACK_APP_TOKEN")
if not SLACK_BOT_TOKEN or not SLACK_APP_TOKEN:
    raise ValueError("Missing Slack tokens")

slack_app = App(token=SLACK_BOT_TOKEN)


# -----------------------------------------------------------------------------
# Helper: запустить async-функцию из синхронного slack-handler-а
# -----------------------------------------------------------------------------
def _run_async(coro):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# -----------------------------------------------------------------------------
# Обработчик правок (refine)
# -----------------------------------------------------------------------------
def _handle_refine(user_id: str, instruction: str, say):
    last = _get_last_result(user_id)
    if not last:
        say("У меня нет предыдущего письма для этого юзера. Отправь полное описание вакансии.")
        return

    say("⏳ Применяю правку к последнему письму...")

    if last.get("dual"):
        # обновляем оба письма
        for key in ("tilek", "victoria"):
            sub = last.get(key, {})
            if not sub.get("cover_letter"):
                continue
            refined = _run_async(refine_letter(
                previous_letter=sub.get("cover_letter", ""),
                previous_screening=sub.get("screening_answers", ""),
                user_instruction=instruction,
                api_key=OPENAI_API_KEY
            ))
            sub["cover_letter"] = refined.get("cover_letter", sub.get("cover_letter", ""))
            sub["screening_answers"] = refined.get("screening_answers", sub.get("screening_answers", ""))
        _save_last_result(user_id, last)
        say("🔀 *Двойной профиль — обновлённые письма*")
        say(format_result_message(last.get("tilek", {}), header="🤖 Tilek Letter (refined):",
                                  show_screening_qs=False))
        say(format_result_message(last.get("victoria", {}), header="💻 Victoria Letter (refined):",
                                  show_screening_qs=False))
        return

    refined = _run_async(refine_letter(
        previous_letter=last.get("cover_letter", ""),
        previous_screening=last.get("screening_answers", ""),
        user_instruction=instruction,
        api_key=OPENAI_API_KEY
    ))
    last["cover_letter"] = refined.get("cover_letter", last.get("cover_letter", ""))
    last["screening_answers"] = refined.get("screening_answers", last.get("screening_answers", ""))
    _save_last_result(user_id, last)
    say(format_result_message(last, header="📝 Обновлённое письмо:", show_screening_qs=False))


# -----------------------------------------------------------------------------
# Главный обработчик DM
# -----------------------------------------------------------------------------
@slack_app.message("")
def handle_direct_message(message, say):
    logger.info(f"📨 Получено сообщение: {message}")
    if message.get("channel_type") != "im":
        return
    if "bot_id" in message or message.get("subtype"):
        return

    user_text = message.get("text", "").strip()
    user_id = message.get("user", "unknown")
    if not user_text:
        say("Пожалуйста, отправьте описание вакансии.")
        return

    # Сначала пробуем распознать как команду-правку
    last_result = _get_last_result(user_id)
    pending = _pop_pending_clarification(user_id)
    try:
        if pending and last_result:
            route = resolve_pending_followup(pending, user_text, last_result)
            if _handle_followup_route(user_id, route, say):
                return
        elif last_result:
            route = classify_followup_message(user_text, last_result)
            if _handle_followup_route(user_id, route, say):
                return
    except Exception as e:
        logger.exception("follow-up handling failed")
        say(f"❌ Ошибка при обработке уточнения: {e}")
        return

    say("⏳ Обрабатываю вакансию... Это может занять до минуты.")

    try:
        result = _run_async(process_job(user_text))
    except Exception as e:
        logger.exception("Ошибка при вызове process_job")
        say(f"❌ Внутренняя ошибка: {str(e)}")
        return

    if "error" in result:
        say(f"❌ Ошибка: {result['error']}")
        return

    _save_last_result(user_id, result)

    if result.get("dual"):
        say("🔀 *Двойной профиль — два письма независимо*")
        # screening-вопросы общие для обоих писем - показываем один раз сверху
        screening_qs = result.get("_screening_questions") or []
        if screening_qs:
            qs_lines = "\n".join(f"{i+1}. {q}" for i, q in enumerate(screening_qs))
            say(f"📋 *Обнаруженные screening-вопросы ({len(screening_qs)}):*\n{qs_lines}")
        say(format_result_message(result.get("tilek", {}), header="🤖 Tilek Letter:",
                                  show_screening_qs=False))
        say_proposal_variants(result.get("tilek", {}), say, header="Tilek proposal variants")
        say(format_result_message(result.get("victoria", {}), header="💻 Victoria Letter:",
                                  show_screening_qs=False))
        say_proposal_variants(result.get("victoria", {}), say, header="Victoria proposal variants")
        return

    say(format_result_message(result))
    say_proposal_variants(result, say)


if __name__ == "__main__":
    handler = SocketModeHandler(slack_app, SLACK_APP_TOKEN)
    logger.info("⚡️ Slack-бот запущен и слушает сообщения...")
    handler.start()
