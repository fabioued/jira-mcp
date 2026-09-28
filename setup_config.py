#!/usr/bin/env python3
"""
Setup and verification script for Jira MCP Server.
Tests Jira connectivity and updates local and global configuration.
"""

import argparse
import os
import sys

# Ensure package imports work
server_dir = os.path.dirname(os.path.abspath(__file__))
if server_dir not in sys.path:
    sys.path.insert(0, server_dir)

from config import config
from jira_client import jira_client


def test_connection() -> bool:
    """Attempts to authenticate with Jira and display user information."""
    print(f"Connecting to Jira at {config.url} ...")
    try:
        user_info = jira_client.get_current_user()
        display_name = user_info.get("displayName", "N/A")
        email = user_info.get("emailAddress", config.email or "N/A")
        account_id = user_info.get("accountId", user_info.get("name", "N/A"))

        print("\n🎉 Authentication Successful!")
        print(f"  • Name:        {display_name}")
        print(f"  • Email:       {email}")
        print(f"  • Account ID:  {account_id}")
        print(f"  • Jira URL:    {config.url}")
        return True
    except PermissionError as pe:
        print(f"\n❌ Authentication Failed: {pe}")
        print("\nTroubleshooting tips:")
        print("  1. Double check that your JIRA_EMAIL matches the email on your Atlassian account.")
        print("  2. Ensure your API token was created at https://id.atlassian.com/manage-profile/security/api-tokens")
        print("  3. Ensure you have access permissions on the Jira instance.")
        return False
    except Exception as e:
        print(f"\n❌ Connection Error: {e}")
        return False


def main() -> None:
    parser.add_argument("--url", help="Jira base URL (e.g. https://your-domain.atlassian.net)")
    parser.add_argument("--email", help="Atlassian account login email")
    parser.add_argument("--token", help="Atlassian API token")
    parser.add_argument("--user", help="Default Jira username / assignee to query")
    parser.add_argument("--test", action="store_true", help="Test current configuration against Jira API")

    args = parser.parse_args()

    updated = False
    if args.url:
        config.url = args.url.rstrip("/")
        updated = True
    if args.email:
        config.email = args.email.strip()
        updated = True
    if args.token:
        config.api_token = args.token.strip()
        updated = True
    if args.user:
        config.default_user = args.user.strip()
        updated = True

    if updated:
        config.save(
            url=config.url,
            email=config.email,
            api_token=config.api_token,
            default_user=config.default_user,
        )
        print(f"✅ Configuration updated in {server_dir}/.env and ~/.jira-mcp-config.json")

    # If no parameters provided or --test passed, run test
    if args.test or not any([args.url, args.email, args.token, args.user]):
        if not config.email:
            print("⚠️ JIRA_EMAIL is not yet configured.")
            print("To configure, run:")
            print("  python3 setup_config.py --email your.email@example.com")
            return
        test_connection()


if __name__ == "__main__":
    main()
