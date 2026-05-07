# main_api.py
import os
import asyncio
import json
import re
from pathlib import Path
from dotenv import load_dotenv
from openai import AsyncOpenAI
from typing import List, Dict, Any, Optional
import sys
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

ROOT_DIR = Path(__file__).parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend import rag

# Загрузка переменных окружения (локально из .env, на Railway — системные env vars)
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable is not set")

client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# ----------------------------------------------------------------------
# 1. Профили пользователей (полные данные)
# ----------------------------------------------------------------------
user_profiles = [
    {
        "name": "Tilek Chubakov",
        "position": "Senior AI/ML Engineer, AI Agents, LLM, MLOps, Lead Data Engineer",
        "skills": [
            "ETL/ELT pipelines with dbt and scalable data warehousing",
            "Data lake and lakehouse architectures for analytics and ML",
            "High-performance data systems optimized for cost and latency",
            "AWS, Google Cloud, and Microsoft Azure infrastructure",
            "Docker and Kubernetes for scalable deployments",
            "CI/CD pipelines with GitHub Actions and GitLab CI/CD",
            "Event-driven systems with Kinesis, Event Hubs, and RabbitMQ",
            "Docker, AWS, RAG, LangChain, LLM fine-tuning",
            "Hugging Face Transformers",
            "Prompt engineering, tool usage, and context-aware pipelines",
            "Autonomous workflows integrating APIs, databases, and enterprise systems",
            "Real-time decision systems replacing manual operations",
            "End-to-end ML pipelines with MLflow and Kubeflow",
            "Time-series forecasting with Prophet and ARIMA",
            "Gradient boosting using XGBoost, LightGBM, and CatBoost",
            "Deep learning with PyTorch and TensorFlow on GPU infrastructure",
            "Supervised and unsupervised learning for anomaly detection, fraud detection, and risk modeling",
            "Named entity recognition, classification, and semantic search",
            "Knowledge retrieval systems and question-answering pipelines",
            "Contract analysis, invoice automation, and compliance validation",
            "Multilingual NLP and morphologically rich language processing",
            "Batch and streaming pipelines using Apache Spark, Apache Kafka, and Apache Airflow",
            "Cloud-native architectures with BigQuery, Dataflow, Pub/Sub, and Snowflake",
            "Hadoop, Hive, Spark (Databricks), Kafka (Confluent), Airflow, DataFlow, Pub/Sub, Kinesis, RabbitMQ, Event Hubs, NiFi, Stitch, Great Expectations",
            "Apache Superset, Tableau, Looker, Power BI",
            "Python, C#, Scala, Java, R, JavaScript, VB.NET, C/C++, shell scripting",
            "sci-kit learn, PyTorch, TensorFlow, Kubeflow, MLflow",
            "Snowflake, MySQL, PostgreSQL, MS SQL Server, MongoDB, Cassandra, HBase, Oracle, Redis, Amazon Redshift",
            "AWS (EC2, S3, RDS, Lambda, Redshift, Glue, Kinesis)",
            "Azure (Function Apps, Event Hubs, Data Explorer, Storage)",
            "GCP (Cloud Functions, Pub/Sub, BigQuery, Cloud Run)",
            "HTML/CSS, React, Node.js, Flask, Express, FastAPI",
            "Docker, Kubernetes, Terraform",
            "Git, GitLab CI/CD, GitHub Actions, dbt, Fivetran, CircleCI, SSIS, CDK"
        ],
        "min_salary_per_hour_usd": 50,
        "priority_cases": [
            "Scale AI", "Arcade", "Deverus", "Generative AI Marketplace",
            "AI Identity Verification", "CryptoPay", "LLM Chatbot & RAG System",
            "AI Document Processing", "FinTech Payment System"
        ]
    },
    {
        "name": "Victoria",
        "position": "Senior Full-Stack Developer, React, Node.js, Scalable SaaS",
        "skills": [
            "Full-stack development with React and Node.js for scalable web applications",
            "Frontend engineering with React, Next.js, TypeScript, Redux, Tailwind CSS",
            "Backend development using Node.js and Express.js for REST API architecture",
            "SaaS platform development with multi-tenant systems and cloud infrastructure",
            "Database design with PostgreSQL and MongoDB, including performance optimization",
            "API integrations, authentication, and secure data handling",
            "Cloud deployment with AWS, Docker, and CI/CD pipelines",
            "Cross-platform development using Flutter and React Native"
        ],
        "min_salary_per_hour_usd": 40,
        "min_salary_agency_usd": 35,
        "priority_cases": [
            "Scale AI", "Arcade", "Deverus", "Generative AI Marketplace",
            "AI Identity Verification", "CryptoPay", "LLM Chatbot & RAG System",
            "AI Document Processing", "FinTech Payment System"
        ]
    },
    {
        "name": "Vicode Solutions",
        "position": "Full-Cycle Software Development Agency, React, Node.js, Scalable SaaS, 350+ developers",
        "skills": [
            "Responsive, high-performance interfaces using React, Next.js, TypeScript, Redux, and Tailwind CSS - clean architecture, intuitive UX, and optimized performance",
            "Robust server-side systems with Node.js and Express.js, secure RESTful APIs, and scalable infrastructures powered by PostgreSQL and MongoDB",
            "Authentication systems, third-party service integrations, and cloud deployment with CI/CD pipelines",
            "Full-stack SaaS application development",
            "React & Next.js frontend architecture",
            "Node.js backend systems and REST API design",
            "Database modeling with PostgreSQL and MongoDB",
            "Multi-tenant platforms and subscription-based products",
            "Payment integrations and secure authentication",
            "Cloud infrastructure and DevOps workflows"
        ],
        "min_salary_per_hour_usd": 35,
        "priority_cases": [
            "Scale AI", "Arcade", "Deverus", "Generative AI Marketplace",
            "AI Identity Verification", "CryptoPay", "LLM Chatbot & RAG System",
            "AI Document Processing", "FinTech Payment System"
        ]
    },
]

# ----------------------------------------------------------------------
# 3. Базовые правила отбора работы
# ----------------------------------------------------------------------
selection_rules = {
    "duration_months": 2,
    "preferred_work_hours_per_week": 30,
    "red_flags": """No job details, too niche stack (GHL-only, OpenClaw-only, n8n-only),
                 geo restrictions that exclude the profile, screen-recorded assessments,
                 Loom mandatory with no alternative."""
}

# ----------------------------------------------------------------------
# 4. Правила составления письма
# ----------------------------------------------------------------------
cover_letter_rules = """
Structure: each case contains project name, client URL or Upwork portfolio link, tech stack (technologies used), industry or niche, role description (what was built), key results with metrics, and a priority flag.

Case 1 (required) must come from the Upwork portfolio. Pick the most relevant Upwork case by stack, niche, and problem type.

Case 2 (best match) is the single most relevant case from the combined pool: Upwork portfolio plus full Interexy case database. There is no hierarchy between the two sources; relevance wins. The system uses the full internal case database to determine best fit.

Case Matching Logic
Match by stack keywords from the job's mandatory skills section. Match by industry or niche. Match by problem type (real-time systems, payments, AI integration, healthcare, etc.). Case 1 is always from the Upwork portfolio. Case 2 is the best-matching case from either the Upwork portfolio or the full Interexy case database, whichever is more relevant. Maximum 2 cases per letter. Never use the same case in both Tilek and Victoria letters for the same job.

Output Block 3: two selected cases with a one-line explanation of why each was chosen.

Keyword Integration Rules
Source: mandatory skills section of the job posting. Naturally weave three to five mandatory skill keywords into the cover letter body. Never list them. Always embed them in the context of case descriptions or the closing statement.

Example: mandatory skills: React, Node.js, Supabase, TypeScript → "Built a production-grade React and Node.js platform with TypeScript throughout and Supabase as the real-time data layer."

Cover Letter Generation Pipeline

Step 1 - Job Evaluation: assess duration, hours, budget, stack fit, red flags. Output PASS or SKIP with reasoning. Stop if SKIP.

Step 2 - Profile Selection: determine Tilek / Victoria / Vicode Solutions / both. If both, run the pipeline twice independently.

Dual-profile rule (when both Tilek and Victoria letters are generated): cases must be completely different; no case can appear in both letters. Letter texts must be meaningfully distinct in hook, framing, and angle - not paraphrases of each other. Screening question answers must also differ; each answer written from the respective profile's perspective with different cases and different language.

Step 3 - Hook Generation: generate two or three hook options for the user to choose from, or auto-select the strongest one.

Hook Rules: never start with "Most...". Use conversational openers only: "Let me be honest...", "From what I see...", "To be honest...", "Let me be direct...". The hook must address a specific technical risk or business pain visible in the job description. One or two sentences maximum. No generic compliments to the client.

Step 4 - Case Selection: pull the two most relevant Priority 1 cases. Format per case: name plus link (if available) plus one or two lines on what was built and with which stack, plus a key result with metric.

Step 5 - Closing Statement: one or two sentences containing years of experience, core stack match to job requirements, availability (40 hours/week), and hourly rate (omit if fixed price).

Immediate start rule: if the job posting indicates the client wants to start immediately, within a few days, or urgently, include in the closing statement that the selected profile is available to start immediately.

Step 6 - CTA and Signature: CTA is always "Let's talk." Signature formats: for a solo profile (Tilek or Victoria) use "Best, [Name]". For the agency angle (Vicode Solutions) use "Best, [Name], Vicode Solutions / vicode.solutions/portfolio". For Tilek on technical roles, add "https://github.com/tilekchubakov" on a separate line.

Step 7 - Screening Questions (if present): detect if the job posting contains a screening questions block (for example, "You will be asked to answer the following questions" or similar). If yes, generate answers as a separate output block; never mix them into the letter body.

Format per answer: use a numbered list matching the job's question order. For "Describe recent experience" or any request to describe a case or project, answer in full detail: project name plus link, what the product does, the client's pain point, the solution built, tech stack, role on the project, and measurable results. Never give a brief or summary answer to this type of question. For technical questions, give a precise technical answer. For "Do you have certifications?" use a standard answer referencing production experience. Include GitHub or portfolio links where relevant. When both Tilek and Victoria answers are generated, each must use different cases and different language.

Cover Letter Structure

Block 1 Hook: one or two sentences, conversational, addresses a specific pain or risk from the job description.
Block 2 Bridge: one sentence connecting the hook to the solution being offered.
Block 3 Case 1: name and link on the same line, followed by one or two lines describing what was built, stack used, and a key result with metric.
Block 4 Case 2: same format as Case 1.
Block 5 Closing: years of experience plus stack match plus availability plus rate if hourly, plus "available to start immediately" if the job is urgent.
Block 6 CTA: "Let's talk."
Block 7 Signature: "Best, [Name]" plus optional portfolio/GitHub line.

Formatting Rules
Use hyphen-minus ( - ) only, never em dash ( — ) or en dash ( – ). No bold text inside the letter. No bullet points inside the letter. No headers inside the letter. Use plain paragraphs only. The case name and link appear on the same line, for example: Classful - https://classful.com. Letter length is 150-200 words maximum. Screening answers are always a separate block, never inside the letter. If the job posting contains specific instructions (answer questions, provide a timeline, include something particular), always follow them without exception. Missing a stated requirement is an automatic disqualifier.

Edge Cases
If the client name is known, open the letter with the client name. If the client name is unknown, use no greeting or just "Hi there". If a Loom is mandatory, write that a Loom will be sent upon response. If an NDA is required, acknowledge willingness to sign in the closing. If "Agency preferred" is stated, use the Vicode Solutions angle. For a fixed price job, do not mention a rate anywhere in the letter. For an hourly job, include the rate in the closing statement. If a screen-recorded assessment is required, flag it to the user and ask whether to proceed. If both AI and fullstack are required, generate two letters independently. If the job requires a test task or assessment, state in the letter that test tasks are completed on a paid basis only, and that the terms can be discussed separately; never agree to unpaid test tasks. If an urgent start or start within days is required, include in the closing that the profile is available to start immediately.
"""

# ----------------------------------------------------------------------
# 5. Шаблон письма-отклика
# ----------------------------------------------------------------------
letter_template = """
From what I see - this is less about building a shoe store and more about building a conversion machine that happens to sell shoes.
Performance, SEO, and clean architecture from day one - that's where I focus.
Arcade - https://arcade.ai
AI-powered marketplace handling thousands of concurrent requests. Built scalable backend infrastructure and React frontend optimized for high-load, real-time user interactions.
Classful - https://classful.com
EdTech SaaS, 1M+ MAU. Stripe integration, PostgreSQL optimization, page load speed improved by 55%. Conversion rate up 30%.
15+ years building scalable backend systems. I'll make sure your store is fast, clean, and ready to grow.
Let's talk.
Best,
Tilek
"""

# ----------------------------------------------------------------------
# Путь к папке с кейсами (относительно корня проекта)
# ----------------------------------------------------------------------
CASES_DIR = Path(__file__).parent.parent / "backend" / "knowledge_base" / "cases"


async def load_case_content(case_id: str) -> str:
    case_path = CASES_DIR / f"{case_id}.md"
    if not case_path.exists():
        print(f"⚠️ Файл кейса {case_id} не найден по пути {case_path}")
        return ""
    with open(case_path, "r", encoding="utf-8") as f:
        return f.read()


def fix_newlines(text: str) -> str:
    text = text.replace('\\n', '\n')
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text


async def evaluate_job_and_generate(
        rag_query: str,
        best_cases_with_content: list,
        user_profiles: list,
        selection_rules: dict,
        cover_letter_rules: str,
        letter_template: str,
        api_key: str,
        allowed_profiles: list = None,
        forbidden_case_ids: list = None
) -> dict:
    client_local = AsyncOpenAI(api_key=api_key)
    profiles_to_use = [p for p in user_profiles if allowed_profiles is None or p["name"] in allowed_profiles]
    forbidden_note = ""
    if forbidden_case_ids:
        forbidden_note = f"IMPORTANT: The following case IDs were already used in another letter for this same job — do NOT select them: {', '.join(forbidden_case_ids)}."

    cases_text = ""
    for idx, case in enumerate(best_cases_with_content, 1):
        cases_text += f"\n=== КЕЙС {idx} ===\nID: {case.get('id')}\nНазвание: {case.get('name', 'Unknown')}\nСсылка: {case.get('link', 'N/A')}\nСодержание:\n{case.get('content', '')[:3000]}\n"

    prompt = f"""
    Ты – AI-ассистент по подбору персонала для IT-вакансий. Твоя задача – оценить вакансию, выбрать наиболее подходящего кандидата из списка профилей и сгенерировать готовое письмо-отклик и ответы на скрининг-вопросы (если есть).

    ### Описание вакансии:
    {rag_query}

    ### Список релевантных кейсов компании (каждый с ID, названием, ссылкой и полным описанием):
    {cases_text}

    ### Профили кандидатов (JSON):
    {json.dumps(profiles_to_use, indent=2, ensure_ascii=False)}

    ### Базовые правила отбора работы (общие для всех кандидатов):
    {json.dumps(selection_rules, indent=2, ensure_ascii=False)}

    ### Правила оформления письма-отклика:
    {cover_letter_rules}

    ### Шаблон письма (может быть использован как основа, но нужно адаптировать под конкретную вакансию и профиль):
    {letter_template}

    ### Задание:
    1. **Job Evaluation**: Проанализируй вакансию. Реши, стоит ли откликаться (PASS) или пропустить (SKIP). Учти:
       - Длительность (duration_months): если вакансия короче указанного, всё равно можно PASS, если остальное подходит.
       - Часы в неделю (preferred_work_hours_per_week): если вакансия требует больше, чем указано, то SKIP.
       - Red flags: если в описании есть признаки, перечисленные в red_flags (например, "unpaid test task", "NDA without payment", "fixed price too low"), то SKIP с пояснением.
       - Соответствие стека и опыта.

       Выведи решение, краткое обоснование и любые флаги (например, "test task required", "urgent start").

    2. **Profile Selection**: Если решение PASS, выбери одного кандидата из списка профилей, который лучше всего подходит под вакансию. Учти:
       - Соответствие skills (особенно обязательным из описания вакансии).
       - min_salary_per_hour: Tilek minimum is $50/hr. Victoria solo angle minimum is $40/hr. Victoria / Vicode Solutions agency angle minimum is $35/hr. If the job budget is below the applicable minimum, the candidate does not qualify.
       - priority_cases: если у кандидата есть приоритетные кейсы, которые совпадают с индустрией/стеком вакансии – это плюс.
       - Общий опыт и позиция.

       Если ни один не подходит – укажи "None" и объясни причину.

    3. **Case Selection**: Для выбранного кандидата выбери 2 наиболее релевантных кейса из предоставленного списка (из тех, что были получены через RAG). Учти приоритетные кейсы кандидата (если они есть в списке). Для каждого кейса дай:
       - ID кейса
       - Название
       - Ссылку на **внешний клиентский сайт**, если она присутствует. **Важно**: ссылки, ведущие на `interexy` (например, `https://interexy.com/cases/...`), а также ссылки на магазины приложений (App Store, Google Play, `playmarket`, `apps.apple.com`, `play.google.com`) НЕ включай. Используй только ссылки на оригинальный сайт клиента (например, `https://classful.com`, `https://scale.com`). Если такой ссылки нет, оставь поле `link` пустым.
       - Одно предложение, почему этот кейс подходит (стек, индустрия, тип проблемы).

       {forbidden_note}
       Никогда не используй один кейс дважды. Если подходящих нет – выбери наиболее близкие.

    4. **Hook Generation**: Generate exactly 3 distinct hook options for Block 1 of the cover letter.
       Rules for each hook:
       - Addresses a different specific technical risk, business pain, or observable challenge from the job description.
       - Never starts with "Most...". Use conversational openers only: "Let me be honest...", "From what I see...", "To be honest...", "Let me be direct...", or similar natural openers.
       - 1-2 sentences maximum.
       - Must be specific to THIS job — not a generic opener that could apply to any posting.

       Score each hook 0-10 on specificity (how directly it targets a concrete, observable pain from THIS job description).
       Auto-select the highest-scoring hook as `selected_hook`. It will be used as Block 1 in the cover letter.

    5. **Cover Letter Generation**: Напиши письмо-отклик от лица выбранного кандидата, строго следуя правилам оформления (cover_letter_rules). Use `selected_hook` (from step 4) as Block 1 (Hook) of the letter. Используй буквально правила: структуру (Hook, Bridge, Case 1, Case 2, Closing, CTA, Signature), форматирование (без маркеров, без жирного, без заголовков, только plain paragraphs), максимальную длину 150-200 слов. Вплети 3-5 ключевых навыков из вакансии в описание кейсов или в closing. Не перечисляй их списком.

       **Важно про переводы строк**: при генерации письма используй **реальные символы перевода строки** (line breaks) для разделения абзацев. Не экранируй их как `\\n`. В поле `cover_letter` JSON должен содержать текст с настоящими переносами строк (это допустимо в JSON строках). Абзацы отделяй пустой строкой (два перевода строки).

    6. **Screening Answers**: Если в описании вакансии есть блок скрининг-вопросов (обычно начинается с "You will be asked to answer..." или "Please answer the following"), то сгенерируй ответы на каждый вопрос в виде нумерованного списка. Ответы должны быть полными, с деталями проектов, ссылками на кейсы, технологиями и метриками. Если вопрос про опыт – обязательно указывай конкретный кейс (из выбранных выше). Если вопрос про сертификаты – ответь стандартно: "У меня нет формальных сертификатов, но есть подтверждённый производственный опыт". Для технических вопросов дай точный ответ. Если скрининг-вопросов нет, оставь поле пустым.

       **Важно про переводы строк**: при генерации ответов используй **реальные символы перевода строки** (line breaks). Каждый новый вопрос с ответом начинай с новой строки. В поле `screening_answers` JSON должен содержать текст с настоящими переносами строк, а не экранированными `\\n`.

    ### Выходной формат (строго JSON):
    {{
      "job_evaluation": {{
        "decision": "PASS" или "SKIP",
        "reasoning": "краткое обоснование",
        "flags": "например, 'urgent_start, test_task_required' или пустая строка"
      }},
      "selected_profile": {{
        "name": "Tilek" или "Victoria" или "Vicode Solutions" или null,
        "reasoning": "почему выбран"
      }},
      "selected_cases": [
        {{
          "case_id": "id",
          "name": "название",
          "link": "ссылка (может быть пустой строкой)",
          "reasoning": "почему выбран"
        }}
      ],
      "hook_options": [
        {{"text": "hook variant 1", "specificity_score": 8}},
        {{"text": "hook variant 2", "specificity_score": 6}},
        {{"text": "hook variant 3", "specificity_score": 7}}
      ],
      "selected_hook": "text of the highest-scoring hook",
      "cover_letter": "текст письма (с переносами строк)",
      "screening_answers": "текст ответов (с переносами строк) или пустая строка"
    }}

    Важно: в JSON строках используй обычные переводы строк, а не `\\n`. Пример: "Привет\nМир" — это правильно. НЕ пиши "Привет\\nМир".
    В ответе верни ТОЛЬКО JSON, без дополнительного текста.
    """
    try:
        response = await client_local.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system",
                 "content": "Ты – экспертный помощник по подбору персонала для IT-компаний. Отвечай только JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            response_format={"type": "json_object"}
        )
        result_text = response.choices[0].message.content
        result = json.loads(result_text)
        if 'cover_letter' in result:
            result['cover_letter'] = fix_newlines(result['cover_letter'])
        if 'screening_answers' in result:
            result['screening_answers'] = fix_newlines(result['screening_answers'])
        if 'selected_hook' in result:
            result['selected_hook'] = fix_newlines(result['selected_hook'])
        return result
    except json.JSONDecodeError as e:
        print(f"JSON decode error: {e}")
        return {
            "job_evaluation": {"decision": "SKIP", "reasoning": f"JSON parse error: {e}", "flags": ""},
            "selected_profile": {"name": None, "reasoning": ""},
            "selected_cases": [],
            "cover_letter": "",
            "screening_answers": ""
        }
    except Exception as e:
        print(f"LLM call error: {e}")
        return {
            "job_evaluation": {"decision": "SKIP", "reasoning": f"LLM error: {e}", "flags": ""},
            "selected_profile": {"name": None, "reasoning": ""},
            "selected_cases": [],
            "cover_letter": "",
            "screening_answers": ""
        }


def append_to_google_sheet(job_description: str, profile_name: str, cover_letter: str, screening_answers: str = ""):
    """
    Записывает данные в Google Sheets таблицу.
    """
    try:
        creds_json = os.getenv("GOOGLE_SHEETS_CREDENTIALS_JSON")
        spreadsheet_id = os.getenv("GOOGLE_SHEETS_SPREADSHEET_ID")
        worksheet_name = os.getenv("GOOGLE_SHEETS_WORKSHEET_NAME", "Sheet1")

        if not creds_json or not spreadsheet_id:
            print("⚠️ Google Sheets credentials not configured, skipping logging")
            return

        creds_dict = json.loads(creds_json)
        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        client_gspread = gspread.authorize(creds)

        sheet = client_gspread.open_by_key(spreadsheet_id).worksheet(worksheet_name)
        now = datetime.now().isoformat()

        # Ограничиваем длину полей
        job_preview = job_description[:5000] + "..." if len(job_description) > 5000 else job_description
        letter_preview = cover_letter[:5000] + "..." if len(cover_letter) > 5000 else cover_letter
        screening_preview = screening_answers[:5000] + "..." if len(screening_answers) > 5000 else screening_answers

        row = [now, job_preview, profile_name, letter_preview, screening_preview]
        sheet.append_row(row)
        print(f"✅ Записано в Google Sheets: {profile_name} - PASS")
    except Exception as e:
        import traceback
        print(f"❌ Ошибка записи в Google Sheets: {e}")
        traceback.print_exc()


async def detect_dual_profile(job_description: str, api_key: str) -> bool:
    """Returns True if the job genuinely requires both AI/ML and fullstack expertise."""
    client_local = AsyncOpenAI(api_key=api_key)
    prompt = (
        "Analyze this job description and determine if it requires BOTH:\n"
        "- AI/ML skills (LLM, Python ML/data, RAG, MLOps, AI agents, NLP, data engineering)\n"
        "- AND fullstack development skills (React, Node.js, SaaS frontend/backend, web app development)\n\n"
        "A job qualifies as dual-profile ONLY if it genuinely requires deep expertise in BOTH areas "
        "simultaneously — not just passing familiarity with one while being primarily the other.\n\n"
        "Respond with JSON only: {\"dual_profile\": true} or {\"dual_profile\": false}\n\n"
        "Job description:\n" + job_description
    )
    try:
        response = await client_local.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You analyze job requirements. Respond only with JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0,
            response_format={"type": "json_object"}
        )
        result = json.loads(response.choices[0].message.content)
        return bool(result.get("dual_profile", False))
    except Exception as e:
        print(f"dual_profile detection error: {e}")
        return False


# ----------------------------------------------------------------------
# Пайплайн обработки (без GUI)
# ----------------------------------------------------------------------
async def process_job(job_description: str) -> dict:
    """Основная функция обработки вакансии – возвращает готовый результат."""
    try:
        best_cases = await rag.retrieve_cases(job_description, OPENAI_API_KEY)
        if not best_cases:
            return {"error": "No relevant cases found."}
        best_cases_with_content = []
        for case in best_cases:
            case_id = case.get("id")
            if not case_id:
                continue
            content = await load_case_content(case_id)
            if content:
                best_cases_with_content.append({
                    "id": case_id,
                    "name": case.get("name", ""),
                    "link": case.get("link", ""),
                    "content": content
                })
        if not best_cases_with_content:
            return {"error": "No cases could be loaded."}

        is_dual = await detect_dual_profile(job_description, OPENAI_API_KEY)

        if is_dual:
            tilek_result = await evaluate_job_and_generate(
                rag_query=job_description,
                best_cases_with_content=best_cases_with_content,
                user_profiles=user_profiles,
                selection_rules=selection_rules,
                cover_letter_rules=cover_letter_rules,
                letter_template=letter_template,
                api_key=OPENAI_API_KEY,
                allowed_profiles=["Tilek Chubakov"]
            )
            tilek_case_ids = [c.get("case_id", "") for c in tilek_result.get("selected_cases", [])]
            victoria_result = await evaluate_job_and_generate(
                rag_query=job_description,
                best_cases_with_content=best_cases_with_content,
                user_profiles=user_profiles,
                selection_rules=selection_rules,
                cover_letter_rules=cover_letter_rules,
                letter_template=letter_template,
                api_key=OPENAI_API_KEY,
                allowed_profiles=["Victoria", "Vicode Solutions"],
                forbidden_case_ids=tilek_case_ids
            )
            import threading
            for sub_result in [tilek_result, victoria_result]:
                if sub_result.get("job_evaluation", {}).get("decision") == "PASS":
                    threading.Thread(
                        target=append_to_google_sheet,
                        args=(
                            job_description,
                            sub_result.get("selected_profile", {}).get("name", "Unknown"),
                            sub_result.get("cover_letter", ""),
                            sub_result.get("screening_answers", "")
                        ),
                        daemon=True
                    ).start()
            return {"dual": True, "tilek": tilek_result, "victoria": victoria_result}

        evaluation = await evaluate_job_and_generate(
            rag_query=job_description,
            best_cases_with_content=best_cases_with_content,
            user_profiles=user_profiles,
            selection_rules=selection_rules,
            cover_letter_rules=cover_letter_rules,
            letter_template=letter_template,
            api_key=OPENAI_API_KEY
        )

        job_eval = evaluation.get("job_evaluation", {})
        if job_eval.get("decision") == "PASS":
            selected_profile = evaluation.get("selected_profile", {}).get("name", "Unknown")
            cover_letter = evaluation.get("cover_letter", "")
            screening_answers = evaluation.get("screening_answers", "")
            import threading
            threading.Thread(
                target=append_to_google_sheet,
                args=(job_description, selected_profile, cover_letter, screening_answers),
                daemon=True
            ).start()

        return evaluation
    except Exception as e:
        return {"error": f"Processing failed: {str(e)}"}
