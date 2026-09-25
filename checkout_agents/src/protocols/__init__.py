"""Agent-to-Agent (A2A) protocol package."""

from .a2a_schema import A2AMessage, TaskRequest, Artifacts, AgentID, PerformativeEnum

__all__ = ["A2AMessage", "TaskRequest", "Artifacts", "AgentID", "PerformativeEnum"]
