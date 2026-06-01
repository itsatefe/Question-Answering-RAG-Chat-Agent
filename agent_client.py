import asyncio
import threading

from google.adk.runners import Runner
from google.genai import types

from agent import AGENT_APP_NAME, build_agent, build_session_service


class LocalRunnerAgentClient:
    def __init__(self):
        self.app_name = AGENT_APP_NAME
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._run_loop,
            name="local-adk-runner-loop",
            daemon=True,
        )
        self._thread.start()
        self.session_service = build_session_service()
        self.runner = Runner(
            app_name=self.app_name,
            agent=build_agent(),
            session_service=self.session_service,
        )

    def _run_loop(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def _run_async(self, coro):
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result()

    def create_session(self, user_id: str):
        return self._run_async(self.session_service.create_session(
            app_name=self.app_name,
            user_id=user_id,
        ))

    def list_sessions(self, user_id: str):
        return self._run_async(self.session_service.list_sessions(
            app_name=self.app_name,
            user_id=user_id,
        ))

    def get_session(self, user_id: str, session_id: str):
        return self._run_async(self.session_service.get_session(
            app_name=self.app_name,
            user_id=user_id,
            session_id=session_id,
        ))

    def stream_query(self, user_id: str, session_id: str, message: str):
        content = types.Content(
            role="user",
            parts=[types.Part(text=message)],
        )

        async def _collect_events():
            events = []
            async for event in self.runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=content,
            ):
                events.append(event)
            return events

        return iter(self._run_async(_collect_events()))

    def close(self):
        self._run_async(self.session_service.close())
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=5)


def create_agent_client() -> LocalRunnerAgentClient:
    return LocalRunnerAgentClient()
