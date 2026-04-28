# CoverLetter/slack_bot.py
import os
import threading
import uvicorn
import requests
import logging
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from dotenv import load_dotenv

# Импортируем FastAPI приложение из соседнего файла
from cover_letter_generator import app as fastapi_app

load_dotenv()

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Slack токены
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
SLACK_APP_TOKEN = os.environ.get("SLACK_APP_TOKEN")
if not SLACK_BOT_TOKEN or not SLACK_APP_TOKEN:
    raise ValueError("Missing Slack tokens in .env")

# Локальный адрес API (сервер будет запущен в том же процессе)
API_URL = "http://localhost:8000/generate"

def run_api():
    """Запуск FastAPI сервера в фоновом потоке"""
    uvicorn.run(fastapi_app, host="0.0.0.0", port=8000, log_level="warning")

# Запускаем API сервер в отдельном демон-потоке
api_thread = threading.Thread(target=run_api, daemon=True)
api_thread.start()
logger.info("⚙️ API сервер запущен на порту 8000 (фоновый режим)")

# Создаём Slack-бота
slack_app = App(token=SLACK_BOT_TOKEN)

def call_generation_api(job_description: str) -> dict:
    """Отправляет описание вакансии в локальное API."""
    try:
        response = requests.post(
            API_URL,
            json={"job_description": job_description},
            timeout=120
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"API request failed: {e}")
        return {"error": str(e)}

@slack_app.message("")
def handle_direct_message(message, say):
    logger.info(f"📨 Получено сообщение: {message}")
    # Только личные сообщения (DM)
    if message.get("channel_type") != "im":
        return
    # Игнорируем сообщения от самого бота
    if "bot_id" in message:
        return

    user_text = message.get("text", "").strip()
    if not user_text:
        say("Пожалуйста, отправьте описание вакансии.")
        return

    say("⏳ Обрабатываю ваш запрос... Это может занять до минуты.")
    result = call_generation_api(user_text)

    if "error" in result:
        say(f"❌ Ошибка: {result['error']}")
        return

    cover_letter = result.get("cover_letter")
    screening = result.get("screening_answers")
    job_eval = result.get("job_evaluation", {})

    blocks = []
    if job_eval.get("decision") == "PASS":
        blocks.append(f"✅ *Решение:* PASS\n_{job_eval.get('reasoning')}_")
    else:
        blocks.append(f"❌ *Решение:* SKIP\n_{job_eval.get('reasoning')}_")

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

    final_message = "\n\n".join(blocks)
    if len(final_message) > 4000:
        final_message = final_message[:3950] + "\n... (сообщение обрезано)"
    say(final_message)

if __name__ == "__main__":
    handler = SocketModeHandler(slack_app, SLACK_APP_TOKEN)
    logger.info("⚡️ Slack‑бот запущен и слушает сообщения...")
    handler.start()
