# -*- coding: utf-8 -*-
"""Global configuration."""

# ---- Whisper model (mlx-whisper, Apple Silicon GPU accelerated) ----
# Downloaded from Hugging Face to a local cache on first run; fully offline after that
MODEL_REPO = "mlx-community/whisper-large-v3-turbo"
# None = auto-detect language (recommended for mixed Chinese/English speech);
# can also force "zh" or "en"
LANGUAGE = None
# A punctuated example sentence used as a decoding "prompt" to reduce missing commas/periods
INITIAL_PROMPT = "以下是带有标点符号的句子。你好，今天天气不错，我们去吃饭吧。"
# Chinese output normalization: "simplified" / "traditional" / "preserve" (leave model output as-is)
OUTPUT_CHINESE = "simplified"
# Custom vocabulary: add jargon, names, or project names you say often that keep getting
# misrecognized (order doesn't matter). The model uses this list to bias recognition toward them.
CUSTOM_VOCABULARY = [
    # "Kubernetes",
    # "faster-whisper",
]

# ---- Recording ----
SAMPLE_RATE = 16000
CHANNELS = 1
MAX_RECORD_SECONDS = 60  # caps recording length in case Fn release is ever missed

# ---- Output ----
AUTO_TYPE = True  # True: always try to type directly at the cursor
# False: normally just types, without touching the clipboard; only falls back to
#        also copying to the clipboard when no editable cursor is found
# True: always copies to the clipboard as well, regardless of whether a cursor was found
ALWAYS_COPY_TO_CLIPBOARD = False

# ---- Hotkey ----
MIN_PRESS_MS = 150  # Fn presses shorter than this are ignored, to filter out accidental taps
