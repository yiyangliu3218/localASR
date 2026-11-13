#!/bin/bash
# Download free, offline ASR models (sherpa-onnx builds, from GitHub releases).
set -e
DEST="${1:-$HOME/asr-models}"
mkdir -p "$DEST" && cd "$DEST"
B=https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models
for m in \
  sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17 \
  sherpa-onnx-whisper-turbo \
  sherpa-onnx-paraformer-zh-2024-03-09 \
  sherpa-onnx-streaming-zipformer-bilingual-zh-en-2023-02-20 \
  sherpa-onnx-streaming-paraformer-bilingual-zh-en; do
  [ -d "$m" ] || { curl -L -o "$m.tar.bz2" "$B/$m.tar.bz2" && tar xjf "$m.tar.bz2" && rm "$m.tar.bz2"; }
done
[ -f silero_vad.onnx ] || curl -L -o silero_vad.onnx "$B/silero_vad.onnx"
echo "Models in $DEST"
