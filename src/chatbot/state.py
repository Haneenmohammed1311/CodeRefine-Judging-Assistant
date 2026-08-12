"""
The chat equivalent of agent/state.py -- but much simpler, because a
conversation only needs to track one thing: the growing list of messages.

`add_messages` is a special LangGraph function: normally, returning a new
value for a state field REPLACES the old one. add_messages changes that
behavior specifically for this field so new messages get APPENDED to the
list instead of overwriting it. That's what makes conversation memory work.
"""

from typing import TypedDict, Annotated
from langgraph.graph.message import add_messages


class ChatState(TypedDict):
    messages: Annotated[list, add_messages]
