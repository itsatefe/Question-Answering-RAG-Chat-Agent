from agent_client import create_agent_client
from config import USER_ID
from session_utils import create_session, send_message


def main():
    print("Starting research Q&A agent...")
    client = create_agent_client()
    session_id = create_session(client, USER_ID)
    print("Ready. Type your question (Ctrl+C to quit).\n")

    try:
        while True:
            question = input("You: ").strip()
            if not question:
                continue
            reply = send_message(client, USER_ID, session_id, question)
            print(f"\nAgent: {reply}\n")
    except KeyboardInterrupt:
        print("\nBye.")
    finally:
        client.close()


if __name__ == "__main__":
    main()
