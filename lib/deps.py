"""Lazy dependency installer for liteflow.

Ensures required SQLite libraries and optional SDKs are available,
installing them silently on first use.
"""

import importlib
import subprocess
import sys
from typing import Dict

# Core dependencies required by liteflow
CORE_DEPS = [
    "simple-graph-sqlite",
    "litequeue",
    "sqlite-utils",
    "sqlitedict",
]

# Optional SDKs mapped by service name
OPTIONAL_SDKS: Dict[str, str] = {
    "github": "PyGithub",
    "slack": "slack_sdk",
    "jira": "jira",
    "notion": "notion-client",
    "linear": "linear-python",
    "sendgrid": "sendgrid",
    "twilio": "twilio",
    "gcp": "google-cloud-core",
    "openai": "openai",
    "anthropic": "anthropic",
}


def ensure_deps(*packages: str) -> None:
    """Install missing packages silently on first use."""
    for pkg in packages:
        module_name = pkg.replace("-", "_")
        try:
            importlib.import_module(module_name)
        except ImportError:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", pkg, "-q"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            importlib.import_module(module_name)


def ensure_sdk(service: str) -> None:
    """Install the optional SDK for a given service name.

    Args:
        service: Service key (e.g. 'github', 'slack').

    Raises:
        ValueError: If the service name is not recognized.
    """
    pkg = OPTIONAL_SDKS.get(service)
    if pkg is None:
        raise ValueError(
            f"Unknown service '{service}'. "
            f"Available: {', '.join(sorted(OPTIONAL_SDKS))}"
        )
    ensure_deps(pkg)


def check_deps() -> Dict[str, Dict[str, bool]]:
    """Return installed/missing status for all known dependencies.

    Returns:
        Dict with 'core' and 'optional' keys, each mapping package names
        to booleans indicating whether they are importable.
    """
    result: Dict[str, Dict[str, bool]] = {"core": {}, "optional": {}}

    for pkg in CORE_DEPS:
        module_name = pkg.replace("-", "_")
        try:
            importlib.import_module(module_name)
            result["core"][pkg] = True
        except ImportError:
            result["core"][pkg] = False

    for service, pkg in OPTIONAL_SDKS.items():
        module_name = pkg.replace("-", "_")
        try:
            importlib.import_module(module_name)
            result["optional"][service] = True
        except ImportError:
            result["optional"][service] = False

    return result
