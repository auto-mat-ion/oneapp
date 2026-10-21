#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")"

echo "Pulling latest code..."
git pull --ff-only origin main

python311=""
if command -v python3.11 >/dev/null 2>&1; then
    python_version="$(python3.11 -c 'import platform; print(platform.python_version())')"
    if [[ "$python_version" == "3.11.9" ]]; then
        python311="$(command -v python3.11)"
    fi
fi

if [[ -z "$python311" ]]; then
    echo "Installing Python 3.11.9..."
    if ! command -v curl >/dev/null 2>&1; then
        echo "Error: curl is required to install Python 3.11.9. Install it with: sudo apt install curl"
        exit 1
    fi
    if ! command -v uv >/dev/null 2>&1; then
        curl -LsSf https://astral.sh/uv/install.sh | sh
        export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
    fi
    uv python install 3.11.9
    python311="$(uv python find 3.11.9)"
fi

if [[ ! -d .venv ]]; then
    echo "Creating virtual environment..."
    if ! "$python311" -m venv .venv; then
        echo "Error: could not create .venv with Python 3.11.9."
        exit 1
    fi
fi

venv_version="$(.venv/bin/python -c 'import platform; print(platform.python_version())')"
if [[ "$venv_version" != "3.11.9" ]]; then
    echo "Error: .venv uses Python $venv_version; recreate it with Python 3.11.9."
    exit 1
fi

echo "Updating dependencies..."
.venv/bin/python -m pip install --quiet --upgrade pip
.venv/bin/python -m pip install -r requirements.txt

echo "Starting main.py..."
printf '4\n' | .venv/bin/python main.py