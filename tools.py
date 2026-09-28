"""
MCP Tool definitions and handlers for Jira.
"""

from typing import Any, Callable, Dict, List, Optional, Union

try:
    from .config import config
    from .jira_client import adf_to_text, jira_client
except ImportError:
    from config import config
    from jira_client import adf_to_text, jira_client


def format_issue_row(issue: Dict[str, Any]) -> str:
    """Formats a single issue into a markdown list item with key details."""
    key = issue.get("key", "")
    fields = issue.get("fields") or {}
    summary = fields.get("summary") or "No summary"
    status_obj = fields.get("status") or {}
    status = status_obj.get("name") or "Unknown"
    priority_obj = fields.get("priority") or {}
    priority = priority_obj.get("name") or "None"
    issue_type_obj = fields.get("issuetype") or {}
    issue_type = issue_type_obj.get("name") or "Task"
    assignee_obj = fields.get("assignee") or {}
    assignee = assignee_obj.get("displayName") or "Unassigned"
    base_url = config.url.rstrip("/")
    url = f"{base_url}/browse/{key}"

    return f"- **[{key}]({url})**: {summary}\n  - **Status**: `{status}` | **Priority**: {priority} | **Type**: {issue_type} | **Assignee**: {assignee}"


def handle_get_my_jira_tickets(args: Dict[str, Any]) -> str:
    status = args.get("status", "open")
    project = args.get("project")
    max_results = int(args.get("max_results", 25))
    username = args.get("username", config.default_user or "")
    user_display = username if username and username != "currentUser()" else "Current User"

    issues = jira_client.get_my_tickets(
        username=username if username else None,
        status_filter=status,
        project=project,
        max_results=max_results,
    )

    if not issues:
        return f"No Jira tickets found for **{user_display}** with filter `{status}`."

    lines = [
        f"### Jira Tickets for {user_display} (Filter: `{status}`, Found: {len(issues)})\n"
    ]
    for issue in issues:
        lines.append(format_issue_row(issue))

    return "\n".join(lines)


def handle_get_jira_ticket(args: Dict[str, Any]) -> str:
    issue_key = args.get("issue_key", "").strip().upper()
    if not issue_key:
        return "Error: `issue_key` is required (e.g. 'PROJ-123')."

    issue = jira_client.get_issue(issue_key)
    fields = issue.get("fields") or {}
    summary = fields.get("summary") or ""
    status_obj = fields.get("status") or {}
    status = status_obj.get("name") or "Unknown"
    priority_obj = fields.get("priority") or {}
    priority = priority_obj.get("name") or "None"
    issue_type_obj = fields.get("issuetype") or {}
    issue_type = issue_type_obj.get("name") or "Task"
    assignee_obj = fields.get("assignee") or {}
    assignee_name = assignee_obj.get("displayName") or "Unassigned"
    reporter_obj = fields.get("reporter") or {}
    reporter_name = reporter_obj.get("displayName") or "Unknown"
    created = fields.get("created") or ""
    updated = fields.get("updated") or ""
    labels = fields.get("labels") or []

    raw_desc = fields.get("description")
    description_text = adf_to_text(raw_desc) if raw_desc else "*(No description provided)*"

    base_url = config.url.rstrip("/")
    url = f"{base_url}/browse/{issue_key}"

    lines = [
        f"# [{issue_key}]({url}): {summary}",
        "",
        f"- **Status**: `{status}`",
        f"- **Type**: {issue_type}",
        f"- **Priority**: {priority}",
        f"- **Assignee**: {assignee_name}",
        f"- **Reporter**: {reporter_name}",
        f"- **Labels**: {', '.join(labels) if labels else 'None'}",
        f"- **Created**: {created} | **Updated**: {updated}",
        "",
        "## Description",
        description_text.strip(),
    ]

    # Recent comments if present
    comment_data = fields.get("comment") or {}
    comments = comment_data.get("comments") or []
    if comments:
        lines.append("\n## Recent Comments")
        for c in comments[-5:]:
            author = c.get("author", {}).get("displayName", "User")
            c_body = adf_to_text(c.get("body"))
            c_created = c.get("created", "")
            lines.append(f"**{author}** ({c_created}):\n{c_body.strip()}\n")

    return "\n".join(lines)


def handle_search_jira_tickets(args: Dict[str, Any]) -> str:
    jql = args.get("jql", "").strip()
    if not jql:
        return "Error: `jql` query string is required."

    max_results = int(args.get("max_results", 25))
    issues = jira_client.search_issues(jql, max_results=max_results)

    if not issues:
        return f"No Jira tickets matched JQL: `{jql}`"

    lines = [f"### JQL Search Results (`{jql}` - {len(issues)} results)\n"]
    for issue in issues:
        lines.append(format_issue_row(issue))

    return "\n".join(lines)


def handle_update_jira_ticket(args: Dict[str, Any]) -> str:
    issue_key = args.get("issue_key", "").strip().upper()
    if not issue_key:
        return "Error: `issue_key` is required."

    summary = args.get("summary")
    description = args.get("description")
    priority = args.get("priority")
    labels = args.get("labels")
    assignee = args.get("assignee")
    comment = args.get("comment")

    res = jira_client.update_issue(
        issue_key=issue_key,
        summary=summary,
        description=description,
        priority=priority,
        labels=labels,
        assignee=assignee,
        comment=comment,
    )

    base_url = config.url.rstrip("/")
    url = f"{base_url}/browse/{issue_key}"
    changes = []
    if summary is not None:
        changes.append(f"Summary updated to: '{summary}'")
    if description is not None:
        changes.append("Description updated")
    if priority is not None:
        changes.append(f"Priority set to '{priority}'")
    if labels is not None:
        changes.append(f"Labels updated: {labels}")
    if assignee is not None:
        changes.append(f"Assignee set to: {assignee or 'Unassigned'}")
    if comment is not None:
        changes.append("Comment added")

    change_list = "\n".join([f"- {c}" for c in changes]) if changes else "- No fields were modified"
    return f"✅ Successfully updated **[{issue_key}]({url})**:\n{change_list}"


def handle_complete_jira_ticket(args: Dict[str, Any]) -> str:
    issue_key = args.get("issue_key", "").strip().upper()
    if not issue_key:
        return "Error: `issue_key` is required."

    comment = args.get("comment")
    transition_name = args.get("transition_name")

    res = jira_client.complete_issue(
        issue_key=issue_key,
        comment=comment,
        transition_name=transition_name,
    )

    base_url = config.url.rstrip("/")
    url = f"{base_url}/browse/{issue_key}"

    if not res.get("success"):
        return f"⚠️ Could not mark **[{issue_key}]({url})** as completed:\n{res.get('message')}"

    return (
        f"🎉 Successfully marked **[{issue_key}]({url})** as completed!\n"
        f"- **New Status**: `{res.get('status')}`\n"
        f"- **Transition Applied**: '{res.get('transition_name')}' (ID: {res.get('transition_id')})\n"
        + (f"- **Comment Added**: {comment}\n" if comment else "")
    )


def handle_list_ticket_transitions(args: Dict[str, Any]) -> str:
    issue_key = args.get("issue_key", "").strip().upper()
    if not issue_key:
        return "Error: `issue_key` is required."

    transitions = jira_client.get_transitions(issue_key)
    base_url = config.url.rstrip("/")
    url = f"{base_url}/browse/{issue_key}"

    if not transitions:
        return f"No transitions available for **[{issue_key}]({url})**. The ticket may already be in a closed/resolved state or locked by workflow permissions."

    lines = [f"### Available Transitions for [{issue_key}]({url}):\n"]
    for t in transitions:
        t_id = t.get("id")
        t_name = t.get("name")
        to_name = t.get("to", {}).get("name", "Unknown")
        cat = t.get("to", {}).get("statusCategory", {}).get("name", "")
        lines.append(f"- **{t_name}** (ID: `{t_id}`) ➔ Status: `{to_name}` ({cat})")

    return "\n".join(lines)


def handle_transition_jira_ticket(args: Dict[str, Any]) -> str:
    issue_key = args.get("issue_key", "").strip().upper()
    transition = args.get("transition", "").strip()
    comment = args.get("comment")

    if not issue_key or not transition:
        return "Error: Both `issue_key` and `transition` are required."

    res = jira_client.transition_issue(issue_key, transition, comment=comment)
    base_url = config.url.rstrip("/")
    url = f"{base_url}/browse/{issue_key}"

    return (
        f"✅ Successfully transitioned **[{issue_key}]({url})**:\n"
        f"- **New Status**: `{res.get('status')}`\n"
        f"- **Transition**: '{res.get('transition_name')}' (ID: {res.get('transition_id')})\n"
        + (f"- **Comment**: {comment}\n" if comment else "")
    )


def handle_add_jira_comment(args: Dict[str, Any]) -> str:
    issue_key = args.get("issue_key", "").strip().upper()
    comment = args.get("comment", "").strip()

    if not issue_key or not comment:
        return "Error: Both `issue_key` and `comment` are required."

    jira_client.add_comment(issue_key, comment)
    base_url = config.url.rstrip("/")
    url = f"{base_url}/browse/{issue_key}"

    return f"💬 Added comment to **[{issue_key}]({url})**:\n> {comment}"


def handle_get_jira_user_info(args: Dict[str, Any]) -> str:
    user = jira_client.get_current_user()
    display_name = user.get("displayName", "N/A")
    email = user.get("emailAddress", config.email or "N/A")
    account_id = user.get("accountId", user.get("name", "N/A"))
    time_zone = user.get("timeZone", "N/A")
    active = user.get("active", True)

    return (
        f"### Jira Authenticated User\n"
        f"- **Display Name**: {display_name}\n"
        f"- **Email**: {email}\n"
        f"- **Account ID**: `{account_id}`\n"
        f"- **Timezone**: {time_zone}\n"
        f"- **Active**: {active}\n"
        f"- **Instance**: {config.url}\n"
    )


# MCP Tool Schemas
TOOLS_METADATA: List[Dict[str, Any]] = [
    {
        "name": "get_my_jira_tickets",
        "description": "Retrieve all Jira tickets associated with the authenticated user (assigned, reported, or mentioned). Supports filtering by status, project, and custom username.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["open", "in_progress", "completed", "all"],
                    "description": "Filter by status: 'open' (uncompleted), 'in_progress', 'completed', or 'all'. Defaults to 'open'.",
                },
                "project": {
                    "type": "string",
                    "description": "Optional project key to filter tickets (e.g. 'PROJ').",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of issues to return (default 25).",
                },
                "username": {
                    "type": "string",
                    "description": "Optional username or account identifier to query for. Defaults to currently authenticated user.",
                },
            },
        },
        "handler": handle_get_my_jira_tickets,
    },
    {
        "name": "get_jira_ticket",
        "description": "Get detailed information about a specific Jira issue by key (e.g. PROJ-123), including summary, description, priority, status, assignee, and comments.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "issue_key": {
                    "type": "string",
                    "description": "The Jira issue key, e.g. 'PROJ-123'.",
                }
            },
            "required": ["issue_key"],
        },
        "handler": handle_get_jira_ticket,
    },
    {
        "name": "search_jira_tickets",
        "description": "Search Jira issues using a custom JQL (Jira Query Language) string.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "jql": {
                    "type": "string",
                    "description": "JQL query string, e.g. 'project = ABC AND status = \"In Progress\"'.",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of issues to return (default 25).",
                },
            },
            "required": ["jql"],
        },
        "handler": handle_search_jira_tickets,
    },
    {
        "name": "update_jira_ticket",
        "description": "Edit fields on an existing Jira issue (summary, description, priority, labels, assignee) and optionally post a comment.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "issue_key": {
                    "type": "string",
                    "description": "The Jira issue key, e.g. 'PROJ-123'.",
                },
                "summary": {
                    "type": "string",
                    "description": "New summary/title for the ticket.",
                },
                "description": {
                    "type": "string",
                    "description": "New description text for the ticket.",
                },
                "priority": {
                    "type": "string",
                    "description": "New priority name, e.g. 'High', 'Medium', 'Low'.",
                },
                "labels": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of labels to assign.",
                },
                "assignee": {
                    "type": "string",
                    "description": "New assignee username or accountId. Set to empty string to unassign.",
                },
                "comment": {
                    "type": "string",
                    "description": "Optional comment to add during the update.",
                },
            },
            "required": ["issue_key"],
        },
        "handler": handle_update_jira_ticket,
    },
    {
        "name": "complete_jira_ticket",
        "description": "Mark a Jira ticket as completed / done. Automatically identifies and executes the 'Done' or 'Resolved' workflow transition, with an optional resolution comment.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "issue_key": {
                    "type": "string",
                    "description": "The Jira issue key, e.g. 'PROJ-123'.",
                },
                "comment": {
                    "type": "string",
                    "description": "Optional closing/resolution comment to post.",
                },
                "transition_name": {
                    "type": "string",
                    "description": "Optional explicit transition name (e.g. 'Done', 'Close Issue'). If omitted, will auto-detect.",
                },
            },
            "required": ["issue_key"],
        },
        "handler": handle_complete_jira_ticket,
    },
    {
        "name": "list_ticket_transitions",
        "description": "List all available workflow transitions for a Jira ticket to check allowable state changes.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "issue_key": {
                    "type": "string",
                    "description": "The Jira issue key, e.g. 'PROJ-123'.",
                }
            },
            "required": ["issue_key"],
        },
        "handler": handle_list_ticket_transitions,
    },
    {
        "name": "transition_jira_ticket",
        "description": "Move a Jira ticket to any workflow state by transition name or ID (e.g. 'In Progress', 'In Review', 'Done').",
        "inputSchema": {
            "type": "object",
            "properties": {
                "issue_key": {
                    "type": "string",
                    "description": "The Jira issue key, e.g. 'PROJ-123'.",
                },
                "transition": {
                    "type": "string",
                    "description": "Transition ID or transition name (e.g. 'In Progress', 'Done').",
                },
                "comment": {
                    "type": "string",
                    "description": "Optional comment to include with the transition.",
                },
            },
            "required": ["issue_key", "transition"],
        },
        "handler": handle_transition_jira_ticket,
    },
    {
        "name": "add_jira_comment",
        "description": "Add a new comment to a Jira ticket.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "issue_key": {
                    "type": "string",
                    "description": "The Jira issue key, e.g. 'PROJ-123'.",
                },
                "comment": {
                    "type": "string",
                    "description": "The comment text to post.",
                },
            },
            "required": ["issue_key", "comment"],
        },
        "handler": handle_add_jira_comment,
    },
    {
        "name": "get_jira_user_info",
        "description": "Fetch the currently authenticated Jira user profile details (name, email, account ID, timezone).",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
        "handler": handle_get_jira_user_info,
    },
]

TOOL_HANDLERS: Dict[str, Callable[[Dict[str, Any]], str]] = {
    t["name"]: t["handler"] for t in TOOLS_METADATA
}


def get_tools_manifest() -> List[Dict[str, Any]]:
    """Returns the MCP tools manifest without internal handler references."""
    return [
        {
            "name": t["name"],
            "description": t["description"],
            "inputSchema": t["inputSchema"],
        }
        for t in TOOLS_METADATA
    ]
