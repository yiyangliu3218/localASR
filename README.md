# LocalASR

An offline, push-to-talk-with-Fn, menu bar dictation tool for Apple Silicon Macs.

Hold **Fn** to speak; on release, the text is typed at the current cursor (Chinese
output is converted to Simplified by default, configurable). Only when no editable
cursor is found does it additionally copy the text to the clipboard.

Recognition runs locally with **SenseVoice-Small** (via `sherpa-onnx`, default) or
**Whisper large-v3-turbo** (`mlx-whisper`, Apple Silicon GPU). Speech is cut at
natural pauses and each phrase is transcribed *while you are still talking*, so the
wait after releasing Fn is ~0.1–0.2 s regardless of how long you dictated.
See [docs/REVIEW_AND_BENCHMARK.md](docs/REVIEW_AND_BENCHMARK.md) for measurements.

Fully local inference — no network calls, no audio ever uploaded. Supports Chinese
and English, including code-switched speech, with automatic language detection.
Models are downloaded on first run (SenseVoice from GitHub releases into
`~/.cache/localasr/models`, Whisper from Hugging Face); after that it works fully offline.

## Requirements

- Apple Silicon (M-series) Mac
- Python 3.13 (the only version tested so far)

## Install

```bash
git clone https://github.com/yiyangliu3218/localASR.git
cd localASR
./install.sh
```

`install.sh` creates a virtual environment (`.venv`) and installs dependencies
(the first run may take a few minutes to download everything).

## Before first use

### 1. Free up the Fn key (important)

System Settings → Keyboard:

- Set "Press 🌐/Fn key to" to **No Action** (otherwise it'll also pop up the emoji
  picker or trigger system dictation)
- If "Press Fn key twice" for dictation is enabled, it's best to turn that off too,
  so it doesn't interfere with this tool's recording

### 2. Grant permissions

On first run, if permissions are missing, the app will show an error. Go to
**System Settings → Privacy & Security** and add the terminal app you use to run
this program (Terminal / iTerm, etc.) to both:

- **Accessibility** — used to simulate keyboard input
- **Input Monitoring** — used to globally listen for the Fn key

After granting these, **fully quit and reopen your terminal** before running again.

## Run

```bash
./run.sh
```

A menu bar icon will appear:

| Icon | Meaning |
|---|---|
| ⏳ | Loading the model (downloaded automatically on first run, fully offline after that) |
| 🎙 | Ready — hold Fn to speak |
| 🔴 | Recording |
| ⌛ | Transcribing |
| ⚠️ | Missing permissions (hotkey listener failed to start), or model failed to load |

Usage: **hold Fn to speak → release → text appears at the cursor** (also copied to
the clipboard if no editable cursor is found).

If the model fails to load (e.g. download interrupted, no network, out of disk
space), the menu bar icon turns ⚠️; opening the menu shows "View error" (the
actual error message) and "Reload model" (retry without restarting the whole app).

Quit: click the menu bar icon → Quit.

## Configuration (`config.py`)

```python
ENGINE = "sensevoice"    # or "mlx-whisper" (original engine, Apple Silicon GPU)
STREAMING = True         # transcribe phrase by phrase while you talk (low release latency)
TYPE_WHILE_SPEAKING = False  # True = type each phrase immediately, while Fn is still held
MODEL_REPO = "mlx-community/whisper-large-v3-turbo"  # only for ENGINE = "mlx-whisper"
LANGUAGE = None          # Whisper only: None = auto-detect; can also force "zh" or "en"
CUSTOM_VOCABULARY = []   # jargon/names that keep getting misrecognized — add them here
OUTPUT_CHINESE = "simplified"  # "simplified" / "traditional" / "preserve" (don't convert model output)
AUTO_TYPE = True         # False = only copy to clipboard, don't auto-type
ALWAYS_COPY_TO_CLIPBOARD = False  # True = always also copy to clipboard, regardless of cursor detection
MAX_RECORD_SECONDS = 300 # max length of a single recording
```

After editing `config.py`, quit the menu bar app and rerun `./run.sh` for changes
to take effect. Changing `MODEL_REPO` will download the new model from Hugging
Face on next launch (other options under the `mlx-community` org include
quantized variants like `whisper-large-v3-turbo-q4` — smaller download and
faster, but somewhat less accurate).

## Troubleshooting

- **Holding Fn does nothing**: most likely a missing permission — check whether
  the menu bar icon is ⚠️; or the system Fn key behavior wasn't disabled and is
  intercepting it first.
- **Text got typed into the wrong window**: this means focus wasn't where you
  expected when you released Fn. Press `Cmd+Z` to undo, then optionally set
  `AUTO_TYPE = False` in `config.py` to switch to clipboard-only mode.
- **Inaccurate recognition / poor mixed Chinese-English handling**: try forcing
  `LANGUAGE = "zh"` / `"en"` (gives up automatic code-switch detection in
  exchange for accuracy).

## Tests & benchmark

```bash
pip install -e ".[dev]"
python -m pytest                                   # unit tests (no Mac / models needed)
bench/download_models.sh ~/.cache/localasr/models  # free models, ~4 GB
python -m pytest                                   # now also runs real-model integration tests
python bench/run_bench.py --models-root ~/.cache/localasr/models --mlx   # add --mlx on Apple Silicon
python bench/bench_realtime.py --models-root ~/.cache/localasr/models
```

## License

MIT, see [LICENSE](LICENSE).
