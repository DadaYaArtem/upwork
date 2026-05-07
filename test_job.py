import asyncio
import json
from CoverLetter.cover_letter_generator import process_job

job_description = """
We are looking for a senior React and Node.js developer to build a SaaS platform.
Must have experience with PostgreSQL, Stripe, authentication, and scalable architecture.
40 hours per week, long-term.
Please answer:
1. Describe your recent experience with SaaS platforms.
2. What is your hourly rate?
"""

async def main():
    result = await process_job(job_description)
    print(json.dumps(result, indent=2, ensure_ascii=False))

asyncio.run(main())