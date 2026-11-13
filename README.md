# LocalASR

Offline push-to-talk dictation for macOS. **Hold Fn, speak, release** — the text is
typed at your cursor, in any app.

- **Fully local**: speech never leaves your Mac; after the one-time model download it
  works without a network.
- **Fast**: speech is transcribed phrase by phrase while you talk, so text appears
  ~0.1–0.3 s after you release Fn, however long you spoke.
- **Chinese + English**, including mixed (code-switched) speech, with punctuation.
  Default engine: [SenseVoice-Small](https://github.com/FunAudioLLM/SenseVoice) via
  [sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx). Optional: Whisper
  large-v3-turbo on the Apple Silicon GPU.

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/yiyangliu3218/localASR/main/install.sh | bash
```

That's the whole setup. It installs into `~/localASR`, sets up its own Python 3.13
(via [uv](https://github.com/astral-sh/uv), nothing touches your system Python),
downloads the speech model (~1 GB, one time) and adds a `localasr` command.

Requirements: a Mac, ideally Apple Silicon (developed and tested on M-series; the
default engine should also run on Intel Macs but that is untested).

<details>
<summary>Install options</summary>

Set these before `bash`, e.g. `curl -fsSL … | LOCALASR_WHISPER=1 bash`:

| Variable | Effect |
|---|---|
| `LOCALASR_DIR=~/path` | install somewhere other than `~/localASR` |
| `LOCALASR_WHISPER=1` | also install the Whisper engine (~800 MB more, Apple Silicon only) |
| `LOCALASR_SKIP_MODELS=1` | don't download the model now; it downloads on first launch |

From a clone instead: `git clone https://github.com/yiyangliu3218/localASR.git && cd localASR && ./install.sh`.
</details>

## Use

```bash
localasr
```

A menu bar icon appears. **The first time**, macOS needs two permissions for the
terminal app you launched it from (Terminal, iTerm, …): open **System Settings →
Privacy & Security** and enable it under both **Accessibility** (to type text) and
**Input Monitoring** (to see the Fn key). Then quit and reopen the terminal and run
`localasr` again.

| Icon | Meaning |
|---|---|
| ⏳ | Loading the model |
| 🎙 | Ready — hold Fn to speak |
| 🔴 | Recording |
| ⌛ | Transcribing |
| ⚠️ | Missing permission or model failed to load — open the menu for details / "Reload model" |

If no text field has focus when you release Fn, the text is copied to the clipboard
instead. Quit from the menu bar icon.

LocalASR takes over the Fn key's own press, so macOS no longer pops up the emoji
picker / switches input source when you use it; Fn + other keys (brightness, arrows,
…) still work. To turn that off, set `SUPPRESS_FN_SYSTEM_ACTION = False` in
`config.py`.

## Update / uninstall

```bash
# update: re-run the installer
curl -fsSL https://raw.githubusercontent.com/yiyangliu3218/localASR/main/install.sh | bash

# uninstall
rm -rf ~/localASR ~/.cache/localasr ~/.local/bin/localasr
```

## Configuration

Edit `~/localASR/config.py`, then restart `localasr`. The most useful options:

```python
ENGINE = "sensevoice"          # or "mlx-whisper" (install with LOCALASR_WHISPER=1)
CUSTOM_VOCABULARY = []         # names / jargon that keep getting misrecognized
OUTPUT_CHINESE = "simplified"  # "simplified" / "traditional" / "preserve"
TYPE_WHILE_SPEAKING = False    # True = type each phrase while Fn is still held
AUTO_TYPE = True               # False = only copy to the clipboard
ALWAYS_COPY_TO_CLIPBOARD = False
LANGUAGE = None                # Whisper only: force "zh" or "en"
```

## Troubleshooting

- **Nothing happens when I hold Fn**: check the menu bar icon. ⚠️ means a missing
  permission (see above). Otherwise look at the terminal: every dictation prints a
  `[诊断]` line with the recording length, volume and recognized text. A very short
  press (under ~0.2 s) records nothing — hold Fn while you speak.
- **Model download is slow or fails**: download these two files in a browser and put
  them, unextracted, in `~/.cache/localasr/models/`, then choose "Reload model":
  - `https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17.tar.bz2`
  - `https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/silero_vad.onnx`

  Or set `LOCALASR_DOWNLOAD_BASE` to a mirror of that release URL. Behind a
  TLS-inspecting proxy, set `SSL_CERT_FILE` to your proxy's CA bundle.
- **Text went into the wrong window**: focus moved before you released Fn. `Cmd+Z`
  to undo; set `AUTO_TYPE = False` for clipboard-only mode.

## Development

```bash
uv pip install --python .venv/bin/python -e ".[dev]"
.venv/bin/python -m pytest      # runs on any OS; macOS APIs are faked
```

## License

MIT, see [LICENSE](LICENSE).
