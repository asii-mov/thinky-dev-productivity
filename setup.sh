#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="$SCRIPT_DIR/config.yaml"

# --- Check for config.yaml ---
if [ ! -f "$CONFIG_FILE" ]; then
    echo "ERROR: config.yaml not found."
    echo "Run:  cp config.yaml.example config.yaml"
    echo "Then edit config.yaml and re-run this script."
    exit 1
fi

# --- Parse YAML (lightweight, no yq dependency) ---
parse_yaml_value() {
    local key="$1"
    grep "^${key}:" "$CONFIG_FILE" | sed "s/^${key}:[[:space:]]*//" | sed 's/[[:space:]]*#.*//'
}

parse_yaml_list() {
    local key="$1"
    # Extract list items under a key, ignoring comments
    awk "/^${key}:/{found=1; next} found && /^[[:space:]]*-/{gsub(/^[[:space:]]*-[[:space:]]*/, \"\"); gsub(/[[:space:]]*#.*/, \"\"); print; next} found && /^[^[:space:]-]/{exit}" "$CONFIG_FILE"
}

PROVIDER="$(parse_yaml_value "provider")"
AWS_REGION="$(parse_yaml_value "aws_region")"

# --- Validate ---
if [ -z "$PROVIDER" ]; then
    echo "ERROR: 'provider' not set in config.yaml"
    exit 1
fi

case "$PROVIDER" in
    bedrock|anthropic) ;;
    *)
        echo "ERROR: Invalid provider '$PROVIDER'. Must be 'bedrock' or 'anthropic'."
        exit 1
        ;;
esac

if [ "$PROVIDER" = "bedrock" ] && [ -z "$AWS_REGION" ]; then
    echo "ERROR: 'aws_region' is required when provider is 'bedrock'."
    exit 1
fi

echo "Provider: $PROVIDER"
[ -n "$AWS_REGION" ] && echo "Region:   $AWS_REGION"
echo ""

# --- Run per-tool setup scripts ---
TOOLS="$(parse_yaml_list "tools")"
if [ -z "$TOOLS" ]; then
    echo "WARNING: No tools listed in config.yaml. Nothing to configure."
    exit 0
fi

SUMMARY_OK=""
SUMMARY_MANUAL=""

while IFS= read -r tool; do
    tool_script="$SCRIPT_DIR/configs/$tool/setup.sh"
    if [ ! -f "$tool_script" ]; then
        echo "WARNING: No setup script found for '$tool' at $tool_script — skipping"
        continue
    fi
    echo "────────────────────────────────────────"
    bash "$tool_script" "$PROVIDER" "$AWS_REGION"
    echo ""

    if [ "$tool" = "cursor" ]; then
        SUMMARY_MANUAL="$SUMMARY_MANUAL  - $tool (project rules configured; global settings need manual setup)\n"
    else
        SUMMARY_OK="$SUMMARY_OK  - $tool\n"
    fi
done <<< "$TOOLS"

# --- Summary ---
echo "════════════════════════════════════════"
echo "Setup complete."
echo ""
if [ -n "$SUMMARY_OK" ]; then
    echo "Fully configured:"
    printf "%b" "$SUMMARY_OK"
fi
if [ -n "$SUMMARY_MANUAL" ]; then
    echo ""
    echo "Requires manual steps:"
    printf "%b" "$SUMMARY_MANUAL"
fi
