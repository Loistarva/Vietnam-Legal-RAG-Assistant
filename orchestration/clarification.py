"""Build clarification messages from versioned, fixed question templates."""
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

import yaml

from orchestration.rag_pipeline import CLARIFY_MESSAGE


def _require_text(value: object, key: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} phải là chuỗi không rỗng")


@dataclass(frozen=True)
class ClarificationCatalog:
    version: str
    questions: Mapping[str, str]
    generic_message: str = CLARIFY_MESSAGE

    def __post_init__(self) -> None:
        _require_text(self.version, "version")
        _require_text(self.generic_message, "generic_message")
        for code, question in self.questions.items():
            _require_text(code, f"facts[{code!r}]")
            _require_text(question, f"facts[{code!r}].question")
        object.__setattr__(self, "questions", MappingProxyType(dict(self.questions)))

    @classmethod
    def from_mapping(cls, data: Mapping) -> "ClarificationCatalog":
        if not isinstance(data, Mapping) or "version" not in data:
            raise ValueError("Thiếu khóa version")
        facts = data.get("facts")
        if not isinstance(facts, Mapping):
            raise ValueError("facts phải là một bảng ánh xạ")
        questions = {}
        for code, fact in facts.items():
            if not isinstance(fact, Mapping) or "question" not in fact:
                raise ValueError(f"Thiếu khóa facts[{code!r}].question")
            questions[code] = fact["question"]
        return cls(data["version"], questions, data.get("generic_message", CLARIFY_MESSAGE))


def load_clarification_catalog(path: str | Path) -> ClarificationCatalog:
    with Path(path).open(encoding="utf-8") as stream:
        return ClarificationCatalog.from_mapping(yaml.safe_load(stream))


@dataclass(frozen=True)
class Clarification:
    message: str
    kept: tuple[str, ...]
    dropped_count: int
    catalog_version: str | None
    generic: bool


def build_clarification(missing_facts: Sequence[str], catalog: ClarificationCatalog | None) -> Clarification:
    codes = dict.fromkeys(missing_facts)
    if catalog is None:
        return Clarification(CLARIFY_MESSAGE, (), len(codes), None, generic=True)
    kept = tuple(code for code in codes if code in catalog.questions)
    message = catalog.generic_message
    if kept:
        header = "Để xác định quy định áp dụng, vui lòng cho biết thêm:"
        message = "\n".join([header, *(f"- {catalog.questions[code]}" for code in kept)])
    return Clarification(message, kept, len(codes) - len(kept), catalog.version, generic=not kept)
