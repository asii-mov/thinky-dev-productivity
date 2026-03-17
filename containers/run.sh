#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGE_NAME="thinky-dev-sandbox:latest"

# --- Parse arguments ---
PROJECT_DIR="${1:-.}"
PROJECT_DIR="$(cd "$PROJECT_DIR" && pwd)"
PROJECT_NAME="$(basename "$PROJECT_DIR")"

# --- Locate .env file ---
ENV_FILE="${THINKY_ENV_FILE:-$SCRIPT_DIR/.env}"
if [ ! -f "$ENV_FILE" ]; then
    echo "ERROR: .env file not found at $ENV_FILE"
    echo "Run:  cp env.example .env  (in the containers/ directory)"
    echo "Then fill in your API keys and re-run."
    exit 1
fi

# --- Check image exists ---
if ! docker image inspect "$IMAGE_NAME" &>/dev/null; then
    echo "Image $IMAGE_NAME not found. Building..."
    bash "$SCRIPT_DIR/build.sh"
fi

# --- Volume names (per-project) ---
VOL_HISTORY="thinky-${PROJECT_NAME}-history"
VOL_CLAUDE="thinky-${PROJECT_NAME}-claude"
VOL_CODEX="thinky-${PROJECT_NAME}-codex"
VOL_GH="thinky-${PROJECT_NAME}-gh"

# --- Container name ---
CONTAINER_NAME="thinky-${PROJECT_NAME}"

echo "Project:   $PROJECT_DIR"
echo "Container: $CONTAINER_NAME"
echo "Env file:  $ENV_FILE"
echo ""

# --- Ensure .gitconfig exists (bind mount requires it) ---
test -f "$HOME/.gitconfig" || touch "$HOME/.gitconfig"

# --- Build docker run args ---
DOCKER_ARGS=(
    --name "$CONTAINER_NAME"
    --rm
    -it
    --env-file "$ENV_FILE"
    # Volumes for state persistence
    -v "${VOL_HISTORY}:/commandhistory"
    -v "${VOL_CLAUDE}:/home/vscode/.claude"
    -v "${VOL_CODEX}:/home/vscode/.codex"
    -v "${VOL_GH}:/home/vscode/.config/gh"
    # Git config (read-only from host)
    -v "$HOME/.gitconfig:/home/vscode/.gitconfig:ro"
    # Project workspace
    -v "${PROJECT_DIR}:/workspace"
    # Capabilities for network isolation
    --cap-add=NET_ADMIN
    --cap-add=NET_RAW
    --init
    -w /workspace
)

# --- SSH agent forwarding (if available) ---
if [ -n "${SSH_AUTH_SOCK:-}" ]; then
    DOCKER_ARGS+=(-v "${SSH_AUTH_SOCK}:/ssh-agent" -e SSH_AUTH_SOCK=/ssh-agent)
    echo "SSH agent: forwarded"
fi

echo "Starting container..."
echo ""

# --- Run container ---
# First run post_install, then drop into shell
docker run "${DOCKER_ARGS[@]}" "$IMAGE_NAME" \
    bash -c "uv run --no-project /opt/post_install.py 2>&1 && exec zsh"
