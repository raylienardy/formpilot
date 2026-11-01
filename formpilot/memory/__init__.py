"""Memory subsystem for FormPilot.

Two-layer memory:
- sqlite_store: Structured facts (name, NIM, semester, preferences)
- vector_store: Semantic memory (motivations, opinions, narratives)

Splitting is deliberate (see ADR-005): facts don't need semantic search,
and storing facts in vector DB risks wrong retrieval.
"""
