"""Fixed repair instructions for a single production Gate retry (FR5.6)."""
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

REPAIR_NOTES_VERSION = "repair_notes_v1"
# Until S12-D1.2 lands, only these reasons are repairable. Outside-context,
# CITATION_*, INVALID_CITATION_*, SOURCE_MAP_*, invalid JSON and language failures are excluded.
REPAIRABLE_REASONS: Mapping[str, str] = MappingProxyType({
    "LLM_OUTPUT_TRUNCATED": "truncated",
    "LLM_OUTPUT_TRUNCATED_JSON": "truncated",
    "ANSWER_MARKER_NOT_IN_EVIDENCE_INDICES": "undeclared_marker",
})
REPAIR_NOTES: Mapping[str, str] = MappingProxyType({
    "truncated": "LƯU Ý SỬA LỖI: Lần trả lời trước bị cắt vì quá dài. Hãy trả lời ngắn gọn hơn, "
                 "giữ đúng định dạng JSON đã yêu cầu và chỉ dựa trên các căn cứ đã cho.",
    "undeclared_marker": "LƯU Ý SỬA LỖI: Lần trả lời trước dùng ký hiệu [n] không có trong evidence_indices. "
                         "Chỉ dùng ký hiệu [n] của các căn cứ đã liệt kê trong evidence_indices, "
                         "giữ đúng định dạng JSON đã yêu cầu.",
})


@dataclass(frozen=True)
class RegenerationPolicy:
    repairable: Mapping[str, str] = field(default_factory=lambda: REPAIRABLE_REASONS)
    notes: Mapping[str, str] = field(default_factory=lambda: REPAIR_NOTES)
    version: str = REPAIR_NOTES_VERSION

    def __post_init__(self) -> None:
        missing = set(self.repairable.values()) - self.notes.keys()
        if missing:
            raise ValueError(f"Missing repair notes: {sorted(missing)}")

    def note_for(self, reason: str | None) -> str | None:
        if reason not in self.repairable:
            return None
        return self.notes[self.repairable[reason]]

    def repair_prompt(self, prompt: str, reason: str) -> str:
        return prompt + "\n\n" + self.notes[self.repairable[reason]]
