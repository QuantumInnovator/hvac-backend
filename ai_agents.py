# ai_agents.py

import os
import json
import time
from dotenv import load_dotenv

from google import genai
from google.genai import errors as genai_errors


load_dotenv()


GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")


client = genai.Client(api_key=GEMINI_API_KEY)


# The old "gemini-2.5-flash" model (via the deprecated google.generativeai
# package) is no longer available to new users. Using the current
# recommended model via the new google-genai SDK instead.
MODEL_NAME = "gemini-3.5-flash"

MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 2


SYSTEM_PROMPT = """
You are an AI HVAC receptionist.

Your job is to answer incoming phone calls professionally.

Collect:

1. Customer Name
2. Phone Number
3. Address
4. HVAC Problem
5. Preferred Appointment Time

Rules:
- Keep answers short.
- Sound natural.
- Be polite.
- Do not say you are an AI.
- Help schedule HVAC service.
"""


def get_ai_response(conversation_history):
    """
    conversation_history: list of dicts like
        [{"role": "user", "text": "..."}, {"role": "model", "text": "..."}, ...]
    The full history is sent each time so the AI remembers the whole call.
    """

    contents = []

    for turn in conversation_history:

        role = "user" if turn["role"] == "user" else "model"

        contents.append({
            "role": role,
            "parts": [{"text": turn["text"]}],
        })

    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):

        try:

            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=contents,
                config={
                    "system_instruction": SYSTEM_PROMPT,
                },
            )

            return response.text

        except genai_errors.ServerError as e:

            # 503 = model temporarily overloaded on Google's side.
            # Retry a couple of times with a short delay before giving up.
            last_error = e

            print(f"⚠️ Gemini overloaded (attempt {attempt}/{MAX_RETRIES}), retrying...")

            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY_SECONDS)

    # All retries exhausted - return a graceful fallback instead of
    # crashing the call, so the customer still hears something sensible.
    print("AI Error after retries:", last_error)

    return (
        "I'm sorry, I'm having a little trouble right now. "
        "Could you please repeat that, or hold on just a moment?"
    )


LEAD_EXTRACTION_PROMPT = """
You will be given a full phone call transcript between an HVAC AI
receptionist and a customer. Extract the following information and
respond with ONLY a raw JSON object (no markdown, no code fences, no
extra text) with exactly these keys:

{
  "customer_name": string or null,
  "phone_number": string or null,
  "address": string or null,
  "issue": string (short description of the HVAC problem, required -
           use "Not specified" if truly unclear),
  "urgency": one of "low", "normal", "high", "emergency" (default "normal"),
  "appointment_time": string or null (preferred time customer mentioned),
  "notes": string or null (any other relevant details)
}

If a field was never mentioned in the call, use null for it (except
"issue" and "urgency" which always need a value as described above).
Respond with ONLY the JSON object.
"""


def extract_lead_info(conversation_history):
    """
    Takes the full call conversation history and asks Gemini to pull out
    structured lead fields as JSON. Returns a dict matching LeadCreate's
    fields, or None if extraction fails.
    """

    transcript_text = "\n".join(
        f"{'Customer' if t['role'] == 'user' else 'AI'}: {t['text']}"
        for t in conversation_history
    )

    try:

        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=f"{LEAD_EXTRACTION_PROMPT}\n\nTranscript:\n{transcript_text}",
        )

        raw_text = response.text.strip()

        # strip accidental markdown code fences, just in case
        if raw_text.startswith("```"):
            raw_text = raw_text.strip("`")
            if raw_text.lower().startswith("json"):
                raw_text = raw_text[4:].strip()

        data = json.loads(raw_text)

        return data

    except Exception as e:
        print("Lead extraction error:", e)
        return None