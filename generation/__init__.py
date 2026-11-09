"""
generation package
Prompt Builder and Generation components for Sprint 9.
"""
from generation.prompt_builder import (
    PROMPT_A_VERSION,
    PROMPT_B_VERSION,
    STANDARD_DISCLAIMER,
    build_controlled_rag_prompt,
    build_zero_shot_prompt,
    format_evidence_item,
    get_prompt_hash,
    map_evidence_indices_to_citations,
)

__all__ = [
    "PROMPT_A_VERSION",
    "PROMPT_B_VERSION",
    "STANDARD_DISCLAIMER",
    "build_controlled_rag_prompt",
    "build_zero_shot_prompt",
    "format_evidence_item",
    "get_prompt_hash",
    "map_evidence_indices_to_citations",
]
