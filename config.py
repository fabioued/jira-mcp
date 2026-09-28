"""
Jira MCP Server Configuration.
Loads settings from environment variables, .env file, or ~/.jira-mcp-config.json.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

SERVER_DIR = Path(__file__).resolve().parent
ENV_FILE = SERVER_DIR / ".env"
GLOBAL_CONFIG_FILE = Path.home() / ".jira-mcp-config.json"


def _load_env_file(file_path: Path) -> Dict[str, str]:
    """Parse a simple key=value .env file."""
    values: Dict[str, str] = {}
    if not file_path.is_file():
        return values
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip().strip("\"'")
                    values[key] = val
    except Exception:
        pass
    return values


def _load_json_config(file_path: Path) -> Dict[str, Any]:
    """Load JSON config if it exists."""
    if not file_path.is_file():
        return {}
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


class JiraConfig:
    """Manages Jira connection parameters."""

    def __init__(self) -> None:
        self.reload()

    def reload(self) -> None:
        env_vars = _load_env_file(ENV_FILE)
        global_vars = _load_json_config(GLOBAL_CONFIG_FILE)

        def get_val(key: str, default: str = "") -> str:
            # 1. OS environment variable
            if os.getenv(key):
                return os.getenv(key, "")
            # 2. .env file
            if key in env_vars:
                return env_vars[key]
            # 3. Global JSON config
            if key in global_vars:
                return str(global_vars[key])
            # Lowercase version in global json
            lower_key = key.lower()
            if lower_key in global_vars:
                return str(global_vars[lower_key])
            return default

        self.url = get_val("JIRA_URL", "").rstrip("/")
        self.email = get_val("JIRA_EMAIL", get_val("JIRA_USERNAME", ""))
        self.api_token = get_val("JIRA_API_TOKEN", "")
        self.default_user = get_val("JIRA_DEFAULT_USER", "")

    def is_configured(self) -> bool:
        return bool(self.url and self.api_token and self.email)

    def save(
        self,
        url: Optional[str] = None,
        email: Optional[str] = None,
        api_token: Optional[str] = None,
        default_user: Optional[str] = None,
    ) -> None:
        """Persist settings to .env and global config."""
        if url:
            self.url = url.rstrip("/")
        if email:
            self.email = email
        if api_token:
            self.api_token = api_token
        if default_user:
            self.default_user = default_user

        # Write to .env
        env_lines = [
            f"JIRA_URL={self.url}\n",
            f"JIRA_EMAIL={self.email}\n",
            f"JIRA_API_TOKEN={self.api_token}\n",
            f"JIRA_DEFAULT_USER={self.default_user}\n",
        ]
        with open(ENV_FILE, "w", encoding="utf-8") as f:
            f.writelines(env_lines)

        # Write to global config
        data = {
            "jira_url": self.url,
            "jira_email": self.email,
            "jira_api_token": self.api_token,
            "jira_default_user": self.default_user,
        }
        with open(GLOBAL_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)


config = JiraConfig()
