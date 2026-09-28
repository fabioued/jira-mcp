"""
Jira REST API Client.
Zero-dependency client implementing Jira Cloud (v3/v2) and Jira Server/DC operations
using Python's standard library urllib.
"""

import base64
import json
import os
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    from .config import config
except ImportError:
    from config import config


def adf_to_text(node: Any) -> str:
    """Recursively converts Atlassian Document Format (ADF) node to readable plain text."""
    if not node:
        return ""
    if isinstance(node, str):
        return node
    if isinstance(node, list):
        return "".join(adf_to_text(item) for item in node)
    if isinstance(node, dict):
        node_type = node.get("type", "")
        if node_type == "text":
            return node.get("text", "")
        content = node.get("content", [])
        inner_text = "".join(adf_to_text(c) for c in content)
        if node_type in ("paragraph", "heading"):
            return inner_text.strip() + "\n\n" if inner_text.strip() else ""
        elif node_type == "bulletList":
            return inner_text
        elif node_type == "orderedList":
            return inner_text
        elif node_type == "listItem":
            return "• " + inner_text.strip() + "\n"
        elif node_type == "codeBlock":
            return f"```\n{inner_text.strip()}\n```\n\n"
        return inner_text
    return str(node)


def text_to_adf(text: str) -> Dict[str, Any]:
    """Converts plain text into an Atlassian Document Format (ADF) doc structure."""
    if not text:
        text = ""
    lines = text.split("\n")
    paragraphs: List[Dict[str, Any]] = []
    for line in lines:
        stripped = line.rstrip()
        paragraphs.append({
            "type": "paragraph",
            "content": [{"type": "text", "text": stripped}] if stripped else [],
        })
    if not paragraphs:
        paragraphs = [{"type": "paragraph", "content": []}]
    return {
        "type": "doc",
        "version": 1,
        "content": paragraphs,
    }


class JiraClient:
    """Interacts with the Jira REST API."""

    def __init__(self) -> None:
        ssl_cert_env = os.getenv("SSL_CERT_FILE")
        ca_candidates = [
            ssl_cert_env,
            "/etc/ssl/cert.pem",
            "/etc/openssl/cert.pem",
            "/etc/pki/tls/cert.pem",
        ]
        cafile = next((p for p in ca_candidates if p and os.path.isfile(p)), None)
        if cafile:
            try:
                self.ssl_context = ssl.create_default_context(cafile=cafile)
            except Exception:
                self.ssl_context = ssl.create_default_context()
        else:
            self.ssl_context = ssl.create_default_context()

    def _get_auth_headers(self) -> Dict[str, str]:
        email = config.email.strip()
        token = config.api_token.strip()

        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "Antigravity-Jira-MCP/1.0",
        }

        if email and token:
            cred_str = f"{email}:{token}"
            b64_creds = base64.b64encode(cred_str.encode("utf-8")).decode("utf-8")
            headers["Authorization"] = f"Basic {b64_creds}"
        elif token:
            # Bearer token fallback if PAT is used
            headers["Authorization"] = f"Bearer {token}"
        return headers

    def _parse_http_error(self, e: urllib.error.HTTPError, url: str) -> None:
        status = e.code
        error_body = e.read().decode("utf-8", errors="replace")
        try:
            error_json = json.loads(error_body)
            err_msg = error_json.get("errorMessages", [])
            err_fields = error_json.get("errors", {})
            all_msgs = []
            if err_msg:
                all_msgs.extend(err_msg)
            if err_fields:
                all_msgs.extend([f"{k}: {v}" for k, v in err_fields.items()])
            msg_str = "; ".join(all_msgs) if all_msgs else error_body
        except Exception:
            msg_str = error_body

        if status == 401:
            raise PermissionError(
                f"Jira Authentication Failed (HTTP 401). Please verify your JIRA_EMAIL and JIRA_API_TOKEN. Error details: {msg_str}"
            )
        elif status == 403:
            raise PermissionError(
                f"Jira Forbidden (HTTP 403). You do not have permission for this resource. Details: {msg_str}"
            )
        elif status == 404:
            raise FileNotFoundError(f"Jira Resource not found (HTTP 404): {url}. Details: {msg_str}")
        else:
            raise RuntimeError(f"Jira API error {status}: {msg_str}")

    def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        query_params: Optional[Dict[str, Any]] = None,
    ) -> Tuple[int, Any]:
        """Performs an HTTP request to Jira and returns (status_code, parsed_json_or_text)."""
        base_url = config.url.rstrip("/")
        if not base_url:
            raise ValueError("Jira URL is not configured. Please set JIRA_URL.")

        url = f"{base_url}{endpoint}"
        if query_params:
            filtered_params = {k: v for k, v in query_params.items() if v is not None}
            url = f"{url}?{urllib.parse.urlencode(filtered_params)}"

        headers = self._get_auth_headers()
        payload_bytes: Optional[bytes] = None
        if data is not None:
            payload_bytes = json.dumps(data).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=payload_bytes,
            headers=headers,
            method=method.upper(),
        )

        try:
            with urllib.request.urlopen(req, context=self.ssl_context, timeout=30) as resp:
                status = resp.status
                body = resp.read().decode("utf-8")
                if not body.strip():
                    return status, None
                try:
                    return status, json.loads(body)
                except json.JSONDecodeError:
                    return status, body
        except urllib.error.HTTPError as e:
            self._parse_http_error(e, url)
        except urllib.error.URLError as e:
            # If SSL certificate verification failed, retry with unverified context
            if "CERTIFICATE_VERIFY_FAILED" in str(e.reason):
                try:
                    unverified_ctx = ssl._create_unverified_context()
                    with urllib.request.urlopen(req, context=unverified_ctx, timeout=30) as resp:
                        status = resp.status
                        body = resp.read().decode("utf-8")
                        if not body.strip():
                            return status, None
                        try:
                            return status, json.loads(body)
                        except json.JSONDecodeError:
                            return status, body
                except urllib.error.HTTPError as he:
                    self._parse_http_error(he, url)
                except Exception:
                    pass
            raise ConnectionError(f"Failed to connect to Jira at {url}: {e.reason}")

    def get_current_user(self) -> Dict[str, Any]:
        """Fetch current authenticated user info."""
        # Try Cloud v3 first, then v2
        try:
            _, data = self._request("GET", "/rest/api/3/myself")
            return data
        except Exception:
            _, data = self._request("GET", "/rest/api/2/myself")
            return data

    def search_issues(self, jql: str, max_results: int = 50) -> List[Dict[str, Any]]:
        """Search Jira issues using JQL."""
        fields = [
            "key",
            "summary",
            "status",
            "priority",
            "issuetype",
            "assignee",
            "reporter",
            "updated",
            "created",
            "description",
            "labels",
        ]
        # Jira Cloud /rest/api/3/search/jql requires bounded queries
        clean_jql = jql.strip()
        if not clean_jql:
            clean_jql = "created is not EMPTY ORDER BY created DESC"
        elif clean_jql.upper().startswith("ORDER BY"):
            clean_jql = f"created is not EMPTY {clean_jql}"

        params = {
            "jql": clean_jql,
            "maxResults": max_results,
            "fields": ",".join(fields),
        }
        # Try modern Cloud endpoint first: /rest/api/3/search/jql
        try:
            _, data = self._request("GET", "/rest/api/3/search/jql", query_params=params)
            return data.get("issues", [])
        except Exception as e_jql:
            # Fallback to older /rest/api/3/search
            try:
                _, data = self._request("GET", "/rest/api/3/search", query_params=params)
                return data.get("issues", [])
            except Exception:
                # Fallback to /rest/api/2/search
                try:
                    _, data = self._request("GET", "/rest/api/2/search", query_params=params)
                    return data.get("issues", [])
                except Exception:
                    raise e_jql

    def get_my_tickets(
        self,
        username: Optional[str] = None,
        status_filter: str = "open",
        project: Optional[str] = None,
        max_results: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Retrieves tickets associated with the user (assignee, reporter, or mentioned).
        status_filter options: 'open', 'in_progress', 'completed', 'all'
        """
        clauses = []

        # If username matches default or current user, use currentUser() for Jira Cloud compatibility
        user = (username or config.default_user or "").strip()
        if not user or user == "currentUser()":
            user_clause = "(assignee = currentUser() OR reporter = currentUser())"
        elif ":" in user:
            # AccountId format in Jira Cloud
            user_clause = f'(assignee = "{user}" OR reporter = "{user}")'
        else:
            user_clause = f'(assignee = currentUser() OR reporter = currentUser() OR assignee = "{user}" OR reporter = "{user}")'

        clauses.append(user_clause)

        status_lower = status_filter.lower().strip()
        if status_lower == "open":
            clauses.append("statusCategory != Done")
        elif status_lower == "in_progress":
            clauses.append("statusCategory = 'In Progress'")
        elif status_lower in ("completed", "done"):
            clauses.append("statusCategory = Done")

        if project:
            clauses.append(f'project = "{project}"')

        jql = " AND ".join(clauses) + " ORDER BY updated DESC"
        try:
            return self.search_issues(jql, max_results=max_results)
        except Exception as primary_err:
            fallback_clauses = ["(assignee = currentUser() OR reporter = currentUser())"]
            if status_lower == "open":
                fallback_clauses.append("statusCategory != Done")
            elif status_lower == "in_progress":
                fallback_clauses.append("statusCategory = 'In Progress'")
            elif status_lower in ("completed", "done"):
                fallback_clauses.append("statusCategory = Done")
            if project:
                fallback_clauses.append(f'project = "{project}"')
            fallback_jql = " AND ".join(fallback_clauses) + " ORDER BY updated DESC"
            try:
                return self.search_issues(fallback_jql, max_results=max_results)
            except Exception:
                raise primary_err

    def get_issue(self, issue_key: str) -> Dict[str, Any]:
        """Fetch details of a single Jira issue."""
        key = issue_key.strip().upper()
        try:
            _, data = self._request("GET", f"/rest/api/3/issue/{key}")
            return data
        except Exception:
            _, data = self._request("GET", f"/rest/api/2/issue/{key}")
            return data

    def update_issue(
        self,
        issue_key: str,
        summary: Optional[str] = None,
        description: Optional[str] = None,
        priority: Optional[str] = None,
        labels: Optional[Union[List[str], str]] = None,
        assignee: Optional[str] = None,
        comment: Optional[str] = None,
        extra_fields: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Updates fields on a Jira issue."""
        key = issue_key.strip().upper()
        fields: Dict[str, Any] = {}

        if summary is not None:
            fields["summary"] = summary

        if priority is not None:
            fields["priority"] = {"name": priority}

        if labels is not None:
            if isinstance(labels, str):
                labels = [label.strip() for label in labels.split(",") if label.strip()]
            fields["labels"] = labels

        if assignee is not None:
            assignee_clean = assignee.strip()
            # If empty string, unassign
            if not assignee_clean:
                fields["assignee"] = None
            else:
                fields["assignee"] = {"name": assignee_clean}

        if extra_fields:
            fields.update(extra_fields)

        # Handle description for v3 (ADF) vs v2
        payload_v3: Dict[str, Any] = {"fields": dict(fields)}
        if description is not None:
            payload_v3["fields"]["description"] = text_to_adf(description)

        # Attempt v3 update first
        update_successful = False
        try:
            self._request("PUT", f"/rest/api/3/issue/{key}", data=payload_v3)
            update_successful = True
        except Exception as e_v3:
            # Try v2 with plain text description
            try:
                payload_v2: Dict[str, Any] = {"fields": dict(fields)}
                if description is not None:
                    payload_v2["fields"]["description"] = description
                self._request("PUT", f"/rest/api/2/issue/{key}", data=payload_v2)
                update_successful = True
            except Exception as e_v2:
                raise RuntimeError(f"Failed to update {key}. v3 error: {e_v3}. v2 error: {e_v2}")

        # Add comment if requested
        comment_result = None
        if comment and comment.strip():
            comment_result = self.add_comment(key, comment.strip())

        return {
            "key": key,
            "updated": update_successful,
            "comment_added": bool(comment_result),
        }

    def add_comment(self, issue_key: str, comment_text: str) -> Dict[str, Any]:
        """Adds a comment to an issue."""
        key = issue_key.strip().upper()
        # Try v3 ADF comment
        v3_payload = {"body": text_to_adf(comment_text)}
        try:
            _, data = self._request("POST", f"/rest/api/3/issue/{key}/comment", data=v3_payload)
            return data
        except Exception:
            # Fallback to v2 plain text comment
            v2_payload = {"body": comment_text}
            _, data = self._request("POST", f"/rest/api/2/issue/{key}/comment", data=v2_payload)
            return data

    def get_transitions(self, issue_key: str) -> List[Dict[str, Any]]:
        """Retrieves available workflow transitions for an issue."""
        key = issue_key.strip().upper()
        try:
            _, data = self._request("GET", f"/rest/api/3/issue/{key}/transitions")
            return data.get("transitions", [])
        except Exception:
            _, data = self._request("GET", f"/rest/api/2/issue/{key}/transitions")
            return data.get("transitions", [])

    def transition_issue(
        self,
        issue_key: str,
        transition_id_or_name: str,
        comment: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Transitions an issue to a new status by transition ID or name."""
        key = issue_key.strip().upper()
        transitions = self.get_transitions(key)

        matched_id: Optional[str] = None
        matched_name: Optional[str] = None
        target_status: Optional[str] = None

        search_term = transition_id_or_name.strip().lower()

        for t in transitions:
            t_id = str(t.get("id", ""))
            t_name = str(t.get("name", ""))
            to_name = str(t.get("to", {}).get("name", ""))

            # Direct match by ID
            if t_id == transition_id_or_name.strip():
                matched_id = t_id
                matched_name = t_name
                target_status = to_name
                break

            # Match by transition name or target status name
            if (
                t_name.lower() == search_term
                or to_name.lower() == search_term
                or search_term in t_name.lower()
            ):
                matched_id = t_id
                matched_name = t_name
                target_status = to_name
                break

        if not matched_id:
            available = [
                f"ID {t.get('id')}: '{t.get('name')}' -> '{t.get('to', {}).get('name')}'"
                for t in transitions
            ]
            avail_str = "\n".join(available) if available else "None (issue may be in a final state)"
            raise ValueError(
                f"Transition '{transition_id_or_name}' not available for {key}.\nAvailable transitions:\n{avail_str}"
            )

        payload: Dict[str, Any] = {"transition": {"id": matched_id}}

        # Post transition to Jira
        try:
            self._request("POST", f"/rest/api/3/issue/{key}/transitions", data=payload)
        except Exception:
            self._request("POST", f"/rest/api/2/issue/{key}/transitions", data=payload)

        # Add comment if specified
        if comment and comment.strip():
            try:
                self.add_comment(key, comment.strip())
            except Exception as ce:
                print(f"[Jira] Failed to post transition comment: {ce}", file=sys.stderr)

        return {
            "key": key,
            "transition_id": matched_id,
            "transition_name": matched_name,
            "status": target_status,
            "success": True,
        }

    def complete_issue(
        self,
        issue_key: str,
        comment: Optional[str] = None,
        transition_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Marks an issue as completed by finding and executing a 'Done' / 'Complete' / 'Resolved' transition.
        """
        key = issue_key.strip().upper()
        transitions = self.get_transitions(key)

        if not transitions:
            # Check current status
            issue_data = self.get_issue(key)
            current_status = issue_data.get("fields", {}).get("status", {}).get("name", "Unknown")
            return {
                "key": key,
                "success": False,
                "message": f"No workflow transitions are available for {key}. Current status is already '{current_status}'.",
                "current_status": current_status,
            }

        # If user explicitly provided a transition name
        if transition_name:
            return self.transition_issue(key, transition_name, comment=comment)

        # Automatic detection of 'Done' / 'Completed' transition
        done_candidates = []
        for t in transitions:
            t_id = str(t.get("id"))
            t_name = str(t.get("name", ""))
            to_obj = t.get("to", {})
            to_name = str(to_obj.get("name", ""))
            cat_key = str(to_obj.get("statusCategory", {}).get("key", "")).lower()

            # Priority 1: Destination status category is 'done'
            if cat_key == "done":
                done_candidates.append((1, t_id, t_name, to_name))
                continue

            # Priority 2: Exact name match for Done / Completed / Closed / Resolved
            t_lower = t_name.lower()
            to_lower = to_name.lower()
            if any(term in (t_lower, to_lower) for term in ["done", "completed", "complete", "closed", "resolved"]):
                done_candidates.append((2, t_id, t_name, to_name))
                continue

            # Priority 3: Partial name match
            if any(term in t_lower or term in to_lower for term in ["done", "close", "resolve", "finish"]):
                done_candidates.append((3, t_id, t_name, to_name))

        if not done_candidates:
            available = [
                f"ID {t.get('id')}: '{t.get('name')}' -> '{t.get('to', {}).get('name')}'"
                for t in transitions
            ]
            return {
                "key": key,
                "success": False,
                "message": (
                    f"Could not automatically detect a 'Done' or 'Completed' transition for {key}.\n"
                    f"Available transitions:\n" + "\n".join(available)
                ),
                "available_transitions": transitions,
            }

        # Sort by candidate priority (lowest number first)
        done_candidates.sort(key=lambda x: x[0])
        _, best_id, best_name, target_status = done_candidates[0]

        return self.transition_issue(key, best_id, comment=comment)


jira_client = JiraClient()
