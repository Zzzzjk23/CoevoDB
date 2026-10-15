"""LLM gateway for the roles that propose specs, hypotheses, and rewrites."""

from . import constants
from .cache import ResponseCache, cache_key
from .gateway import Completion, Gateway, Reply, TransportError
from .schema import parse_reply
from .source import Hit, Snippet, SourceError, SourceReader, open_sources, source_roots
from .implementer import Attempt, Implementer, implementer_prompt, implementer_report
from .conjecturer import (
    Conjecture,
    ConjectureBook,
    Conjecturer,
    Pending,
    conjecturer_prompt,
    select_sources,
)
from .runtime import ImplementerSource, RoleSet, build_roles

__all__ = [
    "constants",
    "Completion",
    "Reply",
    "Gateway",
    "TransportError",
    "ResponseCache",
    "cache_key",
    "parse_reply",
    "SourceReader",
    "SourceError",
    "Snippet",
    "Hit",
    "source_roots",
    "open_sources",
    "Attempt",
    "Implementer",
    "implementer_prompt",
    "implementer_report",
    "Conjecture",
    "Conjecturer",
    "ConjectureBook",
    "Pending",
    "select_sources",
    "conjecturer_prompt",
    "RoleSet",
    "ImplementerSource",
    "build_roles",
]
