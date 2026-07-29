# list_devices.py

import pyaudio

pa = pyaudio.PyAudio()

print("\n=== Available Input Devices ===\n")

for i in range(pa.get_device_count()):

    info = pa.get_device_info_by_index(i)

    if info["maxInputChannels"] > 0:
        marker = ""
        try:
            default_info = pa.get_default_input_device_info()
            if default_info["index"] == i:
                marker = "  <-- current default"
        except Exception:
            pass

        print(f"[{i}] {info['name']}  "
              f"(rate: {int(info['defaultSampleRate'])} Hz){marker}")

print("\n=== Available Output Devices ===\n")

for i in range(pa.get_device_count()):

    info = pa.get_device_info_by_index(i)

    if info["maxOutputChannels"] > 0:
        marker = ""
        try:
            default_info = pa.get_default_output_device_info()
            if default_info["index"] == i:
                marker = "  <-- current default"
        except Exception:
            pass

        print(f"[{i}] {info['name']}  "
              f"(rate: {int(info['defaultSampleRate'])} Hz){marker}")

pa.terminate()

print("\nNote the [index] number of your real physical microphone above,")
print("then set INPUT_DEVICE_INDEX in test_client.py to that number.")