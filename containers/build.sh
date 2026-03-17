#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "==> Copying org configs into build context..."
cp "$REPO_DIR/configs/claude-code/settings.json" "$SCRIPT_DIR/org-configs/settings.json"
cp "$REPO_DIR/configs/claude-code/CLAUDE.md" "$SCRIPT_DIR/org-configs/CLAUDE.md"
cp "$REPO_DIR/configs/codex/config.toml" "$SCRIPT_DIR/org-configs/codex-config.toml"

echo "==> Building thinky-dev-sandbox image..."
docker build -t thinky-dev-sandbox:latest "$SCRIPT_DIR"

echo "==> Build complete: thinky-dev-sandbox:latest"
