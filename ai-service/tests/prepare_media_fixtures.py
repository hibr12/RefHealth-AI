"""Optional live-test fixtures: a generated shape and a public speech sample.

Run explicitly; ordinary unit tests never download files or call providers.
"""
from hashlib import sha256
from pathlib import Path
import ssl
import wave

import httpx
from PIL import Image, ImageDraw

folder = Path(__file__).resolve().parents[2] / ".local" / "assistant-media"
folder.mkdir(parents=True, exist_ok=True)
picture = Image.new("RGB", (256, 256), "white")
ImageDraw.Draw(picture).ellipse((50, 50, 206, 206), fill="blue")
picture.save(folder / "blue-circle.png")

audio_path = folder / "question.wav"
expected = "59dfb9a4acb36fe2a2affc14bacbee2920ff435cb13cc314a08c13f66ba7860e"
if not audio_path.exists() or sha256(audio_path.read_bytes()).hexdigest() != expected:
    with httpx.Client(verify=ssl.create_default_context(), timeout=30) as client:
        response = client.get("https://raw.githubusercontent.com/ggml-org/whisper.cpp/master/samples/jfk.wav")
        response.raise_for_status()
        data = response.content
    if sha256(data).hexdigest() != expected:
        raise ValueError("The public audio fixture changed; review it before updating the expected digest.")
    audio_path.write_bytes(data)
with wave.open(str(audio_path)) as recording:
    assert recording.getframerate() == 16000 and recording.getnchannels() == 1
print(f"Media fixtures ready in {folder}")
