#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

CODEX_DIR="$HOME/.codex"
CONFIG_FILE="$CODEX_DIR/config.toml"
ORG_CONFIG="$SCRIPT_DIR/config.toml"

echo "==> Configuring Codex CLI..."

# Ensure ~/.codex/ exists
mkdir -p "$CODEX_DIR"

# --- Place config.toml ---
if [ -f "$CONFIG_FILE" ]; then
    echo "    Found existing $CONFIG_FILE"
    echo "    Org baseline saved to $CONFIG_FILE.org-baseline for reference"
    cp "$ORG_CONFIG" "$CONFIG_FILE.org-baseline"
    echo "    NOTE: Please manually merge any new org settings into your config."
    echo "    Diff: diff $CONFIG_FILE $CONFIG_FILE.org-baseline"
else
    echo "    Creating $CONFIG_FILE from org baseline"
    cp "$ORG_CONFIG" "$CONFIG_FILE"
fi

echo "==> Codex CLI configuration complete."
