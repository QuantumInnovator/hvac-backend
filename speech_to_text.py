# speech_to_text.py

import os
import json
import asyncio
import websockets

from dotenv import load_dotenv

load_dotenv()

DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")

DEEPGRAM_URL = (
    "wss://api.deepgram.com/v1/listen"
    "?model=nova-2"
    "&language=en"
    "&encoding=mulaw"
    "&sample_rate=8000"
    "&channels=1"
    "&punctuate=true"
    "&interim_results=false"
    "&endpointing=300"
    "&smart_format=true"
)


class DeepgramStream:

    def __init__(self, callback):

        self.callback = callback

        self.ws = None

        self.receiver_task = None

        self.keep_alive_task = None

        self.closed = False


    async def connect(self):

        self.ws = await websockets.connect(

            DEEPGRAM_URL,

            additional_headers={

                "Authorization":
                f"Token {DEEPGRAM_API_KEY}"

            }

        )

        print("🎤 Deepgram WebSocket Connected")

        self.receiver_task = asyncio.create_task(
            self.receive()
        )

        self.keep_alive_task = asyncio.create_task(
            self.keep_alive()
        )


    async def send_audio(self, audio: bytes):

        if self.closed:
            return

        if self.ws is None:
            return

        try:

            await self.ws.send(audio)

        except Exception as e:

            print("Deepgram send error:", e)


    async def receive(self):

        try:

            async for message in self.ws:

                data = json.loads(message)

                msg_type = data.get("type")

                if msg_type != "Results":
                    continue

                # Ignore interim hypotheses
                if not data.get("is_final", False):
                    continue

                transcript = (

                    data

                    .get("channel", {})

                    .get("alternatives", [{}])[0]

                    .get("transcript", "")

                    .strip()

                )

                if not transcript:
                    continue

                print(f"📝 Deepgram: {transcript}")

                try:

                    self.callback(transcript)

                except Exception as e:

                    print("Transcript callback error:", e)

        except websockets.ConnectionClosed:

            print("Deepgram connection closed")

        except Exception as e:

            print("Deepgram receive error:", e)


    async def keep_alive(self):

        while not self.closed:

            try:

                await asyncio.sleep(8)

                if self.ws:

                    await self.ws.send(

                        json.dumps(

                            {

                                "type": "KeepAlive"

                            }

                        )

                    )

            except:

                break


    async def close(self):

        self.closed = True

        try:

            if self.keep_alive_task:

                self.keep_alive_task.cancel()

        except:
            pass

        try:

            if self.receiver_task:

                self.receiver_task.cancel()

        except:
            pass

        try:

            if self.ws:

                await self.ws.send(

                    json.dumps(

                        {

                            "type": "Finalize"

                        }

                    )

                )

        except:
            pass

        try:

            if self.ws:

                await self.ws.close()

        except:
            pass

        print("🔴 Deepgram Closed")


async def create_deepgram(callback):

    dg = DeepgramStream(callback)

    await dg.connect()

    return dg