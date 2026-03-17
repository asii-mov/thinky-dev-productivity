#!/usr/bin/env python3
"""Post-install configuration for Thinky Dev Sandbox.

Runs on container creation to set up:
- Onboarding bypass (when CLAUDE_CODE_OAUTH_TOKEN is set)
- Claude settings merged with org baseline (bypassPermissions mode)
- Codex config from org baseline
- Tmux configuration
- Directory ownership fixes for mounted volumes
"""

import contextlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ORG_SETTINGS = Path("/opt/org-settings.json")
ORG_CLAUDE_MD = Path("/opt/org-CLAUDE.md")
ORG_CODEX_CONFIG = Path("/opt/org-codex-config.toml")


def setup_onboarding_bypass():
    """Bypass the interactive onboarding wizard when CLAUDE_CODE_OAUTH_TOKEN is set."""
    token = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", "").strip()
    if not token:
        print(
            "[post_install] No CLAUDE_CODE_OAUTH_TOKEN set, skipping onboarding bypass",
            file=sys.stderr,
        )
        return

    claude_json = Path.home() / ".claude.json"

    print("[post_install] Running claude -p to populate auth state...", file=sys.stderr)
    try:
        result = subprocess.run(
            ["claude", "-p", "ok"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            print(
                f"[post_install] claude -p exited {result.returncode}: "
                f"{result.stderr.strip()}",
                file=sys.stderr,
            )
    except subprocess.TimeoutExpired:
        print(
            "[post_install] claude -p timed out (expected on cold start)",
            file=sys.stderr,
        )
    except (FileNotFoundError, OSError) as e:
        print(
            f"[post_install] Warning: could not run claude ({e}) — "
            "onboarding bypass skipped",
            file=sys.stderr,
        )
        return

    if not claude_json.exists():
        print(
            f"[post_install] Warning: {claude_json} not created by claude -p — "
            "onboarding bypass skipped",
            file=sys.stderr,
        )
        return

    config: dict = {}
    try:
        config = json.loads(claude_json.read_text())
    except json.JSONDecodeError as e:
        print(
            f"[post_install] Warning: {claude_json} has invalid JSON ({e}), "
            "starting fresh",
            file=sys.stderr,
        )

    config["hasCompletedOnboarding"] = True
    claude_json.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    print(
        f"[post_install] Onboarding bypass configured: {claude_json}", file=sys.stderr
    )


def setup_claude_settings():
    """Configure Claude Code with org settings + bypassPermissions."""
    claude_dir = Path.home() / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)

    settings_file = claude_dir / "settings.json"

    # Load existing user settings (from volume) or start fresh
    user_settings = {}
    if settings_file.exists():
        with contextlib.suppress(json.JSONDecodeError):
            user_settings = json.loads(settings_file.read_text())

    # Load org baseline
    org_settings = {}
    if ORG_SETTINGS.exists():
        with contextlib.suppress(json.JSONDecodeError):
            org_settings = json.loads(ORG_SETTINGS.read_text())

    # Merge: org as base, user overrides, deny rules combined
    merged = {**org_settings, **user_settings}

    # Combine deny rules from both
    org_deny = org_settings.get("permissions", {}).get("deny", [])
    user_deny = user_settings.get("permissions", {}).get("deny", [])
    combined_deny = sorted(set(org_deny + user_deny))

    if "permissions" not in merged:
        merged["permissions"] = {}
    merged["permissions"]["deny"] = combined_deny

    # Enable bypassPermissions — the container IS the sandbox
    merged["permissions"]["defaultMode"] = "bypassPermissions"

    settings_file.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")
    print(
        f"[post_install] Claude settings configured: {settings_file}", file=sys.stderr
    )


def setup_claude_md():
    """Place org CLAUDE.md if not already present."""
    claude_dir = Path.home() / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)
    target = claude_dir / "CLAUDE.md"

    if target.exists():
        content = target.read_text()
        if "# Org Coding Standards" in content:
            print("[post_install] Org CLAUDE.md already present, skipping", file=sys.stderr)
            return
        # Append org standards to existing
        print("[post_install] Appending org standards to existing CLAUDE.md", file=sys.stderr)
        with open(target, "a", encoding="utf-8") as f:
            f.write("\n\n")
            f.write(ORG_CLAUDE_MD.read_text())
    elif ORG_CLAUDE_MD.exists():
        shutil.copy2(ORG_CLAUDE_MD, target)
        print(f"[post_install] Org CLAUDE.md installed: {target}", file=sys.stderr)


def setup_codex_config():
    """Place org Codex config if not already present."""
    codex_dir = Path.home() / ".codex"
    codex_dir.mkdir(parents=True, exist_ok=True)
    target = codex_dir / "config.toml"

    if target.exists():
        print("[post_install] Codex config exists, skipping", file=sys.stderr)
        return

    if ORG_CODEX_CONFIG.exists():
        shutil.copy2(ORG_CODEX_CONFIG, target)
        print(f"[post_install] Codex config installed: {target}", file=sys.stderr)


def setup_tmux_config():
    """Configure tmux with 200k history, mouse support, and vi keys."""
    tmux_conf = Path.home() / ".tmux.conf"

    if tmux_conf.exists():
        print("[post_install] Tmux config exists, skipping", file=sys.stderr)
        return

    config = """\
# 200k line scrollback history
set-option -g history-limit 200000

# Enable mouse support
set -g mouse on

# Use vi keys in copy mode
setw -g mode-keys vi

# Start windows and panes at 1, not 0
set -g base-index 1
setw -g pane-base-index 1

# Renumber windows when one is closed
set -g renumber-windows on

# Faster escape time for vim
set -sg escape-time 10

# True color support
set -g default-terminal "tmux-256color"
set -ag terminal-overrides ",xterm-256color:RGB"

# Status bar
set -g status-style 'bg=#333333 fg=#ffffff'
set -g status-left '[#S] '
set -g status-right '%Y-%m-%d %H:%M'
"""
    tmux_conf.write_text(config, encoding="utf-8")
    print(f"[post_install] Tmux configured: {tmux_conf}", file=sys.stderr)


def fix_directory_ownership():
    """Fix ownership of mounted volumes that may have root ownership."""
    uid = os.getuid()
    gid = os.getgid()

    dirs_to_fix = [
        Path.home() / ".claude",
        Path.home() / ".codex",
        Path("/commandhistory"),
        Path.home() / ".config" / "gh",
    ]

    for dir_path in dirs_to_fix:
        if dir_path.exists():
            try:
                stat_info = dir_path.stat()
                if stat_info.st_uid != uid:
                    subprocess.run(
                        ["sudo", "chown", "-R", f"{uid}:{gid}", str(dir_path)],
                        check=True,
                        capture_output=True,
                    )
                    print(
                        f"[post_install] Fixed ownership: {dir_path}", file=sys.stderr
                    )
            except (PermissionError, subprocess.CalledProcessError) as e:
                print(
                    f"[post_install] Warning: Could not fix ownership of {dir_path}: {e}",
                    file=sys.stderr,
                )


def setup_global_gitignore():
    """Set up global gitignore and local git config."""
    home = Path.home()
    gitignore = home / ".gitignore_global"
    local_gitconfig = home / ".gitconfig.local"
    host_gitconfig = home / ".gitconfig"

    patterns = """\
# Claude Code
.claude/

# macOS
.DS_Store
._*

# Python
*.pyc
__pycache__/
*.egg-info/
.venv/
venv/

# Node
node_modules/
.npm/

# Editors
*.swp
*~
.idea/
.vscode/

# Env files
.env.local
.env.*.local
"""
    gitignore.write_text(patterns, encoding="utf-8")
    print(f"[post_install] Global gitignore created: {gitignore}", file=sys.stderr)

    local_config = f"""\
# Container-local git config
[include]
    path = {host_gitconfig}

[core]
    excludesfile = {gitignore}
    pager = delta

[interactive]
    diffFilter = delta --color-only

[delta]
    navigate = true
    light = false
    line-numbers = true
    side-by-side = false

[merge]
    conflictstyle = diff3

[diff]
    colorMoved = default
"""
    local_gitconfig.write_text(local_config, encoding="utf-8")
    print(
        f"[post_install] Local git config created: {local_gitconfig}", file=sys.stderr
    )


def main():
    """Run all post-install configuration."""
    print("[post_install] Starting post-install configuration...", file=sys.stderr)

    setup_onboarding_bypass()
    setup_claude_settings()
    setup_claude_md()
    setup_codex_config()
    setup_tmux_config()
    fix_directory_ownership()
    setup_global_gitignore()

    print("[post_install] Configuration complete!", file=sys.stderr)


if __name__ == "__main__":
    main()
