#!/bin/bash
# Builds ~/Applications/LocalASR.app (a small launcher for this checkout) and, unless
# LOCALASR_NO_LOGIN=1, registers it to start at login and restart if it crashes.
#
#   macos/make_app.sh               build / update, then (re)start it
#   macos/make_app.sh --uninstall   stop it and remove the app and the login item
#
# Called by install.sh; safe to re-run. The app is only rebuilt when something that
# goes into it changes, because a rebuilt app needs its permissions granted again.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP="$HOME/Applications/LocalASR.app"
LABEL="local.localasr"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
DOMAIN="gui/$(id -u)"

stop_agent() { launchctl bootout "$DOMAIN/$LABEL" >/dev/null 2>&1 || true; }

if [ "${1:-}" = "--uninstall" ]; then
  stop_agent
  rm -f "$PLIST"
  rm -rf "$APP"
  echo "Removed LocalASR.app and its login item."
  exit 0
fi

xcode-select -p >/dev/null 2>&1 || {
  echo "Skipping LocalASR.app: needs the Xcode Command Line Tools (xcode-select --install)." >&2
  exit 1
}

VERSION="$(sed -n 's/^version = "\(.*\)"/\1/p' "$DIR/pyproject.toml" | head -1)"
HASH="$( (cat "$DIR/macos/launcher.c" "$DIR/macos/make_icon.py" "${BASH_SOURCE[0]}"; echo "$DIR $VERSION") | shasum | cut -c1-40)"

if [ "$(cat "$APP/Contents/Resources/build-hash" 2>/dev/null)" != "$HASH" ]; then
  TMP="$(mktemp -d)"
  B="$TMP/LocalASR.app/Contents"
  mkdir -p "$B/MacOS" "$B/Resources"
  clang -O2 -Wall -o "$B/MacOS/LocalASR" -DLOCALASR_DIR="\"$DIR\"" "$DIR/macos/launcher.c"
  "$DIR/.venv/bin/python" "$DIR/macos/make_icon.py" "$B/Resources/AppIcon.icns" \
    || echo "(could not draw the app icon; using the default one)" >&2
  cat > "$B/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>LocalASR</string>
  <key>CFBundleDisplayName</key><string>LocalASR</string>
  <key>CFBundleIdentifier</key><string>$LABEL</string>
  <key>CFBundleExecutable</key><string>LocalASR</string>
  <key>CFBundleIconFile</key><string>AppIcon</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>$VERSION</string>
  <key>CFBundleVersion</key><string>$VERSION</string>
  <key>LSMinimumSystemVersion</key><string>12.0</string>
  <key>LSUIElement</key><true/>
  <key>NSMicrophoneUsageDescription</key><string>LocalASR records your voice while you hold Fn and transcribes it on this Mac.</string>
</dict>
</plist>
EOF
  echo "$HASH" > "$B/Resources/build-hash"
  codesign --force --sign - --identifier "$LABEL" "$TMP/LocalASR.app" >/dev/null 2>&1
  stop_agent  # the old binary may be running
  mkdir -p "$HOME/Applications"
  rm -rf "$APP"
  mv "$TMP/LocalASR.app" "$APP"
  rm -rf "$TMP"
  echo "Built $APP"
fi

if [ "${LOCALASR_NO_LOGIN:-0}" = "1" ]; then
  stop_agent
  rm -f "$PLIST"
  exit 0
fi

mkdir -p "$HOME/Library/LaunchAgents"
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key><array><string>$APP/Contents/MacOS/LocalASR</string></array>
  <key>RunAtLoad</key><true/>
  <!-- restart after a crash, but not after "Quit" from the menu -->
  <key>KeepAlive</key><dict><key>SuccessfulExit</key><false/></dict>
  <key>ProcessType</key><string>Interactive</string>
</dict>
</plist>
EOF

# (Re)start so the running copy uses the current code
stop_agent
for _ in 1 2 3 4 5; do
  launchctl bootstrap "$DOMAIN" "$PLIST" 2>/dev/null && break
  sleep 1  # bootout finishes asynchronously
done
launchctl print "$DOMAIN/$LABEL" >/dev/null 2>&1 \
  && echo "LocalASR starts at login (and is running now)." \
  || echo "Could not register the login item; open $APP manually." >&2
