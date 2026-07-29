# text_to_speech.py

import os
import aiohttp

from dotenv import load_dotenv

load_dotenv()


DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")


# NOTE: encoding=mulaw + sample_rate=8000 + container=none
# gives us RAW mulaw bytes, exactly what Twilio Media Streams expects.
# No wav/container header, so we can send it straight to the websocket.
DEEPGRAM_TTS_URL = (
    "https://api.deepgram.com/v1/speak"
    "?model=aura-asteria-en"
    "&encoding=mulaw"
    "&sample_rate=8000"
    "&container=none"
)


async def text_to_speech_mulaw(text: str) -> bytes:
    """
    Converts text -> raw mulaw audio (8kHz, no container) using
    Deepgram's Aura TTS REST API.

    Returns bytes ready to base64-encode and send as a Twilio
    'media' event payload.
    """

    if not text or not text.strip():
        return b""

    headers = {
        "Authorization": f"Token {DEEPGRAM_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {"text": text}

    async with aiohttp.ClientSession() as session:

        async with session.post(
            DEEPGRAM_TTS_URL,
            headers=headers,
            json=payload,
        ) as resp:

            if resp.status != 200:
                error_text = await resp.text()
                raise RuntimeError(
                    f"Deepgram TTS failed ({resp.status}): {error_text}"
                )

            audio_bytes = await resp.read()

    return audio_bytes