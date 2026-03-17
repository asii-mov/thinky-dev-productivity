"""Configuration management for thinky-remote."""

import os
from pathlib import Path

import yaml


CONFIG_DIR = Path.home() / ".config" / "thinky-remote"
CONFIG_FILE = CONFIG_DIR / "config.yaml"

DEFAULT_CONFIG = {
    "digitalocean_token": "",
    "tailscale_auth_key": "",
    "ssh_public_key": str(Path.home() / ".ssh" / "id_ed25519.pub"),
    "default_region": "nyc3",
    "default_size": "s-2vcpu-4gb",
    "default_image": "ubuntu-24-04-x64",
    "username": os.environ.get("USER", "dev"),
    "email": "",
    "full_name": "",
    "container_image": "thinky-dev-sandbox:latest",
}


def load_config() -> dict:
    """Load config from file, or return defaults."""
    if not CONFIG_FILE.exists():
        return DEFAULT_CONFIG.copy()

    with open(CONFIG_FILE) as f:
        data = yaml.safe_load(f) or {}

    config = DEFAULT_CONFIG.copy()
    config.update(data)
    return config


def save_config(config: dict) -> None:
    """Save config to file with restrictive permissions."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_DIR.chmod(0o700)

    with open(CONFIG_FILE, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)

    CONFIG_FILE.chmod(0o600)


def validate_config(config: dict) -> list[str]:
    """Return list of validation errors, empty if valid."""
    errors = []
    if not config.get("digitalocean_token"):
        errors.append("digitalocean_token is required")
    if not config.get("ssh_public_key"):
        errors.append("ssh_public_key is required")
    else:
        path = Path(config["ssh_public_key"]).expanduser()
        if not path.exists():
            errors.append(f"SSH public key not found: {path}")
        elif not path.name.endswith(".pub"):
            errors.append(f"SSH key must be a .pub file: {path}")
    return errors
