# voice_session.py

import json
import base64
import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from speech_to_text import create_deepgram
from ai_agents import get_ai_response, extract_lead_info
from text_to_speech import text_to_speech_mulaw
from database import SessionLocal
from model import Lead


router = APIRouter()


# Twilio expects ~160-byte mulaw chunks (20ms of 8kHz audio) sent at a
# steady pace. Sending one giant blob can choke playback / get dropped.
CHUNK_SIZE = 160
CHUNK_INTERVAL = 0.02  # seconds


@router.websocket("/media-stream")
async def media_stream(websocket: WebSocket):

    await websocket.accept()

    print("✅ Twilio Media Stream Connected")

    deepgram = None
    last_transcript = ""
    stream_sid = None

    # Full conversation history for this call, so the AI remembers
    # what's already been said (name, problem, etc.) instead of
    # treating every message as a fresh, context-less turn.
    conversation_history = []

    # protects websocket.send_text() from concurrent writes if
    # multiple process_ai() tasks are in flight at once
    send_lock = asyncio.Lock()

    async def send_audio_to_twilio(audio_bytes: bytes):

        if not audio_bytes or not stream_sid:
            return

        for i in range(0, len(audio_bytes), CHUNK_SIZE):

            chunk = audio_bytes[i:i + CHUNK_SIZE]

            payload = base64.b64encode(chunk).decode()

            packet = {
                "event": "media",
                "streamSid": stream_sid,
                "media": {
                    "payload": payload
                }
            }

            async with send_lock:
                await websocket.send_text(json.dumps(packet))

            await asyncio.sleep(CHUNK_INTERVAL)

    async def save_lead():

        if not conversation_history:
            return  # nothing was said, nothing to save

        lead_data = extract_lead_info(conversation_history)

        if not lead_data:
            print("⚠️ Could not extract lead data, skipping save")
            return

        db = SessionLocal()

        try:

            new_lead = Lead(
                customer_name=lead_data.get("customer_name") or "Unknown",
                phone_number=lead_data.get("phone_number") or "Unknown",
                address=lead_data.get("address"),
                issue=lead_data.get("issue") or "Not specified",
                urgency=lead_data.get("urgency") or "normal",
                status="new",
                appointment_time=lead_data.get("appointment_time"),
                estimated_value=0,
                notes=lead_data.get("notes"),
            )

            db.add(new_lead)
            db.commit()
            db.refresh(new_lead)

            print(f"💾 Lead saved (id={new_lead.id}): "
                  f"{new_lead.customer_name} - {new_lead.issue}")

        except Exception as e:
            print("Lead save error:", e)

        finally:
            db.close()

    async def process_ai(text):
        try:
            print("\n👤 Customer:", text)

            conversation_history.append({"role": "user", "text": text})

            reply = get_ai_response(conversation_history)
            print("🤖 AI:", reply)

            conversation_history.append({"role": "model", "text": reply})

            audio_bytes = await text_to_speech_mulaw(reply)

            await send_audio_to_twilio(audio_bytes)

        except Exception as e:
            print("AI Error:", e)

    def transcript_callback(text):

        nonlocal last_transcript

        if not text:
            return

        text = text.strip()

        # duplicate protection
        if text == last_transcript:
            return

        last_transcript = text

        asyncio.create_task(
            process_ai(text)
        )

    try:

        deepgram = await create_deepgram(
            transcript_callback
        )

        print("✅ Deepgram Connected")

        async for message in websocket.iter_text():

            try:
                data = json.loads(message)
            except Exception:
                continue

            event = data.get("event")

            if event == "start":

                stream_sid = data["start"].get("streamSid")

                print("📞 Stream:", stream_sid)

            elif event == "media":

                payload = (
                    data
                    .get("media", {})
                    .get("payload")
                )

                if not payload:
                    continue

                audio = base64.b64decode(payload)

                # DEBUG: confirms bytes are arriving from the client.
                # Remove once things are working.
                print(f"🔍 Received {len(audio)} bytes of audio, forwarding to Deepgram")

                await deepgram.send_audio(audio)

            elif event == "stop":

                print("☎️ Call End")
                break

    except WebSocketDisconnect:

        print("⚠️ Client disconnected")

    except Exception as e:

        print("Websocket Error:", e)

    finally:

        if deepgram:
            try:
                await deepgram.close()
                print("🔴 Deepgram Closed")
            except Exception as e:
                print("Cleanup Error:", e)

        await save_lead()