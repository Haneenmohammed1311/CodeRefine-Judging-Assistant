"""
rubric.py : The official grading criteria for CodeRefine's system design challenge.

WHY THIS FILE EXISTS:
    The agent needs to know what to grade and how many points each part is worth.
    Without this, the agent would read a repo and guess randomly what matters.
    This file is the "marking scheme" like an exam answer key.

WHY IT IS HERE (not in the knowledge base):
    The rubric has only 6 fixed items that never change during a competition.
    Putting 6 items in a Chroma vector database would be overkill there's
    no "search" needed when you always want ALL 6 criteria every time.
    So we keep it as a plain Python constant that gets injected directly
    into the agent's prompt. Simple, fast, zero retrieval-failure risk.

SCORING:
    - Base score: out of 100 (sum of all non-bonus criteria)
    - Bonus: adds up to 10 points on top → max possible = 110
    - A perfect submission scoring all non-bonus criteria = 100
"""

RUBRIC = [
    {
        # Worth 15% of the total score.
        "criterion": "Functional & Non-Functional Requirements",
        "description": (
            "How well the submission lists what the system needs to do (functional "
            "requirements) and the qualities the system must have (non-functional "
            "requirements such as scalability, availability, latency). "
            "A strong submission covers at least 4 functional requirements that "
            "address all major use cases, and at least 3 non-functional requirements "
            "that reflect the full user experience. More is a plus, up to a reasonable limit."
        ),
        "weight_percent": 15,
    },
    {
        # Worth 20% of the total score.
        "criterion": "Data Model",
        "description": (
            "How well the submission organizes and structures all data related "
            "to the system. This is NOT a full database schema an overview of "
            "the main entities (tables/collections), their key fields, and their "
            "relationships is what's expected. The data model should cover all "
            "requirements defined in the functional section."
        ),
        "weight_percent": 20,
    },
    {
        # Worth 20% of the total score.
        "criterion": "API Design",
        "description": (
            "How well the submission designs the communication between different "
            "parts of the system. Should cover core functionality not every "
            "possible endpoint, but enough to handle the main flows. "
            "Each endpoint must specify: (1) the endpoint/function name, "
            "(2) the request body or function arguments (what it takes), "
            "(3) the response body or return value (what it gives back)."
        ),
        "weight_percent": 20,
    },
    {
        # Worth 25%  the HIGHEST weight of all criteria.
        "criterion": "High-Level Architecture",
        "description": (
            "How well the submission presents a high-level diagram of all system "
            "components and how they interact. Each component should handle a single "
            "domain (e.g. Auth Service, Payment Service). "
            "CRITICAL checks: (1) shapes must be consistent if circles = databases, "
            "ALL databases must be circles; (2) every shape must be labeled no "
            "unlabeled boxes; (3) interactions between components must be explicitly "
            "shown with arrows or connections. "
            "Can be microservices or modular monolith both are valid."
        ),
        "weight_percent": 25,
    },
    {
        # Worth 20% of the total score.
        "criterion": "Deep Dives",
        "description": (
            "The most important section for demonstrating seniority and depth. "
            "Teams go deep into each critical component in their architecture, "
            "identifying problems that arise at high scale and the trade-offs "
            "they chose to address those problems. "
            "Strong submissions specify: what database type and why, whether "
            "caching makes sense and where, whether a message broker is needed "
            "and why, and other architectural decisions with clear reasoning. "
            "Vague statements like 'we will use Redis' without explaining WHY "
            "score lower than specific trade-off analysis."
        ),
        "weight_percent": 20,
    },
]

BONUS_MAX_PERCENT = 10