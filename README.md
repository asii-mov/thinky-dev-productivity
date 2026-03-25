# Thinky Dev — Secure AI Coding Tools

Centralized configuration and onboarding for AI coding tools across the org.

## Features
- Spawn DigitalOcean droplets ready to use Claude code in a containerized environment, add your team easily using their GitHub usernames.
- Configure Claude Code to AWS Bedrock or other providers by simply running setup.sh
- Hardened images and networking used by default

TODO:
- Secure secrets management between local/remote
- Harden Codex
- Best practice for allowing AI to use API keys without exposing them
- Improve README.md for clarity and conciseness 

## Quickstart

```bash
git clone <this-repo>
cd thinky-dev-productivity

# 1. Create your config
cp config.yaml.example config.yaml
# Edit config.yaml — choose your provider (bedrock/anthropic) and uncomment the tools you use

# 2. Run setup
./setup.sh
```

## Supported Tools

| Tool | Automation Level | Notes |
|------|-----------------|-------|
| **Claude Code** | Fully automated | Configures settings.json, CLAUDE.md, and provider env vars |
| **Cursor** | Partial | Copies project rules automatically; global settings require manual GUI steps (see [Cursor Onboarding](configs/cursor/ONBOARDING.md)) |
| **Codex** | Fully automated | Configures config.toml and provider settings |

## Container Sandbox (Local Dev)

Run Claude Code and Codex in an isolated container with org configs baked in.

```bash
cd containers

# 1. Build the image (pulls org configs from configs/)
./build.sh

# 2. Create your .env with API keys
cp env.example .env
# Edit .env - add your ANTHROPIC_API_KEY (and optionally OPENAI_API_KEY for Codex)

# 3. Launch the sandbox
./run.sh ~/my-project
```

The container includes:
- Claude Code and Codex CLI pre-installed
- Org deny rules applied automatically
- `bypassPermissions` enabled (the container IS the sandbox)
- Named Docker volumes for shell history, Claude sessions, and GitHub CLI auth
- SSH agent forwarding from host

## Remote VM Sandbox (DigitalOcean)

Provision a hardened cloud VM with Claude Code and Codex ready to go.

```bash
cd remote
uv venv .venv && uv pip install -e .

# 1. Configure (DO token, SSH key, etc.)
# Edit ~/.config/thinky-remote/config.yaml or run:
.venv/bin/thinky-remote config

# 2. Create a sandbox
.venv/bin/thinky-remote create my-sandbox

# 3. SSH in (wait ~5 min for cloud-init on first create)
.venv/bin/thinky-remote ssh my-sandbox

# 4. Hibernate to save cost (snapshots + destroys the VM)
.venv/bin/thinky-remote hibernate my-sandbox

# 5. Wake it later (restores from snapshot)
.venv/bin/thinky-remote wake my-sandbox

# 6. Share with teammates (fetches their public keys from GitHub)
.venv/bin/thinky-remote share my-sandbox teammate1,teammate2

# 7. Destroy when done
.venv/bin/thinky-remote destroy my-sandbox
```

Each VM is provisioned with:
- Claude Code and Codex CLI installed and ready to use
- Docker available for container workflows
- UFW firewall (deny inbound, allow outbound, rate-limited SSH)
- fail2ban monitoring SSH
- Hardened SSH (no passwords, no X11, max 3 auth attempts)
- Optional Tailscale VPN (locks inbound to Tailscale only)

## Testing & Validation (for admins)

Before rolling this out to your team, run through these steps to verify everything works.

### Prerequisites

- `jq` installed (`sudo apt install jq` / `brew install jq`) — required for Claude Code settings merge
- AWS credentials configured if testing Bedrock provider
- `ANTHROPIC_API_KEY` set if testing Anthropic provider

### Test 1: Fresh install (Anthropic)

```bash
# Back up existing configs
cp ~/.claude/settings.json ~/.claude/settings.json.bak 2>/dev/null
cp ~/.claude/CLAUDE.md ~/.claude/CLAUDE.md.bak 2>/dev/null
cp ~/.codex/config.toml ~/.codex/config.toml.bak 2>/dev/null
rm -f ~/.claude/settings.json ~/.claude/CLAUDE.md ~/.codex/config.toml

# Run setup
cp config.yaml.example config.yaml
sed -i 's/^provider: bedrock/provider: anthropic/' config.yaml
sed -i 's/^aws_region:.*/#aws_region:/' config.yaml
sed -i 's/# - cursor/- cursor/' config.yaml
sed -i 's/# - codex/- codex/' config.yaml
./setup.sh

# Verify
cat ~/.claude/settings.json   # Should have org deny rules, no bedrock env vars
cat ~/.claude/CLAUDE.md        # Should have org CLAUDE.md placeholder
cat ~/.codex/config.toml       # Should have org baseline
ls .cursor/rules/              # Should contain org-standards.mdc

# Restore backups
cp ~/.claude/settings.json.bak ~/.claude/settings.json 2>/dev/null
cp ~/.claude/CLAUDE.md.bak ~/.claude/CLAUDE.md 2>/dev/null
cp ~/.codex/config.toml.bak ~/.codex/config.toml 2>/dev/null
```

### Test 2: Existing user (merge check)

```bash
# Run setup again with your real configs in place
./setup.sh

# Verify your existing settings weren't clobbered
cat ~/.claude/settings.json   # Should have BOTH org deny rules AND your personal settings
```

### Test 3: Bedrock provider (requires AWS access)

```bash
sed -i 's/^provider: anthropic/provider: bedrock/' config.yaml
sed -i 's/^#aws_region:.*/aws_region: us-east-1/' config.yaml
./setup.sh

# Verify
cat ~/.claude/settings.json | jq '.env'
# Should show: CLAUDE_CODE_USE_BEDROCK=1, AWS_REGION=us-east-1
```

### Test 4: Error handling

```bash
# Missing config.yaml
rm config.yaml
./setup.sh            # Should error: "config.yaml not found"

# Invalid provider
echo 'provider: gcp' > config.yaml
./setup.sh            # Should error: "Invalid provider"

# Missing region for bedrock
printf 'provider: bedrock\naws_region:\ntools:\n  - claude-code\n' > config.yaml
./setup.sh            # Should error: "aws_region is required"
```

### Rollout checklist

- [ ] All tests above pass
- [ ] Add org-specific coding standards to `configs/claude-code/CLAUDE.md` if needed
- [ ] Review deny rules in `configs/claude-code/settings.json` — add any org-specific sensitive paths
- [ ] Review Codex sandbox/approval settings in `configs/codex/config.toml`
- [ ] Update `<this-repo>` in the Quickstart with your actual repo URL
- [ ] Share repo link with team + point them at the Quickstart section

## Contributing

We encourage everyone to submit PRs to improve tool configs:

- **Add or update tool configs** - edit files under `configs/<tool>/`
- **Add Cursor rules** - add `.mdc` files to `configs/cursor/rules/`
- **Improve the container** - edit `containers/Dockerfile` or `post_install.py`
- **Improve the VM provisioning** - edit `remote/thinky_remote/templates/cloud-init.yaml`
- **Improve onboarding docs** - edit any `ONBOARDING.md` or this README

Please test your changes with `./setup.sh` before submitting. For container changes, run `containers/build.sh` to verify the image builds.

## Provider Options

### AWS Bedrock

Set `provider: bedrock` and `aws_region` in your `config.yaml`.

**With SSO (recommended):** Set `aws_profile` to your SSO profile name. The setup script configures Claude Code to automatically refresh credentials via `aws sso login` when they expire mid-session.

```yaml
provider: bedrock
aws_region: us-east-1
aws_profile: my-sso-profile
```

**Without SSO:** Leave `aws_profile` empty. Credentials are read from `aws configure`, environment variables, or instance roles.

### Anthropic API

Set `provider: anthropic` in your `config.yaml`. Requires `ANTHROPIC_API_KEY` set in your environment.
