#!/bin/bash
set -e

cd "$(dirname "$0")"

python3 -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -e .

echo "Installed. Run with ./run.sh"
