#!/bin/bash
# Launch the local speech-to-text menu bar app
cd "$(dirname "$0")"
source .venv/bin/activate
python3 app.py
