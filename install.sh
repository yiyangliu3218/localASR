#!/bin/bash
# LocalASR installer. Works two ways:
#
#   One-liner on a new Mac (downloads everything into ~/localASR):
#     curl -fsSL https://raw.githubusercontent.com/yiyangliu3218/localASR/main/install.sh | bash
#
#   From an existing clone:
#     ./install.sh
#
# Options (environment variables):
#   LOCALASR_DIR=~/somewhere    where to install (one-liner mode; default ~/localASR)
#   LOCALASR_BRANCH=main        branch to install (one-liner mode)
#   LOCALASR_WHISPER=1          also install the optional Whisper engine (~800 MB extra, Apple Silicon only)
#   LOCALASR_SKIP_MODELS=1      don't pre-download the speech model now (it downloads on first launch)
#   LOCALASR_NO_LOGIN=1         build LocalASR.app but don't start it at login
#
# Re-running it updates an existing install.
set -euo pipefail

REPO="yiyangliu3218/localASR"
BRANCH="${LOCALASR_BRANCH:-main}"
BIN_DIR="$HOME/.local/bin"

say() { printf '\033[1m==> %s\033[0m\n' "$*"; }
die() { printf '\033[31mError: %s\033[0m\n' "$*" >&2; exit 1; }

# Everything runs inside main(), called on the last line, so that with `curl | bash`
# the whole script is downloaded before anything executes.
main() {
[ "$(uname -s)" = "Darwin" ] || die "LocalASR only runs on macOS."

# ---- 1. Get the code -------------------------------------------------------
SCRIPT_DIR=""
if [ -n "${BASH_SOURCE[0]:-}" ] && [ -f "${BASH_SOURCE[0]}" ]; then
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fi

if [ -n "$SCRIPT_DIR" ] && [ -f "$SCRIPT_DIR/app.py" ] && [ -f "$SCRIPT_DIR/pyproject.toml" ]; then
  DIR="$SCRIPT_DIR"  # running from a clone: install in place
  say "Installing from $DIR"
else
  DIR="${LOCALASR_DIR:-$HOME/localASR}"
  if [ -d "$DIR/.git" ]; then
    say "Updating $DIR"
    git -C "$DIR" pull --ff-only origin "$BRANCH"
  elif xcode-select -p >/dev/null 2>&1; then
    [ -e "$DIR" ] && die "$DIR already exists and is not a LocalASR checkout; set LOCALASR_DIR to another path."
    say "Downloading LocalASR into $DIR"
    git clone --depth 1 --branch "$BRANCH" "https://github.com/$REPO.git" "$DIR"
  else
    # No git (Xcode Command Line Tools not installed): fetch a tarball instead
    say "Downloading LocalASR into $DIR (no git found, using a tarball)"
    mkdir -p "$DIR"
    curl -fsSL "https://github.com/$REPO/archive/refs/heads/$BRANCH.tar.gz" \
      | tar -xz -C "$DIR" --strip-components 1
  fi
fi
cd "$DIR"

# ---- 2. uv (fetches Python 3.13 itself, so no system Python is needed) -----
if command -v uv >/dev/null 2>&1; then
  UV="$(command -v uv)"
elif [ -x "$BIN_DIR/uv" ]; then
  UV="$BIN_DIR/uv"
else
  say "Installing uv (Python package manager) into $BIN_DIR"
  curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR="$BIN_DIR" UV_NO_MODIFY_PATH=1 sh
  UV="$BIN_DIR/uv"
fi

# ---- 3. Virtual environment + dependencies ---------------------------------
say "Creating Python 3.13 environment"
"$UV" venv --quiet --allow-existing --python 3.13 .venv

EXTRAS=""
if [ "${LOCALASR_WHISPER:-0}" = "1" ]; then
  [ "$(uname -m)" = "arm64" ] || die "The Whisper engine needs an Apple Silicon Mac."
  EXTRAS="[mlx]"
fi
say "Installing dependencies"
"$UV" pip install --quiet --python .venv/bin/python -e ".$EXTRAS"

# ---- 4. Speech model (~1 GB download, ~1.1 GB on disk) ----------------------
if [ "${LOCALASR_SKIP_MODELS:-0}" != "1" ]; then
  say "Downloading the speech model (one time, ~1 GB)"
  .venv/bin/python -c '
import config, model_download as m
if config.ENGINE == "sensevoice":
    m.ensure_model_dir(config.MODELS_DIR, m.SENSEVOICE)
m.ensure_file(config.MODELS_DIR, m.SILERO_VAD)
' || echo "Model download failed; it will be retried when the app starts."
fi

# ---- 5. `localasr` command --------------------------------------------------
mkdir -p "$BIN_DIR"
ln -sf "$DIR/.venv/bin/localasr" "$BIN_DIR/localasr"
case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *)
    RC="$HOME/.zshrc"; [ "${SHELL##*/}" = "bash" ] && RC="$HOME/.bash_profile"
    if ! grep -qs 'LocalASR' "$RC"; then
      printf '\n# LocalASR\nexport PATH="%s:$PATH"\n' "$BIN_DIR" >> "$RC"
      say "Added $BIN_DIR to PATH in $RC (open a new terminal for it to take effect)"
    fi
    ;;
esac

# ---- 6. LocalASR.app + start at login ------------------------------------
if bash macos/make_app.sh; then
cat <<EOF

LocalASR is installed as ~/Applications/LocalASR.app and is running in the menu bar.
It starts by itself when you log in; open it from Launchpad / Spotlight if you quit it.

First run: in System Settings > Privacy & Security, turn on "LocalASR" under both
"Accessibility" and "Input Monitoring" (use + and pick ~/Applications/LocalASR.app if
it isn't listed), allow the microphone when asked, then quit LocalASR from its menu
bar icon and open it again.

Then hold Fn, speak, release: the text is typed at your cursor.
Logs: ~/Library/Logs/LocalASR/LocalASR.log
EOF
return
fi

cat <<EOF

LocalASR is installed (without the .app, see above).

Start it:   localasr        (or: $DIR/run.sh)

First launch: macOS will ask for permissions. In System Settings > Privacy & Security,
allow your terminal app (Terminal / iTerm / ...) under both "Accessibility" and
"Input Monitoring", then quit and reopen the terminal and run localasr again.

Then hold Fn, speak, release: the text is typed at your cursor.
EOF
}

main "$@"
