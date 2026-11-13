# -*- coding: utf-8 -*-
"""Global configuration."""
import os

# ---- Recognition engine ----
# "sensevoice"  : SenseVoice-Small via sherpa-onnx (default). ~5-11x faster than
#                 Whisper-large on CPU, very strong on Chinese and zh/en code-switching,
#                 adds punctuation itself. Runs on any Mac (Intel too), Linux, Windows.
# "mlx-whisper" : whisper-large-v3-turbo on the Apple Silicon GPU (the original engine).
ENGINE = "sensevoice"
# Where sherpa-onnx models are downloaded (from GitHub releases, free, once)
MODELS_DIR = os.path.expanduser("~/.cache/localasr/models")
NUM_THREADS = 4  # CPU threads for sherpa-onnx (SenseVoice / VAD)

# ---- Whisper model (mlx-whisper, only used when ENGINE == "mlx-whisper") ----
MODEL_REPO = "mlx-community/whisper-large-v3-turbo"
# None = auto-detect language (recommended for mixed Chinese/English speech);
# can also force "zh" or "en"
LANGUAGE = None
# Decoding "prompt" that nudges Whisper toward punctuated, code-switched output.
# Kept bilingual on purpose: a purely Chinese prompt biases English speech toward
# being transcribed (or even translated) as Chinese.
INITIAL_PROMPT = "以下是普通话和 English 混合的句子，带有标点符号。今天我们 review 一下这个 PR 吧。"
# Chinese output normalization: "simplified" / "traditional" / "preserve" (leave model output as-is)
OUTPUT_CHINESE = "simplified"
# Custom vocabulary: add jargon, names, or project names you say often that keep getting
# misrecognized (order doesn't matter). Whisper uses it as a prompt; SenseVoice has no
# prompt, so for SenseVoice it is used for case-insensitive spelling correction of
# Latin-script terms (e.g. "kubernetes" -> "Kubernetes").
CUSTOM_VOCABULARY = [
    # "Kubernetes",
    # "faster-whisper",
]

# ---- Real-time segmentation ----
# True: a voice-activity detector cuts your speech at natural pauses and each finished
# phrase is transcribed in the background *while you are still talking*, so on release
# only the last phrase is left to transcribe (~0.1-0.2 s with SenseVoice).
STREAMING = True
# True: type each phrase as soon as it is recognized, while Fn is still held.
# Off by default: text appears while you speak, which some apps handle poorly.
TYPE_WHILE_SPEAKING = False

# ---- Recording ----
SAMPLE_RATE = 16000
CHANNELS = 1
MAX_RECORD_SECONDS = 300  # caps recording length in case Fn release is ever missed

# ---- Output ----
AUTO_TYPE = True  # True: always try to type directly at the cursor
# False: normally just types, without touching the clipboard; only falls back to
#        also copying to the clipboard when no editable cursor is found
# True: always copies to the clipboard as well, regardless of whether a cursor was found
ALWAYS_COPY_TO_CLIPBOARD = False

# ---- Hotkey ----
MIN_PRESS_MS = 150  # Fn presses shorter than this are ignored, to filter out accidental taps
