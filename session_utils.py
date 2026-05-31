"""Utility functions for working with chat sessions on the deployed agent."""

import asyncio
from typing import Any, Dict, Iterable, List

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from agent import AGENT_APP_NAME
from config import SESSION_SERVICE_URI


def _read_part_attr(part: Any, attr: str, default=None):
    if isinstance(part, dict):
        return part.get(attr, default)
    return getattr(part, attr, default)


def _read_event_attr(event: Any, attr: str, default=None):
    if isinstance(event, dict):
        return event.get(attr, default)
    return getattr(event, attr, default)


def _format_event_parts(parts: List[Any]) -> str:
    rendered: List[str] = []

    for part in parts:
        text = _read_part_attr(part, "text")
        if text:
            rendered.append(text)
            continue

        function_call = _read_part_attr(part, "function_call")
        if function_call:
            name = _read_part_attr(function_call, "name", "unknown_tool")
            args = _read_part_attr(function_call, "args", {})
            rendered.append(f"[tool call] {name}({args})")
            continue

        function_response = _read_part_attr(part, "function_response")
        if function_response:
            name = _read_part_attr(function_response, "name", "unknown_tool")
            response = _read_part_attr(function_response, "response", {})
            rendered.append(f"[tool response] {name}: {response}")

    return " ".join(rendered).strip()


def _session_summary(session: Dict[str, Any] | Any) -> Dict[str, Any]:
    if isinstance(session, dict):
        return {
            "id": session.get("id"),
            "appName": session.get("appName"),
            "userId": session.get("userId"),
            "eventCount": len(session.get("events", [])),
            "state": session.get("state", {}),
            "lastUpdateTime": session.get("lastUpdateTime"),
        }

    return {
        "id": getattr(session, "id", None),
        "app_name": getattr(session, "app_name", None),
        "user_id": getattr(session, "user_id", None),
        "event_count": len(getattr(session, "events", [])),
        "state": getattr(session, "state", {}),
        "last_update_time": getattr(session, "last_update_time", None),
    }


def create_session(remote_agent, user_id: str, verbose: bool = False) -> str:
    session = remote_agent.create_session(user_id=user_id)
    session_id = session["id"] if isinstance(session, dict) else session.id

    if verbose:
        print("\nCreated session:")
        print(_session_summary(session))

    return session_id


def send_message(remote_agent, user_id: str, session_id: str, message: str, verbose: bool = False) -> str:
    collected_text: List[str] = []

    for event in remote_agent.stream_query(
        user_id=user_id,
        session_id=session_id,
        message=message,
    ):
        content = _read_event_attr(event, "content", {})
        parts = content.get("parts", []) if isinstance(content, dict) else getattr(content, "parts", [])
        text = "".join(_read_part_attr(part, "text", "") or "" for part in parts).strip()

        if text:
            collected_text.append(text)

    if verbose:
        print(f"\nYou: {message}")
        print(f"Agent: {''.join(collected_text).strip()}")

    return "".join(collected_text).strip()


def send_chat(remote_agent, user_id: str, session_id: str, messages: Iterable[str], verbose: bool = False) -> List[str]:
    """Convenience helper to send multiple messages in sequence."""
    responses: List[str] = []
    for message in messages:
        responses.append(send_message(remote_agent, user_id, session_id, message, verbose=verbose))
    return responses


def list_sessions(remote_agent, user_id: str, verbose: bool = False):
    sessions_resp = remote_agent.list_sessions(user_id=user_id)

    sessions = (
        sessions_resp.get("sessions", [])
        if isinstance(sessions_resp, dict)
        else getattr(sessions_resp, "sessions", [])
    )

    if verbose:
        print("\nSessions:")
        if not sessions:
            print("(no sessions found)")
            return []

        for s in sessions:
            session_id = s.get("id") if isinstance(s, dict) else s.id
            print("-", session_id)

    return sessions


def get_session(remote_agent, user_id: str, session_id: str, verbose: bool = False):
    session = remote_agent.get_session(
        user_id=user_id,
        session_id=session_id,
    )

    if verbose:
        print("\nFetched session:")
        print(_session_summary(session))

    return session


def count_session_events(session: Dict[str, Any] | Any) -> int:
    events = session.get("events", []) if isinstance(session, dict) else getattr(session, "events", [])
    return len(events)


def get_db_sync_totals(app_name: str = AGENT_APP_NAME) -> Dict[str, int]:
    if not SESSION_SERVICE_URI:
        return {"users_synced": 0, "sessions_synced": 0, "events_synced": 0}

    async def _read_totals() -> Dict[str, int]:
        engine = create_async_engine(SESSION_SERVICE_URI)
        try:
            async with engine.connect() as connection:
                sessions_count = (
                    await connection.execute(
                        text("SELECT COUNT(*) FROM sessions WHERE app_name = :app_name"),
                        {"app_name": app_name},
                    )
                ).scalar_one()
                users_count = (
                    await connection.execute(
                        text("SELECT COUNT(DISTINCT user_id) FROM sessions WHERE app_name = :app_name"),
                        {"app_name": app_name},
                    )
                ).scalar_one()
                events_count = (
                    await connection.execute(
                        text("SELECT COUNT(*) FROM events WHERE app_name = :app_name"),
                        {"app_name": app_name},
                    )
                ).scalar_one()
        finally:
            await engine.dispose()

        return {
            "users_synced": int(users_count),
            "sessions_synced": int(sessions_count),
            "events_synced": int(events_count),
        }

    return asyncio.run(_read_totals())


def print_session_events(session: Dict[str, Any] | Any):
    events = session.get("events", []) if isinstance(session, dict) else getattr(session, "events", [])

    print("\nSession events:")
    if not events:
        print("(events are empty)")
        return

    for ev in events:
        content = ev.get("content", {}) if isinstance(ev, dict) else getattr(ev, "content", {})
        parts = content.get("parts", []) if isinstance(content, dict) else getattr(content, "parts", [])
        text = _format_event_parts(parts)

        author = ev.get("author") if isinstance(ev, dict) else getattr(ev, "author", None)

        if text:
            print(f"{author}: {text}")
