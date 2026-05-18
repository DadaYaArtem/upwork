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

from cover_letter_generator import process_job, refine_letter, OPENAI_API_KEY


# -----------------------------------------------------------------------------
# Per-user state (in-memory). Достаточно для одного процесса бота.
# Если бот рестартует - юзер просто отправит вакансию ещё раз.
# -----------------------------------------------------------------------------
_user_last_result: dict[str, dict] = {}


def _save_last_result(user_id: str, result: dict) -> None:
    _user_last_result[user_id] = result


def _get_last_result(user_id: str) -> dict | None:
    return _user_last_result.get(user_id)


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
    refine_instruction = detect_refine_instruction(user_text)
    if refine_instruction:
        logger.info(f"🔧 Refine для {user_id}: {refine_instruction[:80]}")
        try:
            _handle_refine(user_id, refine_instruction, say)
        except Exception as e:
            logger.exception("refine failed")
            say(f"❌ Ошибка при правке: {e}")
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
        say(format_result_message(result.get("victoria", {}), header="💻 Victoria Letter:",
                                  show_screening_qs=False))
        return

    say(format_result_message(result))


if __name__ == "__main__":
    handler = SocketModeHandler(slack_app, SLACK_APP_TOKEN)
    logger.info("⚡️ Slack-бот запущен и слушает сообщения...")
    handler.start()