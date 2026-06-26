"""
Prompts package.

All LLM prompt templates are stored here as plain strings or Jinja2-style
templates. Keeping prompts in one place makes them easy to version,
review, and iterate on without touching business logic.

Template naming convention:

    SYSTEM_<AGENT_NAME>    — system prompt for an agent
    TOOL_<TOOL_NAME>       — tool-specific instruction fragment
    PERSONA_RECEPTIONIST   — the AI persona definition

These will be populated in the next development phase.
"""
