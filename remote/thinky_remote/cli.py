"""Thinky Remote CLI — manage DigitalOcean sandbox VMs."""

import subprocess
import sys
import time
from pathlib import Path

import click
import requests
from jinja2 import Template

from thinky_remote.api import DOClient
from thinky_remote.config import (
    load_config,
    save_config,
    validate_config,
)

TAG_PREFIX = "thinky-sandbox"


def get_client(config: dict) -> DOClient:
    """Create an authenticated DO client from config."""
    errors = validate_config(config)
    if errors:
        click.echo("Configuration errors:", err=True)
        for e in errors:
            click.echo(f"  - {e}", err=True)
        click.echo("\nRun: thinky-remote config", err=True)
        sys.exit(1)
    return DOClient(config["digitalocean_token"])


def render_cloud_init(config: dict) -> str:
    """Render cloud-init template with config values."""
    template_path = Path(__file__).parent / "templates" / "cloud-init.yaml"
    template_content = template_path.read_text()

    # Read SSH public key
    ssh_key_path = Path(config["ssh_public_key"]).expanduser()
    ssh_key_content = ssh_key_path.read_text().strip()

    template = Template(template_content)
    return template.render(
        username=config.get("username", "dev"),
        full_name=config.get("full_name", ""),
        email=config.get("email", ""),
        ssh_keys=[ssh_key_content],
        tailscale_auth_key=config.get("tailscale_auth_key", ""),
        container_image=config.get("container_image", ""),
    )


def find_droplet_by_name(client: DOClient, name: str) -> dict | None:
    """Find a droplet by its tag name."""
    tag = f"{TAG_PREFIX}:{name}"
    droplets = client.list_droplets(tag=tag)
    return droplets[0] if droplets else None


def find_snapshot_by_name(client: DOClient, name: str) -> dict | None:
    """Find a snapshot by name prefix."""
    prefix = f"thinky-{name}-"
    snapshots = client.list_snapshots()
    matching = [s for s in snapshots if s["name"].startswith(prefix)]
    if matching:
        # Return most recent
        matching.sort(key=lambda s: s["created_at"], reverse=True)
        return matching[0]
    return None


def ensure_ssh_key(client: DOClient, config: dict) -> int:
    """Ensure SSH key is on DigitalOcean, return its ID."""
    ssh_key_path = Path(config["ssh_public_key"]).expanduser()
    local_key = ssh_key_path.read_text().strip()

    # Check existing keys
    for key in client.list_ssh_keys():
        if key["public_key"].strip() == local_key:
            return key["id"]

    # Upload new key
    key_name = f"thinky-{config.get('username', 'dev')}"
    result = client.upload_ssh_key(key_name, local_key)
    click.echo(f"Uploaded SSH key: {key_name}")
    return result["id"]


@click.group()
def cli():
    """Thinky Remote — manage DigitalOcean sandbox VMs."""
    pass


@cli.command()
def config():
    """Configure DigitalOcean token, Tailscale key, and defaults."""
    current = load_config()

    click.echo("Thinky Remote Configuration")
    click.echo("=" * 40)

    current["digitalocean_token"] = click.prompt(
        "DigitalOcean API token",
        default=current.get("digitalocean_token", ""),
    )
    current["tailscale_auth_key"] = click.prompt(
        "Tailscale auth key (optional, leave empty to skip)",
        default=current.get("tailscale_auth_key", ""),
    )
    current["ssh_public_key"] = click.prompt(
        "SSH public key path",
        default=current.get("ssh_public_key", "~/.ssh/id_ed25519.pub"),
    )
    current["username"] = click.prompt(
        "VM username",
        default=current.get("username", "dev"),
    )
    current["email"] = click.prompt(
        "Git email",
        default=current.get("email", ""),
    )
    current["full_name"] = click.prompt(
        "Git full name",
        default=current.get("full_name", ""),
    )
    current["default_region"] = click.prompt(
        "Default region",
        default=current.get("default_region", "nyc3"),
    )
    current["default_size"] = click.prompt(
        "Default droplet size",
        default=current.get("default_size", "s-2vcpu-4gb"),
    )
    current["container_image"] = click.prompt(
        "Container image (empty to skip pre-pull)",
        default=current.get("container_image", "thinky-dev-sandbox:latest"),
    )

    save_config(current)
    click.echo(f"\nConfig saved to {current}")


@cli.command()
@click.argument("name")
@click.option("--region", default=None, help="DigitalOcean region slug")
@click.option("--size", default=None, help="Droplet size slug")
def create(name: str, region: str | None, size: str | None):
    """Create a new sandbox VM."""
    config = load_config()
    client = get_client(config)

    region = region or config["default_region"]
    size = size or config["default_size"]

    # Check if already exists
    existing = find_droplet_by_name(client, name)
    if existing:
        click.echo(f"Sandbox '{name}' already exists (ID: {existing['id']})")
        sys.exit(1)

    # Ensure SSH key is on DO
    ssh_key_id = ensure_ssh_key(client, config)

    # Render cloud-init
    user_data = render_cloud_init(config)

    tag = f"{TAG_PREFIX}:{name}"
    click.echo(f"Creating sandbox '{name}' in {region} ({size})...")

    droplet = client.create_droplet(
        name=f"thinky-{name}",
        region=region,
        size=size,
        image=config.get("default_image", "ubuntu-24-04-x64"),
        ssh_key_ids=[ssh_key_id],
        user_data=user_data,
        tags=[TAG_PREFIX, tag],
    )

    droplet_id = droplet["id"]
    click.echo(f"Droplet created (ID: {droplet_id}). Waiting for IP...")

    # Wait for IP
    ip = None
    for _ in range(30):
        ip = client.get_droplet_ip(droplet_id)
        if ip:
            break
        time.sleep(5)

    if ip:
        click.echo(f"\nSandbox '{name}' ready!")
        click.echo(f"  IP:  {ip}")
        click.echo(f"  SSH: ssh {config['username']}@{ip}")
        if config.get("tailscale_auth_key"):
            click.echo("  Tailscale: will auto-join once cloud-init completes (~2-3 min)")
    else:
        click.echo(f"\nDroplet created (ID: {droplet_id}) but IP not yet assigned.")
        click.echo("Check status with: thinky-remote list")


@cli.command("list")
def list_sandboxes():
    """List all sandbox VMs."""
    config = load_config()
    client = get_client(config)

    droplets = client.list_droplets(tag=TAG_PREFIX)

    if not droplets:
        click.echo("No sandboxes found.")
        return

    click.echo(f"{'Name':<25} {'IP':<18} {'Region':<8} {'Size':<18} {'Status':<10}")
    click.echo("-" * 79)
    for d in droplets:
        ip = "pending"
        for net in d.get("networks", {}).get("v4", []):
            if net["type"] == "public":
                ip = net["ip_address"]
                break
        click.echo(
            f"{d['name']:<25} {ip:<18} {d['region']['slug']:<8} "
            f"{d['size_slug']:<18} {d['status']:<10}"
        )


@cli.command()
@click.argument("name")
def ssh(name: str):
    """SSH into a sandbox VM."""
    config = load_config()
    client = get_client(config)

    droplet = find_droplet_by_name(client, name)
    if not droplet:
        click.echo(f"Sandbox '{name}' not found.", err=True)
        sys.exit(1)

    ip = None
    for net in droplet.get("networks", {}).get("v4", []):
        if net["type"] == "public":
            ip = net["ip_address"]
            break

    if not ip:
        click.echo(f"Sandbox '{name}' has no public IP.", err=True)
        sys.exit(1)

    username = config.get("username", "dev")
    ssh_key = Path(config["ssh_public_key"]).expanduser()
    identity = str(ssh_key).replace(".pub", "")

    click.echo(f"Connecting to {name} ({ip})...")
    subprocess.run(
        [
            "ssh",
            "-o", "StrictHostKeyChecking=accept-new",
            "-i", identity,
            f"{username}@{ip}",
        ],
    )


@cli.command()
@click.argument("name")
def hibernate(name: str):
    """Hibernate a sandbox (snapshot + destroy to save cost)."""
    config = load_config()
    client = get_client(config)

    droplet = find_droplet_by_name(client, name)
    if not droplet:
        click.echo(f"Sandbox '{name}' not found.", err=True)
        sys.exit(1)

    droplet_id = droplet["id"]
    snapshot_name = f"thinky-{name}-{int(time.time())}"

    click.echo(f"Snapshotting '{name}'...")
    action_id = client.create_snapshot(droplet_id, snapshot_name)

    click.echo("Waiting for snapshot to complete (this may take a few minutes)...")
    success = client.wait_for_action(droplet_id, action_id, timeout=600)

    if not success:
        click.echo("Snapshot failed or timed out.", err=True)
        sys.exit(1)

    click.echo(f"Snapshot created: {snapshot_name}")
    click.echo(f"Destroying droplet to save cost...")
    client.delete_droplet(droplet_id)
    click.echo(f"Sandbox '{name}' hibernated. Wake with: thinky-remote wake {name}")


@cli.command()
@click.argument("name")
@click.option("--region", default=None, help="Region for restored droplet")
@click.option("--size", default=None, help="Size for restored droplet")
def wake(name: str, region: str | None, size: str | None):
    """Wake a hibernated sandbox from its snapshot."""
    config = load_config()
    client = get_client(config)

    # Check not already running
    existing = find_droplet_by_name(client, name)
    if existing:
        click.echo(f"Sandbox '{name}' is already running (ID: {existing['id']}).")
        sys.exit(1)

    # Find snapshot
    snapshot = find_snapshot_by_name(client, name)
    if not snapshot:
        click.echo(f"No snapshot found for '{name}'.", err=True)
        sys.exit(1)

    region = region or config["default_region"]
    size = size or config["default_size"]
    ssh_key_id = ensure_ssh_key(client, config)
    tag = f"{TAG_PREFIX}:{name}"

    click.echo(f"Waking '{name}' from snapshot {snapshot['name']}...")
    droplet = client.create_droplet_from_snapshot(
        name=f"thinky-{name}",
        region=region,
        size=size,
        snapshot_id=int(snapshot["id"]),
        ssh_key_ids=[ssh_key_id],
        tags=[TAG_PREFIX, tag],
    )

    droplet_id = droplet["id"]

    # Wait for IP
    ip = None
    for _ in range(30):
        ip = client.get_droplet_ip(droplet_id)
        if ip:
            break
        time.sleep(5)

    if ip:
        click.echo(f"\nSandbox '{name}' restored!")
        click.echo(f"  IP:  {ip}")
        click.echo(f"  SSH: ssh {config['username']}@{ip}")
    else:
        click.echo(f"\nDroplet created (ID: {droplet_id}) but IP not yet assigned.")

    # Clean up old snapshot
    click.echo(f"Cleaning up snapshot: {snapshot['name']}")
    client.delete_snapshot(int(snapshot["id"]))


@cli.command()
@click.argument("name")
@click.confirmation_option(prompt="Are you sure you want to destroy this sandbox?")
def destroy(name: str):
    """Destroy a sandbox VM and its snapshots."""
    config = load_config()
    client = get_client(config)

    # Delete running droplet
    droplet = find_droplet_by_name(client, name)
    if droplet:
        click.echo(f"Destroying droplet: {droplet['name']} (ID: {droplet['id']})")
        client.delete_droplet(droplet["id"])
    else:
        click.echo(f"No running sandbox '{name}' found.")

    # Delete associated snapshots
    snapshot = find_snapshot_by_name(client, name)
    if snapshot:
        click.echo(f"Deleting snapshot: {snapshot['name']}")
        client.delete_snapshot(int(snapshot["id"]))

    click.echo(f"Sandbox '{name}' destroyed.")


def fetch_github_keys(username: str) -> list[str]:
    """Fetch public SSH keys from a GitHub user profile."""
    url = f"https://github.com/{username}.keys"
    resp = requests.get(url, timeout=10)
    if resp.status_code == 404:
        raise click.ClickException(f"GitHub user '{username}' not found")
    resp.raise_for_status()
    keys = [line.strip() for line in resp.text.strip().splitlines() if line.strip()]
    if not keys:
        raise click.ClickException(f"GitHub user '{username}' has no public SSH keys")
    return keys


def get_droplet_ip(droplet: dict) -> str | None:
    """Extract public IPv4 from a droplet dict."""
    for net in droplet.get("networks", {}).get("v4", []):
        if net["type"] == "public":
            return net["ip_address"]
    return None


@cli.command()
@click.argument("name")
@click.argument("users")
def share(name: str, users: str):
    """Share a sandbox with GitHub users by adding their SSH keys.

    USERS is a comma-separated list of GitHub usernames.

    Example: thinky-remote share my-sandbox user1,user2,user3
    """
    config = load_config()
    client = get_client(config)

    droplet = find_droplet_by_name(client, name)
    if not droplet:
        click.echo(f"Sandbox '{name}' not found.", err=True)
        sys.exit(1)

    ip = get_droplet_ip(droplet)
    if not ip:
        click.echo(f"Sandbox '{name}' has no public IP.", err=True)
        sys.exit(1)

    usernames = [u.strip() for u in users.split(",") if u.strip()]
    if not usernames:
        click.echo("No usernames provided.", err=True)
        sys.exit(1)

    # Collect all keys
    all_keys = []
    for gh_user in usernames:
        click.echo(f"Fetching keys for GitHub user: {gh_user}")
        try:
            keys = fetch_github_keys(gh_user)
            click.echo(f"  Found {len(keys)} key(s)")
            all_keys.extend(keys)
        except click.ClickException as e:
            click.echo(f"  {e.message}", err=True)

    if not all_keys:
        click.echo("No keys to add.", err=True)
        sys.exit(1)

    # Build SSH command to append keys
    vm_user = config.get("username", "dev")
    ssh_key = Path(config["ssh_public_key"]).expanduser()
    identity = str(ssh_key).replace(".pub", "")

    # Append each key to authorized_keys on the VM
    key_block = "\n".join(all_keys)
    cmd = f"echo '{key_block}' >> /home/{vm_user}/.ssh/authorized_keys"

    click.echo(f"Adding {len(all_keys)} key(s) to {name}...")
    result = subprocess.run(
        [
            "ssh",
            "-o", "StrictHostKeyChecking=accept-new",
            "-i", identity,
            f"{vm_user}@{ip}",
            cmd,
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        click.echo(f"Failed to add keys: {result.stderr.strip()}", err=True)
        sys.exit(1)

    click.echo(f"\nShared '{name}' with: {', '.join(usernames)}")
    click.echo(f"They can connect with: ssh {vm_user}@{ip}")


def main():
    cli()


if __name__ == "__main__":
    main()
