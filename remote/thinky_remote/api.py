"""DigitalOcean API client — minimal wrapper for sandbox VM lifecycle."""

import sys
import time

import requests

API_BASE = "https://api.digitalocean.com/v2"


class DOClient:
    """Minimal DigitalOcean API client."""

    def __init__(self, token: str):
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        })

    def _request(self, method: str, path: str, **kwargs) -> dict:
        resp = self.session.request(method, f"{API_BASE}{path}", **kwargs)
        if resp.status_code >= 400:
            print(f"API error {resp.status_code}: {resp.text}", file=sys.stderr)
            resp.raise_for_status()
        if resp.status_code == 204:
            return {}
        return resp.json()

    # --- SSH Keys ---

    def list_ssh_keys(self) -> list[dict]:
        """List all SSH keys on the account."""
        return self._request("GET", "/account/keys").get("ssh_keys", [])

    def upload_ssh_key(self, name: str, public_key: str) -> dict:
        """Upload an SSH public key."""
        data = {"name": name, "public_key": public_key}
        return self._request("POST", "/account/keys", json=data).get("ssh_key", {})

    # --- Droplets ---

    def create_droplet(
        self,
        name: str,
        region: str,
        size: str,
        image: str,
        ssh_key_ids: list[int],
        user_data: str,
        tags: list[str] | None = None,
    ) -> dict:
        """Create a new droplet."""
        data = {
            "name": name,
            "region": region,
            "size": size,
            "image": image,
            "ssh_keys": ssh_key_ids,
            "user_data": user_data,
            "tags": tags or [],
            "ipv6": False,
        }
        return self._request("POST", "/droplets", json=data).get("droplet", {})

    def get_droplet(self, droplet_id: int) -> dict:
        """Get droplet details."""
        return self._request("GET", f"/droplets/{droplet_id}").get("droplet", {})

    def list_droplets(self, tag: str | None = None) -> list[dict]:
        """List droplets, optionally filtered by tag."""
        params = {"tag_name": tag} if tag else {}
        return self._request("GET", "/droplets", params=params).get("droplets", [])

    def delete_droplet(self, droplet_id: int) -> None:
        """Delete a droplet."""
        self._request("DELETE", f"/droplets/{droplet_id}")

    def get_droplet_ip(self, droplet_id: int) -> str | None:
        """Get the public IPv4 address of a droplet."""
        droplet = self.get_droplet(droplet_id)
        for net in droplet.get("networks", {}).get("v4", []):
            if net["type"] == "public":
                return net["ip_address"]
        return None

    # --- Snapshots (for hibernate/wake) ---

    def create_snapshot(self, droplet_id: int, name: str) -> int:
        """Create a snapshot of a droplet. Returns the action ID."""
        data = {"type": "snapshot", "name": name}
        result = self._request("POST", f"/droplets/{droplet_id}/actions", json=data)
        return result.get("action", {}).get("id", 0)

    def get_action(self, droplet_id: int, action_id: int) -> dict:
        """Get action status."""
        return self._request(
            "GET", f"/droplets/{droplet_id}/actions/{action_id}"
        ).get("action", {})

    def wait_for_action(
        self, droplet_id: int, action_id: int, timeout: int = 600
    ) -> bool:
        """Wait for an action to complete."""
        start = time.time()
        while time.time() - start < timeout:
            action = self.get_action(droplet_id, action_id)
            status = action.get("status")
            if status == "completed":
                return True
            if status == "errored":
                return False
            time.sleep(5)
        return False

    def list_snapshots(self) -> list[dict]:
        """List all droplet snapshots."""
        return self._request("GET", "/snapshots?resource_type=droplet").get(
            "snapshots", []
        )

    def delete_snapshot(self, snapshot_id: int) -> None:
        """Delete a snapshot."""
        self._request("DELETE", f"/snapshots/{snapshot_id}")

    def create_droplet_from_snapshot(
        self,
        name: str,
        region: str,
        size: str,
        snapshot_id: int,
        ssh_key_ids: list[int],
        tags: list[str] | None = None,
    ) -> dict:
        """Create a droplet from a snapshot."""
        data = {
            "name": name,
            "region": region,
            "size": size,
            "image": snapshot_id,
            "ssh_keys": ssh_key_ids,
            "tags": tags or [],
        }
        return self._request("POST", "/droplets", json=data).get("droplet", {})
