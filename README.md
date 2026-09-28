# Jira Model Context Protocol (MCP) Server

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![MCP Standard](https://img.shields.io/badge/MCP-2024--11--05-green.svg)](https://modelcontextprotocol.io/)

A zero-dependency **Model Context Protocol (MCP)** server providing rich two-way integration with **Jira Cloud** and **Jira Data Center / Server**.

Designed for **Google Antigravity**, **Cursor**, **Claude Desktop**, **Windsurf**, and any MCP-compatible AI assistant or agent.

---

## 🚀 Features

- **🔍 Retrieve My Tickets (`get_my_jira_tickets`)**: Automatically queries Jira for assigned, reported, or mentioned tickets with status filters (`open`, `in_progress`, `completed`, `all`) and project filters.
- **📄 Inspect Issue Details (`get_jira_ticket`)**: View summary, status, priority, issue type, assignee, reporter, subtasks, attachments, comments, and description (with ADF to Markdown conversion).
- **✅ Complete Tickets (`complete_jira_ticket`)**: Smart transition resolver that discovers the workflow's target "Done" / "Resolved" transition and executes it with optional resolution notes.
- **✏️ Edit Issue Fields (`update_jira_ticket`)**: Update issue summaries, descriptions, priority, labels, or assignee.
- **🔄 Workflow Transitions (`list_ticket_transitions` & `transition_jira_ticket`)**: Inspect all available transitions for an issue and move it through any custom workflow state.
- **💬 Add Comments (`add_jira_comment`)**: Post internal notes or user-facing comments directly to issues.
- **🔎 JQL Search (`search_jira_tickets`)**: Run custom, complex Jira Query Language (JQL) expressions with custom field selection and pagination.
- **👤 User Profile & Diagnostics (`get_jira_user_info`)**: Inspect the currently authenticated Jira account and permissions.
- **⚡ Zero External Dependencies**: Built entirely using Python's standard library (`urllib`, `json`, `ssl`).

---

## 🛠️ Available MCP Tools

| Tool | Description | Key Parameters |
| :--- | :--- | :--- |
| `get_my_jira_tickets` | Retrieve tickets for the authenticated user or specified username | `status`, `project`, `max_results`, `username` |
| `get_jira_ticket` | Get full details, markdown description, and comments for an issue | `issue_key` |
| `update_jira_ticket` | Update summary, description, priority, labels, or assignee | `issue_key`, `summary`, `description`, `priority`, `labels`, `assignee` |
| `complete_jira_ticket` | Automatically transition an issue to Done/Completed | `issue_key`, `comment`, `resolution` |
| `list_ticket_transitions` | List all available valid workflow transitions for an issue | `issue_key` |
| `transition_jira_ticket` | Transition an issue to a specific workflow status ID or name | `issue_key`, `transition_id`, `comment` |
| `add_jira_comment` | Add a comment to a Jira issue | `issue_key`, `comment` |
| `search_jira_tickets` | Execute arbitrary JQL queries | `jql`, `max_results`, `fields` |
| `get_jira_user_info` | Get details about the currently authenticated user | *(none)* |

---

## ⚙️ Quickstart & Installation

### Prerequisites
- Python 3.8 or higher.
- A Jira Cloud or Jira Data Center / Server instance.
- An Atlassian API Token (for Jira Cloud).

### 1. Clone the Repository

```bash
git clone https://github.com/your-username/jira-mcp-server.git
cd jira-mcp-server
```

### 2. Configure Credentials

Create a `.env` file from the provided example:

```bash
cp .env.example .env
```

Edit `.env` with your Jira credentials:

```ini
JIRA_URL=https://your-domain.atlassian.net
JIRA_EMAIL=your-email@example.com
JIRA_API_TOKEN=your_api_token_here
JIRA_DEFAULT_USER=
```

> **How to generate an Atlassian API Token**:
> 1. Log in to [https://id.atlassian.com/manage-profile/security/api-tokens](https://id.atlassian.com/manage-profile/security/api-tokens).
> 2. Click **Create API token**.
> 3. Give it a label (e.g., `jira-mcp`) and copy the generated token.

### 3. Test Connection

Verify your configuration and test authentication:

```bash
python3 setup_config.py --test
```

Or configure directly via CLI flags:

```bash
python3 setup_config.py --url https://your-domain.atlassian.net --email your-email@example.com --token YOUR_API_TOKEN --test
```

---

## 🔌 Connecting to AI Clients

### 1. Google Antigravity / Gemini CLI (`mcp_config.json`)

Add to `~/.gemini/config/mcp_config.json` (or `mcp_servers` block):

```json
{
  "mcpServers": {
    "jira": {
      "command": "python3",
      "args": ["/path/to/jira-mcp-server/server.py"],
      "env": {
        "JIRA_URL": "https://your-domain.atlassian.net",
        "JIRA_EMAIL": "your-email@example.com",
        "JIRA_API_TOKEN": "your_api_token_here"
      }
    }
  }
}
```

### 2. Claude Desktop (`claude_desktop_config.json`)

Add to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "jira": {
      "command": "python3",
      "args": ["/path/to/jira-mcp-server/server.py"],
      "env": {
        "JIRA_URL": "https://your-domain.atlassian.net",
        "JIRA_EMAIL": "your-email@example.com",
        "JIRA_API_TOKEN": "your_api_token_here"
      }
    }
  }
}
```

### 3. Cursor (`.cursor/mcp.json`)

```json
{
  "mcpServers": {
    "jira": {
      "command": "python3",
      "args": ["/path/to/jira-mcp-server/server.py"],
      "env": {
        "JIRA_URL": "https://your-domain.atlassian.net",
        "JIRA_EMAIL": "your-email@example.com",
        "JIRA_API_TOKEN": "your_api_token_here"
      }
    }
  }
}
```

---

## 🧪 Testing

Run the included unit test suite:

```bash
python3 test_server.py
```

---

## 🔒 Security & Privacy

- **No telemetry or data logging**: All communication occurs directly between your local machine and your Jira instance via standard HTTPS.
- **Credential Storage**: Credentials can be passed via environment variables, a local `.env` file, or standard MCP client configuration. The `.env` file is ignored by git by default.

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
