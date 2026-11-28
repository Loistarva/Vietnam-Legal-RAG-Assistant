"""AST & literal scan enforcing FR6.1 / FR6.1-AC1 provider HTTP isolation outside model_gateway."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

BACKEND_PACKAGES: tuple[str, ...] = (
    "api",
    "orchestration",
    "agent",
    "retrieval",
    "reranking",
    "generation",
    "grounding",
    "monitoring",
)
FRONTEND_PACKAGE = "frontend"

FORBIDDEN_HTTP_AND_PROVIDER_MODULES: tuple[str, ...] = (
    "httpx",
    "requests",
    "urllib.request",
    "urllib3",
    "aiohttp",
    "openai",
    "ollama",
    "anthropic",
    "google.genai",
    "google.generativeai",
)

# frontend/ calls our own FastAPI server via requests (IR1.6), so only LLM provider SDKs
# and non-backend HTTP clients / direct model_gateway bypasses are forbidden in frontend/.
FORBIDDEN_FRONTEND_MODULES: tuple[str, ...] = (
    "httpx",
    "urllib.request",
    "urllib3",
    "aiohttp",
    "openai",
    "ollama",
    "anthropic",
    "google.genai",
    "google.generativeai",
    "model_gateway",
)

PROVIDER_ENDPOINT_MARKERS: tuple[str, ...] = (
    "/api/generate",
    "/api/chat",
    "/api/tags",
    "11434",
    "v1/chat/completions",
    "api.openai.com",
    "generativelanguage.googleapis.com",
)


def _iter_imported_modules(source: str, file_path: Path) -> list[tuple[int, str]]:
    """Return every top-level / dotted module imported in ``source``."""
    tree = ast.parse(source, filename=str(file_path))
    imports: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append((node.lineno, alias.name))
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            imports.append((node.lineno, mod))
            for alias in node.names:
                if mod:
                    imports.append((node.lineno, f"{mod}.{alias.name}"))
    return imports


def _matches_forbidden(imported: str, forbidden: tuple[str, ...]) -> str | None:
    for target in forbidden:
        if imported == target or imported.startswith(f"{target}."):
            return target
    return None


@pytest.mark.req("FR6.1")
@pytest.mark.req("FR6.1-AC1")
def test_no_direct_provider_http_imports_outside_model_gateway():
    violations: list[str] = []

    for pkg in BACKEND_PACKAGES:
        pkg_dir = ROOT / pkg
        if not pkg_dir.exists():
            continue
        for py_file in sorted(pkg_dir.rglob("*.py")):
            source = py_file.read_text(encoding="utf-8")
            rel = py_file.relative_to(ROOT).as_posix()
            for lineno, mod_name in _iter_imported_modules(source, py_file):
                matched = _matches_forbidden(mod_name, FORBIDDEN_HTTP_AND_PROVIDER_MODULES)
                if matched:
                    violations.append(f"{rel}:{lineno} imports forbidden HTTP/provider module '{mod_name}' ({matched})")

    frontend_dir = ROOT / FRONTEND_PACKAGE
    if frontend_dir.exists():
        for py_file in sorted(frontend_dir.rglob("*.py")):
            source = py_file.read_text(encoding="utf-8")
            rel = py_file.relative_to(ROOT).as_posix()
            for lineno, mod_name in _iter_imported_modules(source, py_file):
                matched = _matches_forbidden(mod_name, FORBIDDEN_FRONTEND_MODULES)
                if matched:
                    violations.append(f"{rel}:{lineno} imports forbidden module '{mod_name}' ({matched})")

    assert not violations, "Phát hiện vi phạm cô lập Model Gateway (FR6.1-AC1):\n" + "\n".join(violations)


@pytest.mark.req("FR6.1")
@pytest.mark.req("FR6.1-AC1")
def test_no_direct_provider_endpoint_literals_outside_model_gateway():
    violations: list[str] = []
    for pkg in (*BACKEND_PACKAGES, FRONTEND_PACKAGE):
        pkg_dir = ROOT / pkg
        if not pkg_dir.exists():
            continue
        for py_file in sorted(pkg_dir.rglob("*.py")):
            source = py_file.read_text(encoding="utf-8")
            rel = py_file.relative_to(ROOT).as_posix()
            for marker in PROVIDER_ENDPOINT_MARKERS:
                if marker in source:
                    violations.append(f"{rel} contains provider endpoint marker '{marker}'")

    assert not violations, "Phát hiện URL/port provider trực tiếp ngoài model_gateway/:\n" + "\n".join(violations)
