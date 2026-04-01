#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [[ -f ".venv/bin/activate" ]]; then
  source .venv/bin/activate
fi

PYTHON_BIN=""
if [[ -x ".venv/bin/python" ]]; then
  PYTHON_BIN="$(pwd)/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="$(command -v python3)"
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN="$(command -v python)"
else
  echo "No Python interpreter found. Install python3 or create .venv first." >&2
  exit 1
fi

# Reset terminal mode in case an extension left it in a bad state.
stty sane 2>/dev/null || true

# Avoid Python startup injection from VS Code Python terminal.
unset PYTHONSTARTUP
unset VSCODE_DEBUGPY_ADAPTER_ENDPOINTS
unset PYTHONINSPECT
unset PYTHONBREAKPOINT

# Use stable OpenCV-based auth backend by default; opt-in to face_recognition via env override.
export JARVIS_FACE_BACKEND="${JARVIS_FACE_BACKEND:-legacy}"

exec "$PYTHON_BIN" Main.py "$@"
