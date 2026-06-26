import os

from google.adk.agents import Agent

from config import SESSION_DB_ECHO, SESSION_SERVICE_URI
from rag_pipeline import search_documents


AGENT_APP_NAME = "research_qa_agent"

TOOLS = [search_documents]

_PROMPT_FILE = os.path.join(
    os.path.dirname(__file__), "frontend", "lib", "generated", "system-prompt.txt"
)

_RAG_RULES = """
## Research Assistant Rules (override "generate realistic data" rule above)

You are a research assistant. Your ONLY source of knowledge is the search_documents tool.

1. For ANY question about paper content, methods, findings, or authors: call search_documents
   first. Never answer from memory or invent data.
   - When asked about a specific table or figure (e.g. "table 6"), search its topic rather than
     its number. Also try a second search with the literal string if the first returns nothing.
2. Every factual claim MUST include a citation embedded in the markdown text:
   (Source: <filename>, page <N>, excerpt <N>). No citation = do not make the claim.
3. If search_documents returns no useful results, respond with:
   TextContent("I could not find relevant information in the documents for this question.")
4. Quote the paper directly where possible rather than paraphrasing.

## Response Structure

- Wrap ALL text (answers, citations, explanations) in MarkDownRenderer — never output bare text.
- For data visualisation requests: call search_documents first, then build charts/tables from
  the returned data. Never invent numbers.
- Structure: MarkDownRenderer with the answer + citations, followed by any charts or tables.
- Root must always be root = Stack([...]).
"""


def _load_instruction() -> str:
    try:
        with open(_PROMPT_FILE, encoding="utf-8") as f:
            openui_prompt = f.read()
    except FileNotFoundError:
        raise RuntimeError(
            f"OpenUI system prompt not found at {_PROMPT_FILE}. "
            "Run: cd frontend && npx @openuidev/cli generate lib/openui-library/index.ts "
            "--out lib/generated/system-prompt.txt"
        )
    return openui_prompt + _RAG_RULES


def build_session_service():
    if SESSION_SERVICE_URI:
        from google.adk.sessions import DatabaseSessionService
        return DatabaseSessionService(db_url=SESSION_SERVICE_URI, echo=SESSION_DB_ECHO)

    from google.adk.sessions import InMemorySessionService
    return InMemorySessionService()


def build_agent() -> Agent:
    return Agent(
        model="gemini-2.5-pro",
        name=AGENT_APP_NAME,
        instruction=_load_instruction(),
        tools=TOOLS,
    )
