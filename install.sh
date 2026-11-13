#!/bin/bash
set -e

cd "$(dirname "$0")"

python3 -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
if [ "$(uname -m)" = "arm64" ]; then
  python -m pip install -e ".[mlx]"   # keep the optional Apple-GPU Whisper engine available
else
  python -m pip install -e .
fi

echo "Installed. Run with ./run.sh"
