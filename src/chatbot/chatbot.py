"""
Thin backward-compatible entry point. The real logic now lives in
graph.py, which adds short-term conversation memory -- this file just
re-exposes a simple function name so nothing else needs to change.
"""

 
from src.chatbot.graph import ask
 
 
def answer_question(question: str, thread_id: str = "default-session") -> str:
    return ask(question, thread_id=thread_id)
 
 
if __name__ == "__main__":
    # Loading .env here specifically, because running this file directly
    # (poetry run python -m src.chatbot.chatbot) skips main.py entirely --
    # and main.py is normally what loads the .env file. Any file with its
    # own standalone test block needs to handle this itself.
    from dotenv import load_dotenv
    load_dotenv()

    # Quick manual test -- two related questions, second one is a follow-up
    # that only makes sense WITH memory of the first.
    print("Q: How many members can be on a team?")
    print(f"A: {answer_question('How many members can be on a team?')}\n")

    print("Q: And what age do they need to be?")
    print(f"A: {answer_question('And what age do they need to be?')}")
