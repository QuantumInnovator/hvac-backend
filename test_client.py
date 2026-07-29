# test_client.py

import asyncio
import base64
import json
import struct
import signal

import pyaudio
import websockets

try:
    import audioop
    HAS_AUDIOOP = True
except ImportError:
    HAS_AUDIOOP = False
    print("⚠️ audioop not available (Python 3.13+?) - using basic fallback resampler")
    print("   For better quality: pip install audioop-lts")


WS_URL = "ws://127.0.0.1:8000/media-stream"

TARGET_RATE = 8000
CHUNK_MS = 20  # 20ms chunks, matches Twilio's expected cadence

# Set these to force a specific device (see list_devices.py output).
# Leave as None to use Windows' default device (currently seems wrong -
# RMS stays near 0 even while speaking, so try setting INPUT_DEVICE_INDEX
# explicitly to your real mic's index).
INPUT_DEVICE_INDEX = 2
OUTPUT_DEVICE_INDEX = None


RUNNING = True


def shutdown(sig, frame):
    global RUNNING
    print("\n🛑 Stopping...")
    RUNNING = False


signal.signal(signal.SIGINT, shutdown)


# ==========================
# PCM16 <-> MULAW
# ==========================

BIAS = 0x84
CLIP = 32635


def linear2ulaw(sample):

    if sample > CLIP:
        sample = CLIP

    if sample < -CLIP:
        sample = -CLIP

    sign = 0

    if sample < 0:
        sign = 0x80
        sample = -sample

    sample += BIAS

    exponent = 7
    exp_mask = 0x4000

    while exponent > 0 and not (sample & exp_mask):
        exponent -= 1
        exp_mask >>= 1

    mantissa = (sample >> (exponent + 3)) & 0x0F

    return (~(sign | (exponent << 4) | mantissa)) & 0xFF


def pcm_to_mulaw(data):

    samples = struct.unpack("<" + "h" * (len(data) // 2), data)

    return bytes(linear2ulaw(x) for x in samples)


def ulaw2linear(u_val):
    """Standard mu-law -> 16-bit linear PCM decode."""

    u_val = ~u_val & 0xFF

    sign = u_val & 0x80
    exponent = (u_val >> 4) & 0x07
    mantissa = u_val & 0x0F

    sample = ((mantissa << 3) + BIAS) << exponent
    sample -= BIAS

    if sign != 0:
        sample = -sample

    if sample > 32767:
        sample = 32767
    if sample < -32768:
        sample = -32768

    return sample


def mulaw_to_pcm(data):

    return struct.pack(
        "<" + "h" * len(data),
        *(ulaw2linear(b) for b in data)
    )


# ==========================
# Resampling (native mic rate <-> 8000 Hz)
# ==========================


def basic_resample(pcm_bytes, src_rate, dst_rate):
    """
    Fallback linear-interpolation resampler, used only if audioop
    isn't available. Lower quality than audioop but works everywhere.
    """

    samples = struct.unpack("<" + "h" * (len(pcm_bytes) // 2), pcm_bytes)

    if not samples:
        return b""

    src_n = len(samples)
    dst_n = int(src_n * dst_rate / src_rate)

    out = []

    for i in range(dst_n):
        src_pos = i * (src_n - 1) / max(dst_n - 1, 1)
        idx = int(src_pos)
        frac = src_pos - idx

        s1 = samples[idx]
        s2 = samples[min(idx + 1, src_n - 1)]

        out.append(int(s1 + (s2 - s1) * frac))

    return struct.pack("<" + "h" * len(out), *out)


class Resampler:
    """Stateful resampler wrapping audioop.ratecv when available."""

    def __init__(self, src_rate, dst_rate):
        self.src_rate = src_rate
        self.dst_rate = dst_rate
        self._state = None

    def convert(self, pcm_bytes):

        if self.src_rate == self.dst_rate:
            return pcm_bytes

        if HAS_AUDIOOP:
            converted, self._state = audioop.ratecv(
                pcm_bytes, 2, 1, self.src_rate, self.dst_rate, self._state
            )
            return converted

        return basic_resample(pcm_bytes, self.src_rate, self.dst_rate)


# ==========================
# Websocket connect retry
# ==========================


async def connect_ws():

    while True:

        try:

            ws = await websockets.connect(
                WS_URL,
                ping_interval=20,
                ping_timeout=20
            )

            print("✅ Backend Connected")

            return ws

        except Exception:

            print("⏳ Waiting for backend...")

            await asyncio.sleep(2)


# ==========================
# Sender: mic -> websocket
# ==========================


async def sender(ws, mic, native_rate, native_chunk_frames):

    global RUNNING

    resampler = Resampler(native_rate, TARGET_RATE)

    chunk_count = 0

    while RUNNING:

        pcm_native = mic.read(native_chunk_frames, exception_on_overflow=False)

        # DEBUG: print mic volume (RMS) roughly once a second so we can
        # confirm numerically whether real sound is being captured.
        # Typical silence/room noise: 0-100. Normal speech: 500-5000+.
        # If this stays near 0 even while talking loudly close to the
        # mic, Windows is capturing from the wrong / muted device.
        chunk_count += 1
        if chunk_count % 50 == 0 and HAS_AUDIOOP:
            volume = audioop.rms(pcm_native, 2)
            print(f"🔊 Mic volume (RMS): {volume}")

        pcm_8k = resampler.convert(pcm_native)

        if not pcm_8k:
            await asyncio.sleep(CHUNK_MS / 1000)
            continue

        mulaw = pcm_to_mulaw(pcm_8k)

        payload = base64.b64encode(mulaw).decode()

        packet = {
            "event": "media",
            "media": {
                "payload": payload
            }
        }

        await ws.send(json.dumps(packet))

        await asyncio.sleep(CHUNK_MS / 1000)


# ==========================
# Receiver: websocket -> speaker
# ==========================


PREBUFFER_CHUNKS = 5  # ~100ms of buffering before playback starts,
                       # absorbs network jitter so playback is smooth


async def player(speaker, queue, native_out_rate):
    """
    Pulls decoded 8kHz PCM chunks off the queue, resamples them to the
    speaker's native rate, and writes them at a steady pace - decoupled
    from network arrival timing. This is what actually smooths out
    choppy audio.
    """

    loop = asyncio.get_event_loop()

    resampler = Resampler(TARGET_RATE, native_out_rate)

    async def play(chunk):
        pcm_out = resampler.convert(chunk)
        await loop.run_in_executor(None, speaker.write, pcm_out)

    # wait for a small prebuffer before starting playback
    buffered = []

    while len(buffered) < PREBUFFER_CHUNKS:

        chunk = await queue.get()

        if chunk is None:  # sentinel: stream ended before prebuffer filled
            for c in buffered:
                await play(c)
            return

        buffered.append(chunk)

    for c in buffered:
        await play(c)

    while True:

        chunk = await queue.get()

        if chunk is None:
            break

        await play(chunk)


async def receiver(ws, queue):
    """
    Only decodes incoming media events and pushes them onto the queue.
    Playback timing is handled entirely by player().
    """

    global RUNNING

    try:

        async for message in ws:

            try:
                data = json.loads(message)
            except Exception:
                continue

            event = data.get("event")

            if event == "media":

                payload = data.get("media", {}).get("payload")

                if not payload:
                    continue

                mulaw = base64.b64decode(payload)

                pcm_8k = mulaw_to_pcm(mulaw)

                await queue.put(pcm_8k)

            elif event == "stop":

                print("☎️ Server ended stream")
                RUNNING = False
                break

    except websockets.ConnectionClosed:

        print("❌ Websocket closed (receiver)")

    finally:
        await queue.put(None)  # signal player to stop


# ==========================
# Main stream
# ==========================


async def stream():

    global RUNNING

    ws = await connect_ws()

    pa = pyaudio.PyAudio()

    mic = None
    speaker = None

    try:

        await ws.send(
            json.dumps({
                "event": "start",
                "start": {
                    "streamSid": "LOCAL_TEST"
                }
            })
        )

        print("📞 Stream Started")

        # --- detect native input rate ---
        if INPUT_DEVICE_INDEX is not None:
            in_info = pa.get_device_info_by_index(INPUT_DEVICE_INDEX)
        else:
            in_info = pa.get_default_input_device_info()

        native_in_rate = int(in_info["defaultSampleRate"])
        native_chunk_frames = int(native_in_rate * CHUNK_MS / 1000)

        print(f"🎙️ Using mic: {in_info['name']} @ {native_in_rate} Hz "
              f"(will resample to {TARGET_RATE} Hz)")

        # --- detect native output rate ---
        if OUTPUT_DEVICE_INDEX is not None:
            out_info = pa.get_device_info_by_index(OUTPUT_DEVICE_INDEX)
        else:
            out_info = pa.get_default_output_device_info()

        native_out_rate = int(out_info["defaultSampleRate"])

        print(f"🔊 Using speaker: {out_info['name']} @ {native_out_rate} Hz")

        mic = pa.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=native_in_rate,
            input=True,
            input_device_index=INPUT_DEVICE_INDEX,
            frames_per_buffer=native_chunk_frames
        )

        speaker = pa.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=native_out_rate,
            output=True,
            output_device_index=OUTPUT_DEVICE_INDEX,
            frames_per_buffer=int(native_out_rate * CHUNK_MS / 1000) * 4
        )

        print("🎤 Speak now... (AI replies will play through speaker)")

        playback_queue = asyncio.Queue()

        await asyncio.gather(
            sender(ws, mic, native_in_rate, native_chunk_frames),
            receiver(ws, playback_queue),
            player(speaker, playback_queue, native_out_rate),
        )

    except websockets.ConnectionClosed:

        print("❌ Websocket closed")

    except Exception as e:

        print("Client Error:", e)

    finally:

        try:
            await ws.send(json.dumps({"event": "stop"}))
        except Exception:
            pass

        if mic:
            mic.stop_stream()
            mic.close()

        if speaker:
            speaker.stop_stream()
            speaker.close()

        pa.terminate()

        await ws.close()

        print("🔴 Closed")


if __name__ == "__main__":

    asyncio.run(stream())