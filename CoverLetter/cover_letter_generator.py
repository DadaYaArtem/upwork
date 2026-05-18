# cover_letter_generator.py
# -----------------------------------------------------------------------------
# Изменения относительно прежней версии:
#  1. Промпт основной генерации полностью на английском (единый язык output).
#  2. Screening-вопросы извлекаются ОТДЕЛЬНЫМ дешёвым вызовом до главного шага.
#     В основной промпт уже приходит готовый numbered list + команда ответить на все.
#  3. Few-shot примеры писем (2 Tilek + 2 Victoria) — взяты из реальной истории
#     в CSV. Они дают модели стиль вместо догадок по правилам.
#  4. Hook anchor rule: каждый hook обязан явно сослаться на конкретный фрагмент
#     job description. Без привязки — score < 5, такой hook не выбирается.
#  5. Основная модель — gpt-4o. gpt-4o-mini оставлен только для дешёвых детекторов.
#  6. letter_template убран как общий шаблон (он тянул "Best, Tilek" даже под Victoria).
#  7. Добавлена функция refine_letter — для команд "translate to english",
#     "shorter", "more technical" из Slack-бота без повторного RAG.
# -----------------------------------------------------------------------------

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

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable is not set")

client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# Какие модели использовать
MAIN_MODEL = os.getenv("COVER_LETTER_MAIN_MODEL", "gpt-4o")          # для письма
HELPER_MODEL = os.getenv("COVER_LETTER_HELPER_MODEL", "gpt-4o-mini") # для детекторов


# -----------------------------------------------------------------------------
# Профили
# -----------------------------------------------------------------------------
user_profiles = [
    {
        "name": "Tilek Chubakov",
        "position": "Senior AI/ML Engineer, AI Agents, LLM, MLOps, Lead Data Engineer",
        "skills": [
            "ETL/ELT pipelines with dbt and scalable data warehousing",
            "Data lake and lakehouse architectures for analytics and ML",
            "AWS, GCP, Azure infrastructure; Docker and Kubernetes",
            "RAG, LangChain, LLM fine-tuning, Hugging Face Transformers",
            "Prompt engineering, tool usage, context-aware pipelines",
            "Autonomous workflows integrating APIs, databases, enterprise systems",
            "End-to-end ML pipelines with MLflow and Kubeflow",
            "Time-series forecasting (Prophet, ARIMA); XGBoost, LightGBM, CatBoost",
            "PyTorch, TensorFlow on GPU infrastructure",
            "NER, classification, semantic search, RAG, QA systems",
            "Apache Spark, Kafka, Airflow; BigQuery, Snowflake, Redshift",
            "Python, C#, Scala, Java, R, JavaScript",
            "PostgreSQL, MongoDB, Cassandra, Redis, MS SQL Server, Oracle",
            "AWS Lambda, Glue, Kinesis; GCP Pub/Sub, BigQuery, Cloud Run",
            "Azure Function Apps, Event Hubs, Data Explorer",
            "Node.js, React, Flask, FastAPI on the integration layer",
            "Terraform, GitLab CI/CD, GitHub Actions, dbt, Fivetran"
        ],
        "min_salary_per_hour_usd": 50,
        "priority_cases": [
            "Scale AI", "Arcade", "Deverus", "Generative AI Marketplace",
            "AI Identity Verification", "CryptoPay", "LLM Chatbot & RAG System",
            "AI Document Processing", "FinTech Payment System"
        ],
        "signature": "Best,\nTilek",
        "github": "https://github.com/tilekchubakov"
    },
    {
        "name": "Victoria",
        "position": "Senior Full-Stack Developer, React, Node.js, Scalable SaaS",
        "skills": [
            "Full-stack development with React and Node.js for scalable web applications",
            "Frontend with React, Next.js, TypeScript, Redux, Tailwind",
            "Backend with Node.js and Express for REST API architecture",
            "SaaS platforms, multi-tenant systems, cloud infrastructure",
            "PostgreSQL and MongoDB schema design and performance tuning",
            "API integrations, authentication, secure data handling",
            "AWS, Docker, CI/CD pipelines",
            "Cross-platform with Flutter and React Native"
        ],
        "min_salary_per_hour_usd": 40,
        "min_salary_agency_usd": 35,
        "priority_cases": [
            "Scale AI", "Arcade", "Deverus", "Generative AI Marketplace",
            "AI Identity Verification", "CryptoPay", "LLM Chatbot & RAG System",
            "AI Document Processing", "FinTech Payment System"
        ],
        "signature": "Best,\nViktoryia"
    },
    {
        "name": "Vicode Solutions",
        "position": "Full-Cycle Software Development Agency, React, Node.js, Scalable SaaS, 350+ developers",
        "skills": [
            "Responsive React, Next.js, TypeScript, Redux, Tailwind interfaces",
            "Node.js and Express backends, REST API design",
            "PostgreSQL and MongoDB modeling for multi-tenant SaaS",
            "Auth, third-party integrations, cloud deployment with CI/CD",
            "Full-stack SaaS application development, payment integrations"
        ],
        "min_salary_per_hour_usd": 35,
        "priority_cases": [
            "Scale AI", "Arcade", "Deverus", "Generative AI Marketplace",
            "AI Identity Verification", "CryptoPay", "LLM Chatbot & RAG System",
            "AI Document Processing", "FinTech Payment System"
        ],
        "signature": "Best,\nViktoryia, Vicode Solutions\nhttps://vicode.solutions/portfolio"
    },
]


# -----------------------------------------------------------------------------
# Базовые правила отбора работы
# -----------------------------------------------------------------------------
selection_rules = {
    "duration_months": 2,
    "preferred_work_hours_per_week": 30,
    "red_flags": (
        "No job details, too niche stack (GHL-only, OpenClaw-only, n8n-only), "
        "geo restrictions that exclude the profile, screen-recorded assessments, "
        "Loom mandatory with no alternative, unpaid test tasks."
    )
}


# -----------------------------------------------------------------------------
# Правила оформления письма — единым английским блоком
# -----------------------------------------------------------------------------
cover_letter_rules = """\
COVER LETTER RULES (English only — never mix languages inside the letter).

Length: 150-200 words. Plain paragraphs only. No bullet points, no headers, no bold.
Allowed punctuation for separators: hyphen-minus only (-). Never use em dash or en dash.
If the client name is visible in the job post, start with it ("Hi <Name>,"). Otherwise use "Hi there,".

Structure (each block is 1-3 sentences, separated by blank lines):
  1. HOOK - one or two sentences naming a concrete technical risk, architectural pitfall,
     or business pain that is OBSERVABLE in the job description. Must quote or paraphrase
     a specific fragment of the job text. Never start with "Most...". Conversational openers
     like "Let me be honest", "From what I see", "You are not considering the significant
     technical risk...", "To be honest..." are fine. No generic compliments.
  2. BRIDGE - one sentence connecting the hook to what you do. Mention 2-3 mandatory
     skill keywords from the job (woven into the sentence, never listed).
  3. CASE 1 - "ClientName - https://link". Then one or two sentences: what was built,
     stack used, one concrete metric. Pull from the provided RAG cases. Never invent links.
  4. CASE 2 - same format. Different case from Case 1. Different aspect of the project
     than Case 1 if relevant.
  5. CLOSING - years of experience + stack match + availability (40 hrs/week) + hourly
     rate (skip if fixed-price). Add "available to start immediately" if the post signals
     urgency. If a test task is mentioned, state it is completed on a paid basis only.
  6. CTA - exactly "Let's talk." on its own line.
  7. SIGNATURE - profile-specific signature provided in the profile.

Keyword integration: weave 3-5 mandatory-skill keywords from the job into the case
descriptions or closing. Never list them.

Mandatory: if the job post contains any specific instructions (answer N questions,
include a phrase, mention a timeline) - follow them. Missing a stated requirement is
an auto-fail and the letter must not be submitted.

Cases sourcing: Case 1 should be the strongest Upwork-portfolio match by stack/niche
when available; Case 2 the best from the combined pool. If both letters (Tilek + Victoria)
are generated for the same job, they must use completely different cases and have
meaningfully different framing.
"""


# -----------------------------------------------------------------------------
# Few-shot примеры (взяты из реальной истории Tilek/Vika)
# -----------------------------------------------------------------------------
PROPOSAL_VARIANT_STRUCTURES = """\
PROPOSAL VARIANT STRUCTURES
Generate three additional full cover-letter variants after the main `cover_letter`.
They are meant to be ready-to-copy alternatives, not outlines.

Shared rules for every variant:
  - English only.
  - 150-220 words.
  - Plain paragraphs only, unless the job explicitly asks for numbered answers inside the proposal.
  - Use only selected cases and facts available in the job, profiles, and RAG cases.
  - Keep the profile signature and rate/availability rules consistent with the main letter.
  - Do not copy the main letter. Each variant must have a clearly different opening and framing.
  - Screening answers stay in `screening_answers`. However, if the job explicitly asks for
    architecture, implementation plan, technical approach, stack recommendation, or "how would
    you build this", exactly one variant may include one concise "For the architecture/stack..."
    paragraph inside the letter.

Variant 1 - Risk / Ownership:
  Open with the concrete technical or business risk visible in this job. Then position the
  profile as the person who owns that risk end to end. Use the cases as proof that the same
  class of risk has been handled before.

Variant 2 - Architecture / Approach:
  Open with the system design problem in the job. Include one job-specific approach paragraph
  such as "For the architecture..." or "For the stack..." with concrete components, boundaries,
  or data flow. Keep it practical and not over-engineered.

Variant 3 - Case-Led Proof:
  Lead with the closest selected case and map it tightly to the client's requirements. The
  opening should feel like "I have built this adjacent thing before", then explain the match
  through stack, workflow, constraints, and measurable result.
"""


TILEK_EXAMPLES = """\
EXAMPLE 1 (Tilek, Shopify + React + Python + AWS job):
You are not considering the significant technical risk which can cost you $150k when React + Python systems are scaled on AWS without proper Terraform, API boundaries, and cloud cost control.

I build full-stack platforms using React for complex admin UIs, Python for backend services, AWS Lambda for scalable workloads, GraphQL for stable data contracts, and Terraform for fully reproducible infrastructure.

On Deverus - https://www.deverus.com/ - a large-scale background screening platform, I rebuilt core flows with React frontend, Python services on AWS, and cloud automation, cutting onboarding drop-off by 74% and supporting millions of checks monthly.

On Arcade AI - https://www.arcade.ai/ - an AI-powered SaaS marketplace, I delivered scalable React/Next.js frontends with AI-driven logic stable enough for production traffic and monetization.

Working with me means a senior engineer who designs systems to survive real traffic and audits, not just pass initial QA - I proactively eliminate AWS cost leaks and infra drift.

Let's talk.
Best,
Tilek

EXAMPLE 2 (Tilek, AI SaaS on React + Next.js + Supabase):
Roy and Mateusz, you are not considering the significant technical risk which can cost you $180k when AI-driven SaaS platforms are built without proper data ingestion pipelines, agent orchestration, and clean frontend-backend boundaries.

I build AI SaaS platforms using React and Next.js for production UI, Supabase for auth and real-time data, and OpenAI for RAG pipelines and multi-agent orchestration.

On Arcade AI - https://www.arcade.ai/ - I delivered a scalable React/Next.js frontend integrated with AI-driven logic and stabilized the platform for real user traffic.

On Deverus - https://www.deverus.com/ - I rebuilt a regulated multi-tenant SaaS with React/Node, REST APIs, and optimized DB structure - same architectural pattern your platform needs.

Available 40 hrs/week at $50/hr, ready to start immediately.

Let's talk.
Best,
Tilek
"""

VICTORIA_EXAMPLES = """\
EXAMPLE 1 (Victoria, HIPAA full-stack):
Hi Jason,

This is a backend ownership problem - multi-tenant data isolation, HIPAA-compliant infrastructure, and a clean API layer a real clinic can trust from day one. The frontend is done; the hard part is everything underneath it.

I work as a senior full-stack engineer owning Node.js/Fastify backends and React frontends end to end - PostgreSQL schema design, REST API boundaries, auth, and production delivery. Fluent in TypeScript, Prisma and Supabase, and Redis-backed async infrastructure.

On Renegade Health - https://renegade.health/ - a HIPAA-regulated telemedicine platform, I led compliance audit prep: PHI access controls, audit logging, architectural sign-off. Stack: Node.js, TypeScript, PostgreSQL, GCP.

On Deverus - https://www.deverus.com/ - a regulated multi-tenant SaaS, I worked on backend redesign and a blockchain-based digital wallet for document verification - another environment where data isolation wasn't optional.

Available immediately, 40 hrs/week, $40/hr.

Let's talk.
Best,
Viktoryia

EXAMPLE 2 (Victoria, marketplace):
Hi Sara,

Building a marketplace is an architecture decision made at the start that determines whether the platform scales cleanly or becomes a bottleneck six months in. Vendor profiles, listings, payment flows, and AI integrations all need to be designed as a system.

I own projects like this end to end - from the first database schema to a vendor listing a product and a buyer completing a payment. Fewer handoffs, faster decisions, no gap between design and build.

On Arcade - https://www.arcade.ai/ - an AI-powered generative design marketplace, I built the React frontend and Node.js backend orchestrating AI/ML models, real-time 3D previews, and artisan order workflows - reducing product design time from days to minutes.

On Nash.io - https://nash.io/ - a digital asset trading platform, I delivered real-time frontend architecture with React and WebSocket on AWS.

Let's talk.
Best,
Viktoryia
"""


# -----------------------------------------------------------------------------
# Загрузка кейсов
# -----------------------------------------------------------------------------
CASES_DIR = Path(__file__).parent.parent / "backend" / "knowledge_base" / "cases"


async def load_case_content(case_id: str) -> str:
    case_path = CASES_DIR / f"{case_id}.md"
    if not case_path.exists():
        print(f"⚠️ Файл кейса {case_id} не найден по пути {case_path}")
        return ""
    with open(case_path, "r", encoding="utf-8") as f:
        return f.read()


def fix_newlines(text: str) -> str:
    if not text:
        return text
    text = text.replace('\\n', '\n')
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text


def normalize_proposal_variants(result: dict) -> None:
    variants = result.get("proposal_variants")
    if not isinstance(variants, list):
        result["proposal_variants"] = []
        return

    expected_names = ("Risk / Ownership", "Architecture / Approach", "Case-Led Proof")
    normalized = []
    for variant in variants:
        if len(normalized) == 3:
            break
        if not isinstance(variant, dict):
            continue
        cover_letter = variant.get("cover_letter")
        if not isinstance(cover_letter, str) or not cover_letter.strip():
            continue
        normalized.append({
            "structure_name": expected_names[len(normalized)],
            "angle": str(variant.get("angle") or ""),
            "when_to_use": str(variant.get("when_to_use") or ""),
            "cover_letter": fix_newlines(cover_letter),
        })
    result["proposal_variants"] = normalized


def format_cover_letter_for_sheet(cover_letter: str, proposal_variants: Optional[List[dict]] = None) -> str:
    sections = []
    if cover_letter:
        sections.append("MAIN COVER LETTER\n" + cover_letter)

    for idx, variant in enumerate(proposal_variants or [], 1):
        if not isinstance(variant, dict):
            continue
        variant_letter = variant.get("cover_letter")
        if not variant_letter:
            continue
        title = variant.get("structure_name") or f"Variant {idx}"
        angle = variant.get("angle") or ""
        heading = f"VARIANT {idx}: {title}"
        if angle:
            heading += f"\nAngle: {angle}"
        sections.append(f"{heading}\n{variant_letter}")

    return "\n\n---\n\n".join(sections)


# -----------------------------------------------------------------------------
# Детектор dual-profile (без изменений по логике)
# -----------------------------------------------------------------------------
async def detect_dual_profile(job_description: str, api_key: str) -> bool:
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
            model=HELPER_MODEL,
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


# -----------------------------------------------------------------------------
# НОВОЕ: отдельный шаг извлечения screening-вопросов
# -----------------------------------------------------------------------------
async def extract_screening_questions(job_description: str, api_key: str) -> List[str]:
    """
    Вытаскивает из job description все вопросы, на которые клиент явно
    или неявно просит ответить. Возвращает список строк.
    Если вопросов нет — возвращает [].
    """
    client_local = AsyncOpenAI(api_key=api_key)
    prompt = f"""You are extracting questions a freelancer must answer in their cover letter.

Read the job posting below and return EVERY question or explicit instruction-to-describe that
appears in it. Capture all of these patterns:

  - Numbered or bulleted lists of questions ("1. What is your...  2. How would you...").
  - Questions in prose ending with "?".
  - Imperative requests for information ("Please describe your experience with X",
    "Tell us about a similar project", "Share your timeline and budget",
    "Explain your approach to Y", "What is your hourly rate?").
  - Sections that start with phrases like "You will be asked to answer the following",
    "Please answer these questions", "In your proposal please include", "When applying,
    cover the following".
  - Any explicit checklist of items the client wants in the proposal (timeline, rate, samples,
    portfolio link, availability) - capture each item as a separate question.

Rules:
  - Return each item as a clean single-sentence question. If the original is imperative
    ("Please share your timeline"), convert it to a question ("What is your timeline?").
  - Preserve the order they appear in the post.
  - Do NOT invent questions that are not in the post.
  - Do NOT include generic application etiquette (e.g. "are you interested?").
  - If there are no questions at all, return an empty list.

Job description:
\"\"\"
{job_description}
\"\"\"

Respond with JSON only in this exact shape:
{{ "questions": ["question 1", "question 2", ...] }}
"""
    try:
        response = await client_local.chat.completions.create(
            model=HELPER_MODEL,
            messages=[
                {"role": "system", "content": "You extract screening questions. Respond only with JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0,
            response_format={"type": "json_object"}
        )
        result = json.loads(response.choices[0].message.content)
        questions = result.get("questions", [])
        # дешёвый sanity-check
        return [q.strip() for q in questions if isinstance(q, str) and q.strip()]
    except Exception as e:
        print(f"screening extraction error: {e}")
        return []


# -----------------------------------------------------------------------------
# Google Sheets логгер (без изменений)
# -----------------------------------------------------------------------------
def append_to_google_sheet(
    job_description: str,
    profile_name: str,
    cover_letter: str,
    screening_answers: str = "",
    proposal_variants: Optional[List[dict]] = None,
):
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

        job_preview = job_description[:5000] + "..." if len(job_description) > 5000 else job_description
        sheet_cover_letter = format_cover_letter_for_sheet(cover_letter, proposal_variants)
        letter_preview = (
            sheet_cover_letter[:45000] + "..."
            if len(sheet_cover_letter) > 45000
            else sheet_cover_letter
        )
        screening_preview = screening_answers[:5000] + "..." if len(screening_answers) > 5000 else screening_answers

        row = [now, job_preview, profile_name, letter_preview, screening_preview]
        sheet.append_row(row)
        print(f"✅ Записано в Google Sheets: {profile_name} - PASS")
    except Exception as e:
        import traceback
        print(f"❌ Ошибка записи в Google Sheets: {e}")
        traceback.print_exc()


# -----------------------------------------------------------------------------
# ГЛАВНЫЙ ПРОМПТ — теперь на английском
# -----------------------------------------------------------------------------
def _build_main_prompt(
    job_description: str,
    cases_text: str,
    profiles_to_use: list,
    selection_rules: dict,
    screening_questions: List[str],
    forbidden_case_ids: Optional[List[str]],
    examples_block: str,
) -> str:
    forbidden_note = ""
    if forbidden_case_ids:
        forbidden_note = (
            "IMPORTANT - the following case IDs were already used in a parallel letter "
            f"for this same job. Do NOT select them: {', '.join(forbidden_case_ids)}.\n"
        )

    if screening_questions:
        screening_block = (
            "SCREENING QUESTIONS DETECTED IN THE POST. You MUST answer every single one "
            "in `screening_answers` as a numbered list, in the order shown below. "
            "Skipping a question is an automatic disqualifier - in that case return "
            "decision=SKIP with reasoning=\"cannot answer all screening questions\".\n\n"
            "Questions to answer:\n"
            + "\n".join(f"{i+1}. {q}" for i, q in enumerate(screening_questions))
            + "\n\nFor each answer:\n"
              "- Use the same numbering as above.\n"
              "- For experience/project questions: name the case, give its link, what was built, "
              "the client's pain, the stack, your role, and a measurable result. Never give a brief answer.\n"
              "- For rate/availability/timeline questions: be specific (rate, hours, ETA).\n"
              "- For certification questions: 'I do not have formal certifications, but I have "
              "production experience verifiable through portfolio cases above.'\n"
              "- For technical questions: give a precise technical answer.\n"
              "- Always answer in English.\n"
        )
    else:
        screening_block = (
            "No screening questions were detected. Return `screening_answers` as an empty string."
        )

    profiles_json = json.dumps(profiles_to_use, indent=2, ensure_ascii=False)
    selection_json = json.dumps(selection_rules, indent=2, ensure_ascii=False)

    return f"""You are an expert proposal writer for Upwork IT jobs. You evaluate the job, pick the
right profile from the provided list, choose 2 relevant cases from the RAG-retrieved pool,
and produce a final proposal letter + screening answers.

OUTPUT LANGUAGE
All of these MUST be in English: `cover_letter`, `screening_answers`, every `hook_options[].text`,
and `selected_hook`. Never mix languages inside any of these fields, not even single Russian
words. The `reasoning` fields are also expected in English; if you must use Russian to be clear,
that is acceptable ONLY inside reasoning fields, never inside output text shown to the client.

JOB DESCRIPTION
\"\"\"
{job_description}
\"\"\"

RAG-RETRIEVED CASES (each with ID, name, client link, full content)
{cases_text}

CANDIDATE PROFILES
{profiles_json}

JOB-SELECTION BASE RULES
{selection_json}

COVER LETTER RULES
{cover_letter_rules}

PROPOSAL VARIANT RULES
{PROPOSAL_VARIANT_STRUCTURES}

REFERENCE EXAMPLES (style only - do NOT copy text or cases, do NOT mimic specific phrasing
unless it fits the actual job):
{examples_block}

SCREENING DETECTION
{screening_block}

{forbidden_note}
TASK STEPS

1. JOB EVALUATION. PASS or SKIP based on:
   - duration_months: shorter is fine if everything else fits.
   - preferred_work_hours_per_week: SKIP if the job demands more.
   - red_flags from base rules - any match = SKIP with explanation.
   - Stack/experience fit.
   Output decision + short reasoning + flags (e.g. "urgent_start, test_task_required").

2. PROFILE SELECTION. From the allowed profiles, pick ONE:
   - Stack match against the job's mandatory skills section.
   - Rate gate: Tilek minimum $50/hr; Victoria solo minimum $40/hr; Vicode Solutions
     (agency) minimum $35/hr. If budget below applicable minimum - profile does not qualify.
   - Priority cases that overlap with job stack/industry are a plus.
   If no profile fits, return name=null with reasoning.

3. CASE SELECTION. For the chosen profile, pick the 2 most relevant cases from the RAG list above.
   For each: case_id, name, external client link, one-sentence reasoning. Exclude links
   that point to interexy domains or app stores (apps.apple.com, play.google.com,
   playmarket). Leave link empty if no clean external client link is available.
   Never use the same case twice.
   {forbidden_note}

4. HOOK GENERATION. Produce exactly 3 distinct hook options for Block 1.
   HARD REQUIREMENT: each hook MUST reference a concrete detail observable in THIS job
   description - a specific technology mentioned, a concrete risk implied by the stated
   architecture, a specific business goal, a stated constraint, or a unique combination of
   requirements. A hook that would also work for an unrelated job is a failure.
   Rules:
     - Never start with "Most...".
     - Use conversational openers: "Let me be honest", "From what I see",
       "You are not considering the significant technical risk...", "To be honest",
       "<Client name>, you are not considering...", or similar.
     - 1-2 sentences max.
   Score each hook 0-10 on specificity. Specificity rubric:
     - 9-10: cites or paraphrases a specific phrase/requirement from the job.
     - 6-8: references the exact stack combo and a plausible technical pitfall for it.
     - 3-5: generic for the role family, no anchor to this job.
     - 0-2: applies to almost any job.
   Auto-select by setting `selected_hook` to the highest-scoring hook (must be >=6; if all
   are <6, regenerate in your reasoning and try again before finalizing).

5. COVER LETTER. Write the letter strictly following the cover letter rules. Use
   `selected_hook` verbatim as Block 1. Use the cases selected in step 3, with the
   profile's signature block from the profile JSON. For Tilek on technical roles add the
   github line under the signature. 150-200 words.

6. SCREENING ANSWERS. Generate per the SCREENING DETECTION block above.

7. PROPOSAL VARIANTS. Generate exactly 3 additional full proposal variants in
   `proposal_variants`, following PROPOSAL VARIANT RULES. Use these exact structure names:
   "Risk / Ownership", "Architecture / Approach", and "Case-Led Proof". They must be
   complete ready-to-copy letters, not outlines, and must be materially different from
   the main `cover_letter`.

NEWLINES
For `cover_letter`, `screening_answers`, `selected_hook`, and every
`proposal_variants[].cover_letter` use REAL newline characters inside the JSON string
(this is valid JSON). Do not escape them as `\\n`. Separate paragraphs with one blank
line (two newlines).

OUTPUT FORMAT - STRICT JSON, NOTHING ELSE
{{
  "job_evaluation": {{
    "decision": "PASS" or "SKIP",
    "reasoning": "short reasoning",
    "flags": "comma-separated flags or empty string"
  }},
  "selected_profile": {{
    "name": "Tilek" or "Victoria" or "Vicode Solutions" or null,
    "reasoning": "why chosen"
  }},
  "selected_cases": [
    {{
      "case_id": "id",
      "name": "case name",
      "link": "external client url or empty string",
      "reasoning": "why this case fits"
    }}
  ],
  "hook_options": [
    {{"text": "hook variant 1", "specificity_score": 8}},
    {{"text": "hook variant 2", "specificity_score": 6}},
    {{"text": "hook variant 3", "specificity_score": 7}}
  ],
  "selected_hook": "text of the highest-scoring hook",
  "cover_letter": "letter body with real newlines",
  "screening_answers": "answers with real newlines, or empty string",
  "proposal_variants": [
    {{
      "structure_name": "Risk / Ownership",
      "angle": "one sentence explaining this variant's angle",
      "when_to_use": "one sentence explaining when this variant is strongest",
      "cover_letter": "full ready-to-copy letter with real newlines"
    }},
    {{
      "structure_name": "Architecture / Approach",
      "angle": "one sentence explaining this variant's angle",
      "when_to_use": "one sentence explaining when this variant is strongest",
      "cover_letter": "full ready-to-copy letter with real newlines"
    }},
    {{
      "structure_name": "Case-Led Proof",
      "angle": "one sentence explaining this variant's angle",
      "when_to_use": "one sentence explaining when this variant is strongest",
      "cover_letter": "full ready-to-copy letter with real newlines"
    }}
  ]
}}
"""


async def evaluate_job_and_generate(
        rag_query: str,
        best_cases_with_content: list,
        user_profiles: list,
        selection_rules: dict,
        api_key: str,
        screening_questions: Optional[List[str]] = None,
        allowed_profiles: Optional[List[str]] = None,
        forbidden_case_ids: Optional[List[str]] = None
) -> dict:
    client_local = AsyncOpenAI(api_key=api_key)
    profiles_to_use = [p for p in user_profiles if allowed_profiles is None or p["name"] in allowed_profiles]

    # Подбираем few-shot блок под список разрешённых профилей,
    # чтобы для Victoria-only не маячил "Best, Tilek".
    if allowed_profiles == ["Tilek Chubakov"]:
        examples_block = TILEK_EXAMPLES
    elif allowed_profiles and "Tilek Chubakov" not in allowed_profiles:
        examples_block = VICTORIA_EXAMPLES
    else:
        examples_block = TILEK_EXAMPLES + "\n\n" + VICTORIA_EXAMPLES

    cases_text = ""
    for idx, case in enumerate(best_cases_with_content, 1):
        cases_text += (
            f"\n=== CASE {idx} ===\n"
            f"ID: {case.get('id')}\n"
            f"Name: {case.get('name', 'Unknown')}\n"
            f"Link: {case.get('link', 'N/A')}\n"
            f"Content:\n{case.get('content', '')[:3000]}\n"
        )

    prompt = _build_main_prompt(
        job_description=rag_query,
        cases_text=cases_text,
        profiles_to_use=profiles_to_use,
        selection_rules=selection_rules,
        screening_questions=screening_questions or [],
        forbidden_case_ids=forbidden_case_ids,
        examples_block=examples_block,
    )

    try:
        response = await client_local.chat.completions.create(
            model=MAIN_MODEL,
            messages=[
                {"role": "system",
                 "content": (
                     "You are a senior Upwork proposal writer. You always output strictly "
                     "valid JSON. The `cover_letter`, `screening_answers`, and `selected_hook` "
                     "fields must be in English only, never mixed with Russian. Always include "
                     "exactly 3 full proposal variants in `proposal_variants`."
                 )},
                {"role": "user", "content": prompt}
            ],
            temperature=0.5,
            response_format={"type": "json_object"}
        )
        result_text = response.choices[0].message.content
        result = json.loads(result_text)
        for k in ("cover_letter", "screening_answers", "selected_hook"):
            if k in result and isinstance(result[k], str):
                result[k] = fix_newlines(result[k])
        normalize_proposal_variants(result)
        return result
    except json.JSONDecodeError as e:
        print(f"JSON decode error: {e}")
        return {
            "job_evaluation": {"decision": "SKIP", "reasoning": f"JSON parse error: {e}", "flags": ""},
            "selected_profile": {"name": None, "reasoning": ""},
            "selected_cases": [],
            "cover_letter": "",
            "screening_answers": "",
            "proposal_variants": []
        }
    except Exception as e:
        print(f"LLM call error: {e}")
        return {
            "job_evaluation": {"decision": "SKIP", "reasoning": f"LLM error: {e}", "flags": ""},
            "selected_profile": {"name": None, "reasoning": ""},
            "selected_cases": [],
            "cover_letter": "",
            "screening_answers": "",
            "proposal_variants": []
        }


# -----------------------------------------------------------------------------
# Refine - для команд из Slack типа "translate to english", "shorter",
# "more technical". Не запускает RAG повторно.
# -----------------------------------------------------------------------------
async def refine_letter(
    previous_letter: str,
    previous_screening: str,
    user_instruction: str,
    api_key: str,
    target_language: str = "English"
) -> Dict[str, str]:
    """
    Применяет пользовательскую правку к уже сгенерированному письму, сохраняя
    структуру (hook, bridge, кейсы со ссылками, closing, CTA, signature).
    """
    client_local = AsyncOpenAI(api_key=api_key)
    prompt = f"""You are refining an already-generated Upwork cover letter and its screening answers.
Apply the user's instruction. Keep the proposal structure (hook, bridge, two cases with their links,
closing, CTA, signature) intact unless the instruction explicitly asks to change a specific part.
Do NOT add information that was not present in the previous letter (no invented metrics, no new cases).

Output language: {target_language}. Never mix languages.
Keep the length 150-200 words for the letter unless the instruction says otherwise.
Use plain paragraphs, hyphen-minus as separator, no bullets, no headers, no bold.

PREVIOUS LETTER:
\"\"\"
{previous_letter}
\"\"\"

PREVIOUS SCREENING ANSWERS (may be empty):
\"\"\"
{previous_screening}
\"\"\"

USER INSTRUCTION:
\"\"\"
{user_instruction}
\"\"\"

Respond with JSON only:
{{
  "cover_letter": "refined letter with real newlines",
  "screening_answers": "refined answers with real newlines, or empty string if there were none",
  "note": "one-sentence note about what you changed"
}}
"""
    try:
        response = await client_local.chat.completions.create(
            model=MAIN_MODEL,
            messages=[
                {"role": "system",
                 "content": "You refine cover letters. Output strict JSON. Never mix languages."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.4,
            response_format={"type": "json_object"}
        )
        result = json.loads(response.choices[0].message.content)
        for k in ("cover_letter", "screening_answers"):
            if k in result and isinstance(result[k], str):
                result[k] = fix_newlines(result[k])
        return result
    except Exception as e:
        print(f"refine_letter error: {e}")
        return {"cover_letter": previous_letter, "screening_answers": previous_screening,
                "note": f"refine failed: {e}"}


def _compact_result_for_chat(result: dict) -> dict:
    if result.get("dual"):
        return {
            "dual": True,
            "tilek": _compact_result_for_chat(result.get("tilek", {})),
            "victoria": _compact_result_for_chat(result.get("victoria", {})),
            "screening_questions": result.get("_screening_questions", []),
        }

    return {
        "job_evaluation": result.get("job_evaluation", {}),
        "selected_profile": result.get("selected_profile", {}),
        "selected_cases": result.get("selected_cases", []),
        "hook_options": result.get("hook_options", []),
        "selected_hook": result.get("selected_hook", ""),
        "cover_letter": result.get("cover_letter", ""),
        "screening_answers": result.get("screening_answers", ""),
        "proposal_variants": result.get("proposal_variants", []),
    }


async def answer_about_last_result(last_result: dict, user_question: str, api_key: str) -> str:
    client_local = AsyncOpenAI(api_key=api_key)
    context_json = json.dumps(_compact_result_for_chat(last_result), ensure_ascii=False, indent=2)
    prompt = f"""You answer internal Slack follow-up questions about the latest Upwork proposal result.
Use only the stored result below. Do not invent project facts, rates, cases, or job details.
If the user asks which proposal variant is strongest, compare the main letter and variants by
specificity, fit to the job, and usefulness for winning a reply.

Answer in the same language as the user's question when obvious. Keep it concise.

STORED RESULT:
{context_json[:20000]}

USER QUESTION:
{user_question}
"""
    try:
        response = await client_local.chat.completions.create(
            model=MAIN_MODEL,
            messages=[
                {"role": "system", "content": "You answer questions about a generated Upwork proposal. Be concise and factual."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
        return (response.choices[0].message.content or "").strip()
    except Exception as e:
        print(f"answer_about_last_result error: {e}")
        return f"Не смог ответить по последнему результату: {e}"


# -----------------------------------------------------------------------------
# Основной пайплайн
# -----------------------------------------------------------------------------
async def process_job(job_description: str) -> dict:
    try:
        # 1. RAG: вытаскиваем кейсы
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

        # 2. Параллельно: dual-profile detection + screening extraction
        is_dual_task = detect_dual_profile(job_description, OPENAI_API_KEY)
        screening_task = extract_screening_questions(job_description, OPENAI_API_KEY)
        is_dual, screening_questions = await asyncio.gather(is_dual_task, screening_task)

        if screening_questions:
            print(f"📋 Detected {len(screening_questions)} screening questions:")
            for q in screening_questions:
                print(f"   - {q}")
        else:
            print("📋 No screening questions detected")

        # 3. Генерация (dual или single)
        if is_dual:
            tilek_result = await evaluate_job_and_generate(
                rag_query=job_description,
                best_cases_with_content=best_cases_with_content,
                user_profiles=user_profiles,
                selection_rules=selection_rules,
                api_key=OPENAI_API_KEY,
                screening_questions=screening_questions,
                allowed_profiles=["Tilek Chubakov"]
            )
            tilek_case_ids = [c.get("case_id", "") for c in tilek_result.get("selected_cases", [])]
            victoria_result = await evaluate_job_and_generate(
                rag_query=job_description,
                best_cases_with_content=best_cases_with_content,
                user_profiles=user_profiles,
                selection_rules=selection_rules,
                api_key=OPENAI_API_KEY,
                screening_questions=screening_questions,
                allowed_profiles=["Victoria", "Vicode Solutions"],
                forbidden_case_ids=tilek_case_ids
            )
            # Передадим screening_questions наружу - полезно для логов и Slack
            tilek_result["_screening_questions"] = screening_questions
            victoria_result["_screening_questions"] = screening_questions

            import threading
            for sub_result in [tilek_result, victoria_result]:
                if sub_result.get("job_evaluation", {}).get("decision") == "PASS":
                    threading.Thread(
                        target=append_to_google_sheet,
                        args=(
                            job_description,
                            sub_result.get("selected_profile", {}).get("name", "Unknown"),
                            sub_result.get("cover_letter", ""),
                            sub_result.get("screening_answers", ""),
                            sub_result.get("proposal_variants", [])
                        ),
                        daemon=True
                    ).start()
            return {"dual": True, "tilek": tilek_result, "victoria": victoria_result,
                    "_screening_questions": screening_questions,
                    "_job_description": job_description}

        evaluation = await evaluate_job_and_generate(
            rag_query=job_description,
            best_cases_with_content=best_cases_with_content,
            user_profiles=user_profiles,
            selection_rules=selection_rules,
            api_key=OPENAI_API_KEY,
            screening_questions=screening_questions
        )
        evaluation["_screening_questions"] = screening_questions
        evaluation["_job_description"] = job_description

        job_eval = evaluation.get("job_evaluation", {})
        if job_eval.get("decision") == "PASS":
            selected_profile = evaluation.get("selected_profile", {}).get("name", "Unknown")
            cover_letter = evaluation.get("cover_letter", "")
            screening_answers = evaluation.get("screening_answers", "")
            import threading
            threading.Thread(
                target=append_to_google_sheet,
                args=(
                    job_description,
                    selected_profile,
                    cover_letter,
                    screening_answers,
                    evaluation.get("proposal_variants", []),
                ),
                daemon=True
            ).start()

        return evaluation
    except Exception as e:
        return {"error": f"Processing failed: {str(e)}"}
