# CoverLetter/slack_bot.py
import os
import sys
import asyncio
import logging
from pathlib import Path
from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

# Добавляем корень проекта в sys.path, чтобы импортировать соседний модуль
ROOT_DIR = Path(__file__).parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from cover_letter_generator import process_job


def format_result_message(result: dict, header: str = "") -> str:
    cover_letter = result.get("cover_letter")
    screening = result.get("screening_answers")
    job_eval = result.get("job_evaluation", {})

    blocks = []
    if header:
        blocks.append(f"*{header}*")
    if job_eval.get("decision") == "PASS":
        blocks.append(f"✅ *Решение:* PASS\n_{job_eval.get('reasoning')}_")
    else:
        blocks.append(f"❌ *Решение:* SKIP\n_{job_eval.get('reasoning')}_")

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

@slack_app.message("")
def handle_direct_message(message, say):
    logger.info(f"📨 Получено сообщение: {message}")
    if message.get("channel_type") != "im":
        return
    if "bot_id" in message:
        return

    user_text = message.get("text", "").strip()
    if not user_text:
        say("Пожалуйста, отправьте описание вакансии.")
        return

    say("⏳ Обрабатываю ваш запрос... Это может занять до минуты.")

    # Асинхронно вызываем process_job из синхронного обработчика
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(process_job(user_text))
    except Exception as e:
        logger.exception("Ошибка при вызове process_job")
        say(f"❌ Внутренняя ошибка: {str(e)}")
        return
    finally:
        loop.close()

    if "error" in result:
        say(f"❌ Ошибка: {result['error']}")
        return

    if result.get("dual"):
        say("🔀 *Двойной профиль — два письма независимо*")
        say(format_result_message(result.get("tilek", {}), header="🤖 Tilek Letter:"))
        say(format_result_message(result.get("victoria", {}), header="💻 Victoria Letter:"))
        return

    say(format_result_message(result))

if __name__ == "__main__":
    handler = SocketModeHandler(slack_app, SLACK_APP_TOKEN)
    logger.info("⚡️ Slack‑бот запущен и слушает сообщения...")
    handler.start()
