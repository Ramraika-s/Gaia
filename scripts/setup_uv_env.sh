#!/usr/bin/env bash
set -euo pipefail

# scripts/setup_uv_env.sh
# Pins compatible Python 3.12 via uv and synchronizes dependencies for Gaia.

echo "=== Gaia Python Environment Setup (uv + Python 3.12) ==="

# 1. Verify uv installation
if ! command -v uv &> /dev/null; then
    echo "ERROR: 'uv' package manager is not installed on this system."
    echo "To install official uv, run:"
    echo "  curl -LsSf https://astral.sh/uv/install.sh | sh"
    read -rp "Would you like to install uv now? [y/N]: " choice
    case "$choice" in
        [yY][eE][sS]|[yY])
            echo "Installing uv..."
            curl -LsSf https://astral.sh/uv/install.sh | sh
            export PATH="$HOME/.local/bin:$PATH"
            ;;
        *)
            echo "Setup aborted. Please install uv and run this script again."
            exit 1
            ;;
    esac
fi

echo "Using uv binary: $(command -v uv) ($(uv --version))"

# 2. Fetch and pin Python 3.12 (bypassing bleeding-edge system Python on Fedora 45)
echo "Installing and pinning Python 3.12..."
uv python install 3.12
uv python pin 3.12

# 3. Synchronize virtual environment with pinned dependencies
echo "Synchronizing dependencies via uv sync..."
uv sync

# 4. Verify the active virtual environment
echo "Verifying environment:"
uv run python --version
echo "Verifying core dependencies..."
uv run python -c "import torch, numpy, duckdb, aiosqlite, pydantic, websockets, psutil; print('All core modules imported successfully: OK')"

echo "=== Gaia Environment Ready ==="
