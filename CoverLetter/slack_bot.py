# slack_bot.py
import os
import requests
import logging
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from dotenv import load_dotenv

load_dotenv()

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Slack токены
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
SLACK_APP_TOKEN = os.environ.get("SLACK_APP_TOKEN")
if not SLACK_BOT_TOKEN or not SLACK_APP_TOKEN:
    raise ValueError("Missing Slack tokens in .env")

# URL вашего API (локально или удалённо)
API_URL = os.environ.get("API_URL", "http://localhost:8000/generate")

app = App(token=SLACK_BOT_TOKEN)


def call_generation_api(job_description: str) -> dict:
    """Отправляет описание вакансии в FastAPI и возвращает результат."""
    try:
        response = requests.post(
            API_URL,
            json={"job_description": job_description},
            timeout=120  # генерация может занимать время
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"API request failed: {e}")
        return {"error": str(e)}


@app.message("")
def handle_direct_message(message, say, client):
    print(f"Получено сообщение: {message}")

    # Реагируем только на сообщения в личном чате (не в каналах)
    if message.get("channel_type") != "im":
        return
    # Игнорируем сообщения от самого бота
    if "bot_id" in message:
        return

    user_text = message.get("text", "").strip()
    if not user_text:
        say("Пожалуйста, отправьте описание вакансии.")
        return

    # Информируем пользователя о начале обработки
    say("⏳ Обрабатываю ваш запрос... Это может занять до минуты.")

    # Вызываем API
    result = call_generation_api(user_text)

    if "error" in result:
        say(f"❌ Ошибка при обработке: {result['error']}")
        return

    # Формируем ответное сообщение
    cover_letter = result.get("cover_letter")
    screening = result.get("screening_answers")
    job_eval = result.get("job_evaluation", {})

    # Собираем блоки для отправки
    blocks = []
    if job_eval.get("decision") == "PASS":
        blocks.append(f"✅ *Решение:* PASS\n_{job_eval.get('reasoning')}_")
    else:
        blocks.append(f"❌ *Решение:* SKIP\n_{job_eval.get('reasoning')}_")

    if cover_letter:
        blocks.append(f"📝 *Письмо-отклик:*\n```{cover_letter}```")
    if screening:
        blocks.append(f"❓ *Ответы на вопросы:*\n```{screening}```")

    # Выбираем выбранный профиль, кейсы (опционально)
    selected = result.get("selected_profile", {})
    if selected.get("name"):
        blocks.append(f"👤 *Выбранный профиль:* {selected['name']} – {selected.get('reasoning', '')}")

    cases = result.get("selected_cases", [])
    if cases:
        cases_text = "\n".join([f"• {c['name']} – {c.get('reasoning', '')}" for c in cases])
        blocks.append(f"📂 *Выбранные кейсы:*\n{cases_text}")

    # Отправляем всё одним сообщением (если слишком длинное, можно разбить)
    final_message = "\n\n".join(blocks)
    if len(final_message) > 4000:
        # Обрезаем до 4000 символов (ограничение Slack)
        final_message = final_message[:3950] + "\n... (сообщение обрезано)"
    say(final_message)


if __name__ == "__main__":
    handler = SocketModeHandler(app, SLACK_APP_TOKEN)
    logger.info("⚡️ Бот запущен и слушает сообщения...")
    handler.start()
