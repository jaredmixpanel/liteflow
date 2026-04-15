"""Credential management with sqlitedict and basic encryption.

Provides a SecureStore class that persists API tokens and credentials
in a SQLite-backed key-value store with optional Fernet encryption
or base64 obfuscation fallback.
"""

import base64
import datetime
import hashlib
import json
import platform
import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional

from .deps import ensure_deps

# Service base URLs for known integrations
SERVICE_URLS: Dict[str, str] = {
    "github": "https://api.github.com",
    "slack": "https://slack.com/api",
    "jira": "https://your-domain.atlassian.net/rest/api/3",
    "notion": "https://api.notion.com/v1",
    "linear": "https://api.linear.app/graphql",
    "sendgrid": "https://api.sendgrid.com/v3",
    "openai": "https://api.openai.com/v1",
    "anthropic": "https://api.anthropic.com/v1",
}


def _derive_key() -> bytes:
    """Derive an encryption key from machine identity."""
    machine_id = platform.node().encode()
    return hashlib.sha256(machine_id).digest()


def _get_fernet():
    """Try to create a Fernet cipher; return None if cryptography is unavailable."""
    try:
        from cryptography.fernet import Fernet

        raw_key = _derive_key()
        # Fernet requires a 32-byte url-safe base64 key
        fernet_key = base64.urlsafe_b64encode(raw_key)
        return Fernet(fernet_key)
    except ImportError:
        return None


class SecureStore:
    """Encrypted credential storage backed by sqlitedict.

    Uses Fernet symmetric encryption when the ``cryptography`` package is
    available; falls back to base64 obfuscation with a warning otherwise.
    """

    def __init__(self, db_path: str = "~/.liteflow/credentials.db") -> None:
        ensure_deps("sqlitedict")

        self._db_path = str(Path(db_path).expanduser())
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)

        self._fernet = _get_fernet()
        if self._fernet is None:
            warnings.warn(
                "cryptography package not installed. "
                "Credentials will use base64 obfuscation only. "
                "Install cryptography for proper encryption: "
                "pip install cryptography",
                stacklevel=2,
            )

    def _encrypt(self, plaintext: str) -> str:
        """Encrypt a string value."""
        if self._fernet is not None:
            return self._fernet.encrypt(plaintext.encode()).decode()
        # Fallback: base64 with derived key XOR (basic obfuscation)
        key = _derive_key()
        data = plaintext.encode()
        xored = bytes(b ^ key[i % len(key)] for i, b in enumerate(data))
        return base64.b64encode(xored).decode()

    def _decrypt(self, ciphertext: str) -> str:
        """Decrypt a string value."""
        if self._fernet is not None:
            return self._fernet.decrypt(ciphertext.encode()).decode()
        # Fallback: reverse the base64 + XOR obfuscation
        key = _derive_key()
        xored = base64.b64decode(ciphertext.encode())
        data = bytes(b ^ key[i % len(key)] for i, b in enumerate(xored))
        return data.decode()

    def _open(self) -> "sqlitedict.SqliteDict":
        """Open the sqlitedict store."""
        from sqlitedict import SqliteDict

        return SqliteDict(self._db_path, autocommit=True)

    def set_token(
        self,
        service: str,
        token: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Store an API token for a service.

        Args:
            service: Service name (e.g. 'github', 'slack').
            token: The API token or key.
            metadata: Optional metadata (scopes, description, etc.).
        """
        cred = {
            "type": "token",
            "token": self._encrypt(token),
            "base_url": SERVICE_URLS.get(service),
            "scopes": (metadata or {}).get("scopes", []),
            "added_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "metadata": metadata or {},
        }
        with self._open() as store:
            store[service] = json.dumps(cred)

    def get_token(self, service: str) -> Optional[str]:
        """Retrieve a decrypted API token for a service.

        Args:
            service: Service name.

        Returns:
            The decrypted token string, or None if not found.
        """
        with self._open() as store:
            raw = store.get(service)
            if raw is None:
                return None
            cred = json.loads(raw)
            return self._decrypt(cred["token"])

    def set_credential(self, service: str, cred: Dict[str, Any]) -> None:
        """Store a full credential bundle for a service.

        The 'token' field (if present) is encrypted before storage.

        Args:
            service: Service name.
            cred: Credential dict with type, token, url, scopes, etc.
        """
        stored = dict(cred)
        if "token" in stored:
            stored["token"] = self._encrypt(stored["token"])
        stored.setdefault(
            "added_at",
            datetime.datetime.now(datetime.timezone.utc).isoformat(),
        )
        with self._open() as store:
            store[service] = json.dumps(stored)

    def get_credential(self, service: str) -> Optional[Dict[str, Any]]:
        """Retrieve a full credential bundle with decrypted token.

        Args:
            service: Service name.

        Returns:
            Credential dict with decrypted token, or None if not found.
        """
        with self._open() as store:
            raw = store.get(service)
            if raw is None:
                return None
            cred = json.loads(raw)
            if "token" in cred:
                cred["token"] = self._decrypt(cred["token"])
            return cred

    def list_services(self) -> List[str]:
        """List all stored service names.

        Returns:
            Sorted list of service name strings.
        """
        with self._open() as store:
            return sorted(store.keys())

    def remove(self, service: str) -> None:
        """Remove credentials for a service.

        Args:
            service: Service name to remove.
        """
        with self._open() as store:
            if service in store:
                del store[service]

    def test_credential(self, service: str) -> Dict[str, Any]:
        """Test whether a stored credential is valid.

        Performs a basic connectivity check for known services.

        Args:
            service: Service name.

        Returns:
            Dict with 'valid' (bool) and 'message' (str) keys.
        """
        token = self.get_token(service)
        if token is None:
            return {"valid": False, "message": f"No credentials stored for '{service}'"}

        cred = self.get_credential(service)
        base_url = (cred or {}).get("base_url") or SERVICE_URLS.get(service)

        if base_url is None:
            return {
                "valid": True,
                "message": f"Token exists for '{service}' but no known API URL to test against",
            }

        # Attempt a lightweight API call
        import urllib.request
        import urllib.error

        test_endpoints: Dict[str, str] = {
            "github": "/user",
            "slack": "/auth.test",
            "openai": "/models",
            "anthropic": "/models",
        }
        endpoint = test_endpoints.get(service, "")
        url = base_url.rstrip("/") + endpoint

        headers = {"Authorization": f"Bearer {token}"}
        if service == "github":
            headers["Authorization"] = f"token {token}"
            headers["Accept"] = "application/vnd.github.v3+json"
        elif service == "anthropic":
            headers = {
                "x-api-key": token,
                "anthropic-version": "2023-06-01",
            }

        try:
            req = urllib.request.Request(url, headers=headers, method="GET")
            urllib.request.urlopen(req, timeout=10)
            return {"valid": True, "message": f"Successfully authenticated with {service}"}
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                return {"valid": False, "message": f"Authentication failed ({e.code}): {e.reason}"}
            # Other HTTP errors might still mean auth is fine
            return {"valid": True, "message": f"Authenticated, but got HTTP {e.code}: {e.reason}"}
        except Exception as e:
            return {"valid": False, "message": f"Connection error: {e}"}
