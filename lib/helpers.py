"""Utility classes for liteflow step execution.

Provides:
- StepContext: dot-path context access and merging
- HTTPStep: zero-dependency HTTP client with auth injection
- RunLogger: structured logging to console and database
"""

import datetime
import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional


class StepContext:
    """Wraps a raw context dict with dot-path access and merging.

    Example::

        ctx = StepContext({"github": {"issues": [{"title": "Bug"}]}})
        ctx.get("github.issues.0.title")  # => "Bug"
        ctx.require("github.issues")       # passes
        ctx.require("slack.channel")       # raises KeyError
    """

    def __init__(self, raw: Optional[Dict[str, Any]] = None) -> None:
        self.data: Dict[str, Any] = raw if raw is not None else {}

    def get(self, dotpath: str, default: Any = None) -> Any:
        """Access a nested value using dot-path notation.

        Supports dict keys and integer list indices.

        Args:
            dotpath: Dot-separated path (e.g. 'github.issues.0.title').
            default: Value to return if path is not found.

        Returns:
            The value at the path, or default.
        """
        current: Any = self.data
        for part in dotpath.split("."):
            if isinstance(current, dict):
                current = current.get(part)
                if current is None:
                    return default
            elif isinstance(current, (list, tuple)):
                try:
                    current = current[int(part)]
                except (ValueError, IndexError):
                    return default
            else:
                return default
        return current

    def require(self, *keys: str) -> None:
        """Raise a descriptive error if any keys are missing from context.

        Args:
            *keys: Dot-paths that must resolve to non-None values.

        Raises:
            KeyError: With a message listing all missing keys.
        """
        missing = [k for k in keys if self.get(k) is None]
        if missing:
            raise KeyError(
                f"Required context keys missing: {', '.join(missing)}. "
                f"Available top-level keys: {', '.join(sorted(self.data.keys()))}"
            )

    def merge(self, step_id: str, output: Dict[str, Any]) -> None:
        """Merge step output into context, namespaced by step_id.

        Args:
            step_id: The step identifier to namespace under.
            output: The step's output dict.
        """
        self.data[step_id] = output

    def to_dict(self) -> Dict[str, Any]:
        """Return the underlying context data as a plain dict."""
        return dict(self.data)

    def __repr__(self) -> str:
        keys = list(self.data.keys())
        return f"StepContext(keys={keys})"


class HTTPStep:
    """Minimal HTTP client built on urllib with zero extra dependencies.

    Supports automatic auth header injection when paired with a SecureStore.
    """

    def __init__(self, auth_store: Any = None) -> None:
        """Initialize the HTTP client.

        Args:
            auth_store: Optional SecureStore instance for auto-auth.
        """
        self.auth = auth_store

    def get(
        self,
        url_or_service: str,
        endpoint: str = "",
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Perform an HTTP GET request.

        Args:
            url_or_service: Full URL or service name (resolved via auth store).
            endpoint: API endpoint path to append.
            headers: Optional request headers.
            params: Optional query parameters.

        Returns:
            Parsed JSON response as a dict.
        """
        url = self._resolve_url(url_or_service, endpoint)
        if params:
            url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
        headers = headers or {}
        self._inject_auth(url_or_service, headers)
        return self._request("GET", url, headers)

    def post(
        self,
        url_or_service: str,
        data: Any = None,
        endpoint: str = "",
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Perform an HTTP POST request.

        Args:
            url_or_service: Full URL or service name.
            data: Request body (will be JSON-encoded).
            endpoint: API endpoint path to append.
            headers: Optional request headers.

        Returns:
            Parsed JSON response as a dict.
        """
        url = self._resolve_url(url_or_service, endpoint)
        headers = headers or {}
        self._inject_auth(url_or_service, headers)
        return self._request("POST", url, headers, data)

    def put(
        self,
        url_or_service: str,
        data: Any = None,
        endpoint: str = "",
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Perform an HTTP PUT request.

        Args:
            url_or_service: Full URL or service name.
            data: Request body (will be JSON-encoded).
            endpoint: API endpoint path to append.
            headers: Optional request headers.

        Returns:
            Parsed JSON response as a dict.
        """
        url = self._resolve_url(url_or_service, endpoint)
        headers = headers or {}
        self._inject_auth(url_or_service, headers)
        return self._request("PUT", url, headers, data)

    def delete(
        self,
        url_or_service: str,
        endpoint: str = "",
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Perform an HTTP DELETE request.

        Args:
            url_or_service: Full URL or service name.
            endpoint: API endpoint path to append.
            headers: Optional request headers.

        Returns:
            Parsed JSON response as a dict.
        """
        url = self._resolve_url(url_or_service, endpoint)
        headers = headers or {}
        self._inject_auth(url_or_service, headers)
        return self._request("DELETE", url, headers)

    def _resolve_url(self, url_or_service: str, endpoint: str) -> str:
        """Resolve a URL or service name to a full URL.

        If url_or_service starts with http, treat as a URL.
        Otherwise, look up the base URL in the auth store.
        """
        if url_or_service.startswith(("http://", "https://")):
            base = url_or_service.rstrip("/")
        elif self.auth is not None:
            cred = self.auth.get_credential(url_or_service)
            if cred and cred.get("base_url"):
                base = cred["base_url"].rstrip("/")
            else:
                # Try known service URLs
                from .creds import SERVICE_URLS

                base_url = SERVICE_URLS.get(url_or_service)
                if base_url:
                    base = base_url.rstrip("/")
                else:
                    raise ValueError(
                        f"Cannot resolve URL for service '{url_or_service}'. "
                        "Provide a full URL or store credentials with a base_url."
                    )
        else:
            from .creds import SERVICE_URLS

            base_url = SERVICE_URLS.get(url_or_service)
            if base_url:
                base = base_url.rstrip("/")
            else:
                raise ValueError(
                    f"Cannot resolve URL for '{url_or_service}'. "
                    "Provide a full URL or configure an auth store."
                )

        if endpoint:
            return base + "/" + endpoint.lstrip("/")
        return base

    def _inject_auth(self, service: str, headers: Dict[str, str]) -> None:
        """Auto-inject authorization headers for known services."""
        if self.auth is None:
            return
        if service.startswith(("http://", "https://")):
            return
        if "Authorization" in headers or "authorization" in headers:
            return

        token = self.auth.get_token(service)
        if token is None:
            return

        # Service-specific auth header formats
        if service == "github":
            headers["Authorization"] = f"token {token}"
            headers.setdefault("Accept", "application/vnd.github.v3+json")
        elif service == "anthropic":
            headers["x-api-key"] = token
            headers.setdefault("anthropic-version", "2023-06-01")
        elif service == "slack":
            headers["Authorization"] = f"Bearer {token}"
        else:
            headers["Authorization"] = f"Bearer {token}"

    def _request(
        self,
        method: str,
        url: str,
        headers: Dict[str, str],
        data: Any = None,
    ) -> Dict[str, Any]:
        """Execute an HTTP request and return parsed JSON.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE).
            url: Full request URL.
            headers: Request headers.
            data: Optional request body.

        Returns:
            Parsed JSON response, or dict with raw text on parse failure.

        Raises:
            urllib.error.HTTPError: On HTTP error responses.
        """
        body = None
        if data is not None:
            headers.setdefault("Content-Type", "application/json")
            body = json.dumps(data).encode("utf-8")

        req = urllib.request.Request(url, data=body, headers=headers, method=method)

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode("utf-8")
                if not raw.strip():
                    return {"status": resp.status, "ok": True}
                try:
                    return json.loads(raw)
                except json.JSONDecodeError:
                    return {"status": resp.status, "body": raw}
        except urllib.error.HTTPError as e:
            error_body = ""
            try:
                error_body = e.read().decode("utf-8")
            except Exception:
                pass
            raise type(e)(
                e.url,
                e.code,
                f"{e.reason}: {error_body}",
                e.headers,
                None,
            ) from None


class RunLogger:
    """Structured logging to console and execution database.

    Logs are printed to stderr and optionally stored alongside step
    execution records in the state database.
    """

    def __init__(
        self,
        run_id: str,
        step_id: str,
        db_path: Optional[str] = None,
    ) -> None:
        """Initialize the logger.

        Args:
            run_id: The current run identifier.
            step_id: The current step identifier.
            db_path: Optional path to execution database for persistent logs.
        """
        self.run_id = run_id
        self.step_id = step_id
        self.db_path = db_path
        self._logs: List[Dict[str, Any]] = []

    def _log(self, level: str, message: str, data: Any = None) -> None:
        """Internal logging method."""
        import sys

        ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
        entry = {
            "timestamp": ts,
            "level": level,
            "run_id": self.run_id,
            "step_id": self.step_id,
            "message": message,
        }
        if data is not None:
            entry["data"] = data

        self._logs.append(entry)

        # Print to stderr
        prefix = f"[{level.upper():5s}] [{self.step_id}]"
        print(f"{prefix} {message}", file=sys.stderr)
        if data is not None:
            print(f"{prefix}   {json.dumps(data, default=str)}", file=sys.stderr)

    def info(self, message: str, data: Any = None) -> None:
        """Log an informational message.

        Args:
            message: Log message.
            data: Optional structured data.
        """
        self._log("info", message, data)

    def warn(self, message: str, data: Any = None) -> None:
        """Log a warning message.

        Args:
            message: Log message.
            data: Optional structured data.
        """
        self._log("warn", message, data)

    def error(self, message: str, data: Any = None) -> None:
        """Log an error message.

        Args:
            message: Log message.
            data: Optional structured data.
        """
        self._log("error", message, data)

    def get_logs(self) -> List[Dict[str, Any]]:
        """Return all accumulated log entries."""
        return list(self._logs)
