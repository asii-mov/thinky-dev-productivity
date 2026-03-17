#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RULES_SRC="$SCRIPT_DIR/rules"
PROJECT_DIR="${3:-.}"  # Third arg is project dir, default to current dir
RULES_DST="$PROJECT_DIR/.cursor/rules"

echo "==> Configuring Cursor..."

# --- Copy project rules ---
if [ -d "$RULES_SRC" ] && [ -n "$(ls -A "$RULES_SRC" 2>/dev/null)" ]; then
    mkdir -p "$RULES_DST"
    for rule in "$RULES_SRC"/*.mdc; do
        [ -f "$rule" ] || continue
        name="$(basename "$rule")"
        if [ -f "$RULES_DST/$name" ]; then
            echo "    Rule $name already exists in $RULES_DST — skipping"
        else
            cp "$rule" "$RULES_DST/$name"
            echo "    Copied rule: $name -> $RULES_DST/"
        fi
    done
else
    echo "    No rules found in $RULES_SRC"
fi

# --- Manual steps reminder ---
echo ""
echo "    ┌─────────────────────────────────────────────────────┐"
echo "    │  Cursor global settings require manual configuration │"
echo "    │  See: configs/cursor/ONBOARDING.md                   │"
echo "    └─────────────────────────────────────────────────────┘"
echo ""

echo "==> Cursor configuration complete (project rules only)."
