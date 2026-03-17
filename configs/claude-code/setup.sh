#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROVIDER="${1:-}"
AWS_REGION="${2:-}"

CLAUDE_DIR="$HOME/.claude"
SETTINGS_FILE="$CLAUDE_DIR/settings.json"
ORG_SETTINGS="$SCRIPT_DIR/settings.json"
ORG_CLAUDE_MD="$SCRIPT_DIR/CLAUDE.md"

echo "==> Configuring Claude Code..."

# Ensure ~/.claude/ exists
mkdir -p "$CLAUDE_DIR"

# --- Merge settings.json (non-destructive) ---
if [ -f "$SETTINGS_FILE" ]; then
    echo "    Found existing $SETTINGS_FILE — merging org settings (existing keys preserved)"
    # Merge: org settings as base, user settings override
    # Requires jq for key-level merge
    if command -v jq &>/dev/null; then
        # Deep merge: user's file wins on conflicts, org deny rules are combined
        jq -s '
            .[0] as $org | .[1] as $user |
            ($org * $user) |
            .permissions.deny = (($org.permissions.deny // []) + ($user.permissions.deny // []) | unique)
        ' "$ORG_SETTINGS" "$SETTINGS_FILE" > "$SETTINGS_FILE.tmp"
        mv "$SETTINGS_FILE.tmp" "$SETTINGS_FILE"
    else
        echo "    WARNING: jq not found — cannot merge settings. Install jq or manually merge:"
        echo "    $ORG_SETTINGS -> $SETTINGS_FILE"
    fi
else
    echo "    Creating $SETTINGS_FILE from org baseline"
    cp "$ORG_SETTINGS" "$SETTINGS_FILE"
fi

# --- Set provider-specific env vars in settings.json ---
if command -v jq &>/dev/null; then
    case "$PROVIDER" in
        bedrock)
            echo "    Setting provider: AWS Bedrock (region: $AWS_REGION)"
            jq --arg region "$AWS_REGION" '
                .env.CLAUDE_CODE_USE_BEDROCK = "1" |
                .env.AWS_REGION = $region
            ' "$SETTINGS_FILE" > "$SETTINGS_FILE.tmp"
            mv "$SETTINGS_FILE.tmp" "$SETTINGS_FILE"
            ;;
        anthropic)
            echo "    Setting provider: Anthropic API"
            # Remove bedrock vars if they exist from a previous run
            jq 'del(.env.CLAUDE_CODE_USE_BEDROCK, .env.AWS_REGION)' \
                "$SETTINGS_FILE" > "$SETTINGS_FILE.tmp"
            mv "$SETTINGS_FILE.tmp" "$SETTINGS_FILE"
            if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
                echo "    NOTE: ANTHROPIC_API_KEY is not set in your environment."
                echo "    Set it via: export ANTHROPIC_API_KEY=<your-key>"
            fi
            ;;
        *)
            echo "    WARNING: Unknown provider '$PROVIDER' — skipping env var setup"
            ;;
    esac
else
    echo "    WARNING: jq not found — cannot set provider env vars in settings.json"
    echo "    Install jq and re-run, or manually set env vars."
fi

# --- CLAUDE.md ---
# Place org CLAUDE.md in ~/.claude/ as a global reference
GLOBAL_CLAUDE_MD="$CLAUDE_DIR/CLAUDE.md"
if [ -f "$GLOBAL_CLAUDE_MD" ]; then
    # Check if org standards are already present
    if grep -q "# Org Coding Standards" "$GLOBAL_CLAUDE_MD" 2>/dev/null; then
        echo "    Org standards already in $GLOBAL_CLAUDE_MD — skipping"
    else
        echo "    Appending org standards to existing $GLOBAL_CLAUDE_MD"
        printf '\n\n' >> "$GLOBAL_CLAUDE_MD"
        cat "$ORG_CLAUDE_MD" >> "$GLOBAL_CLAUDE_MD"
    fi
else
    echo "    Creating $GLOBAL_CLAUDE_MD from org baseline"
    cp "$ORG_CLAUDE_MD" "$GLOBAL_CLAUDE_MD"
fi

echo "==> Claude Code configuration complete."
