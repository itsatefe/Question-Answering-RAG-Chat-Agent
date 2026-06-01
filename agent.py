from google.adk.agents import Agent

from config import SESSION_DB_ECHO, SESSION_SERVICE_URI
from rag_pipeline import search_documents


AGENT_APP_NAME = "research_qa_agent"

TOOLS = [search_documents]


def build_session_service():
    if SESSION_SERVICE_URI:
        from google.adk.sessions import DatabaseSessionService
        return DatabaseSessionService(db_url=SESSION_SERVICE_URI, echo=SESSION_DB_ECHO)

    from google.adk.sessions import InMemorySessionService
    return InMemorySessionService()


def build_agent() -> Agent:
    return Agent(
        model="gemini-2.5-flash-lite",
        name=AGENT_APP_NAME,
        instruction=(
            "You are a research assistant. Your ONLY source of knowledge about research papers "
            "is the search_documents tool. You have no other access to paper content.\n\n"
            "RULES — follow these without exception:\n"
            "1. For ANY question about a paper's content, methods, findings, authors, or claims: "
            "call search_documents first. Never answer from memory.\n"
            "2. Every factual statement you make MUST be followed by a citation in this exact format: "
            "(Source: <filename>, page <N>, excerpt <N>). No citation = do not make the claim.\n"
            "3. If search_documents returns no useful results, say exactly: "
            "'I could not find relevant information in the documents for this question.' "
            "Do not guess or supplement with general knowledge.\n"
            "4. Quote the paper directly where possible rather than paraphrasing."
        ),
        tools=TOOLS,
    )
