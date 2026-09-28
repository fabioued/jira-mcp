"""
Unit and integration test suite for Jira MCP Server.
Tests JSON-RPC protocol compliance, ADF formatting, and Jira tool operations with mocks.
"""

import io
import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Ensure module can be imported directly
test_dir = os.path.dirname(os.path.abspath(__file__))
if test_dir not in sys.path:
    sys.path.insert(0, test_dir)

from config import JiraConfig
from jira_client import adf_to_text, text_to_adf
from tools import (
    TOOL_HANDLERS,
    get_tools_manifest,
    handle_complete_jira_ticket,
    handle_get_jira_ticket,
    handle_get_my_jira_tickets,
    handle_update_jira_ticket,
)
import server


class TestADFFormatting(unittest.TestCase):
    """Test Atlassian Document Format conversion to/from plain text."""

    def test_adf_to_text_paragraphs(self):
        adf = {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": "First line"}],
                },
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": "Second line"}],
                },
            ],
        }
        text = adf_to_text(adf)
        self.assertIn("First line", text)
        self.assertIn("Second line", text)

    def test_adf_to_text_bullet_list(self):
        adf = {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "bulletList",
                    "content": [
                        {
                            "type": "listItem",
                            "content": [
                                {
                                    "type": "paragraph",
                                    "content": [{"type": "text", "text": "Item A"}],
                                }
                            ],
                        },
                        {
                            "type": "listItem",
                            "content": [
                                {
                                    "type": "paragraph",
                                    "content": [{"type": "text", "text": "Item B"}],
                                }
                            ],
                        },
                    ],
                }
            ],
        }
        text = adf_to_text(adf)
        self.assertIn("• Item A", text)
        self.assertIn("• Item B", text)

    def test_text_to_adf(self):
        sample = "Line one\nLine two"
        adf = text_to_adf(sample)
        self.assertEqual(adf["type"], "doc")
        self.assertEqual(len(adf["content"]), 2)
        self.assertEqual(adf["content"][0]["content"][0]["text"], "Line one")
        self.assertEqual(adf["content"][1]["content"][0]["text"], "Line two")


class TestTools(unittest.TestCase):
    """Test tool handlers against mocked Jira client."""

    def test_tools_manifest(self):
        manifest = get_tools_manifest()
        tool_names = [t["name"] for t in manifest]
        self.assertIn("get_my_jira_tickets", tool_names)
        self.assertIn("get_jira_ticket", tool_names)
        self.assertIn("search_jira_tickets", tool_names)
        self.assertIn("update_jira_ticket", tool_names)
        self.assertIn("complete_jira_ticket", tool_names)
        self.assertIn("list_ticket_transitions", tool_names)
        self.assertIn("transition_jira_ticket", tool_names)
        self.assertIn("add_jira_comment", tool_names)

        # Verify all tools have registered handlers
        for name in tool_names:
            self.assertIn(name, TOOL_HANDLERS)

    @patch("tools.jira_client")
    def test_get_my_jira_tickets(self, mock_client):
        mock_client.get_my_tickets.return_value = [
            {
                "key": "TEST-101",
                "fields": {
                    "summary": "Fix login button styling",
                    "status": {"name": "In Progress"},
                    "priority": {"name": "High"},
                    "issuetype": {"name": "Bug"},
                    "assignee": {"displayName": "Test User"},
                },
            }
        ]
        res = handle_get_my_jira_tickets({"status": "open", "username": "testuser"})
        self.assertIn("TEST-101", res)
        self.assertIn("Fix login button styling", res)
        self.assertIn("In Progress", res)
        self.assertIn("High", res)

    @patch("tools.jira_client")
    def test_get_jira_ticket(self, mock_client):
        mock_client.get_issue.return_value = {
            "key": "TEST-200",
            "fields": {
                "summary": "Implement MCP Server",
                "status": {"name": "To Do"},
                "priority": {"name": "Highest"},
                "issuetype": {"name": "Story"},
                "assignee": {"displayName": "Test User"},
                "reporter": {"displayName": "admin"},
                "created": "2026-09-21T10:00:00.000+0000",
                "updated": "2026-09-21T11:00:00.000+0000",
                "labels": ["backend", "mcp"],
                "description": {
                    "type": "doc",
                    "version": 1,
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [{"type": "text", "text": "Build server for Jira."}],
                        }
                    ],
                },
            },
        }
        res = handle_get_jira_ticket({"issue_key": "TEST-200"})
        self.assertIn("TEST-200", res)
        self.assertIn("Implement MCP Server", res)
        self.assertIn("Build server for Jira.", res)
        self.assertIn("Highest", res)

    @patch("tools.jira_client")
    def test_complete_jira_ticket(self, mock_client):
        mock_client.complete_issue.return_value = {
            "key": "TEST-200",
            "transition_id": "31",
            "transition_name": "Done",
            "status": "Done",
            "success": True,
        }
        res = handle_complete_jira_ticket({
            "issue_key": "TEST-200",
            "comment": "Completed via Jira MCP",
        })
        self.assertIn("TEST-200", res)
        self.assertIn("Successfully marked", res)
        self.assertIn("Done", res)

    @patch("tools.jira_client")
    def test_update_jira_ticket(self, mock_client):
        mock_client.update_issue.return_value = {
            "key": "TEST-200",
            "updated": True,
            "comment_added": True,
        }
        res = handle_update_jira_ticket({
            "issue_key": "TEST-200",
            "summary": "New Title",
            "priority": "High",
        })
        self.assertIn("Successfully updated", res)
        self.assertIn("TEST-200", res)


class TestMCPProtocol(unittest.TestCase):
    """Test MCP JSON-RPC stdio protocol interactions."""

    def test_initialize(self):
        output = io.StringIO()
        with patch("sys.stdout", output):
            server.handle_initialize(1, {"clientInfo": {"name": "test-client", "version": "1.0"}})

        res_line = output.getvalue().strip()
        data = json.loads(res_line)
        self.assertEqual(data["jsonrpc"], "2.0")
        self.assertEqual(data["id"], 1)
        self.assertEqual(data["result"]["protocolVersion"], "2024-11-05")
        self.assertEqual(data["result"]["serverInfo"]["name"], "jira-mcp-server")

    def test_tools_list(self):
        output = io.StringIO()
        with patch("sys.stdout", output):
            server.handle_tools_list(2, {})

        res_line = output.getvalue().strip()
        data = json.loads(res_line)
        self.assertEqual(data["id"], 2)
        tools = data["result"]["tools"]
        self.assertTrue(len(tools) >= 5)

    @patch("tools.jira_client")
    def test_tools_call(self, mock_client):
        mock_client.get_my_tickets.return_value = []
        output = io.StringIO()
        with patch("sys.stdout", output):
            server.handle_tools_call(
                3,
                {"name": "get_my_jira_tickets", "arguments": {"username": "testuser"}},
            )

        res_line = output.getvalue().strip()
        data = json.loads(res_line)
        self.assertEqual(data["id"], 3)
        self.assertFalse(data["result"]["isError"])
        content_text = data["result"]["content"][0]["text"]
        self.assertIn("No Jira tickets found", content_text)


if __name__ == "__main__":
    unittest.main()
