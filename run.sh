#!/bin/bash
# Launch the LocalASR menu bar app (after ./install.sh)
cd "$(dirname "$0")"
exec .venv/bin/python app.py
