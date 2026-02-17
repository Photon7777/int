import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

SYSTEM = """You are an Internship Application Agent for Data/Analytics roles.
Your goal: help the user apply faster with higher-quality materials.

Return output in this EXACT structure with clear headings:

1) ROLE SUMMARY (2-3 bullets)
2) MUST-HAVE SKILLS (bullets)
3) NICE-TO-HAVE SKILLS (bullets)
4) RESUME GAP CHECK (bullets: Missing / Weak / Strong matches)
5) TAILORED RESUME BULLETS (5-7 bullets; quantifiable; ATS-friendly)
6) 120-WORD COVER LETTER PARAGRAPH (1 paragraph)
7) NETWORKING MESSAGE (LinkedIn DM <= 80 words)
8) INTERVIEW TALKING POINTS (4 bullets)

Rules:
- If job post is messy/partial, still produce best-effort.
- Be specific: use keywords from the job post.
- Never invent experiences; if unsure, phrase as suggestions.
"""

def generate_application_materials(job_post: str, resume_text: str, extra_notes: str = "") -> str:
    user = f"""
JOB POST:
{job_post}

RESUME (USER-PROVIDED):
{resume_text}

EXTRA NOTES:
{extra_notes}
"""
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
        ],
        temperature=0.4,
    )
    return resp.choices[0].message.content