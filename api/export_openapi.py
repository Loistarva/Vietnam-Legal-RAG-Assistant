"""Write the OpenAPI snapshot ``api/openapi.json`` (Sprint 10 D5.6).

    python -m api.export_openapi            # rewrite the snapshot
    python -m api.export_openapi --check    # exit 1 if the snapshot is stale

``test/api/test_openapi_contract.py`` fails when the app and the snapshot differ, so a
breaking change to routes or schemas shows up in review. Dev 2 builds the UI client from
this file. No API key or pipeline is needed: a placeholder key and the mock pipeline are used.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SNAPSHOT = Path(__file__).resolve().parent / "openapi.json"
PLACEHOLDER_KEY = "openapi-export-placeholder-key"


def build_spec() -> dict:
    from api.main import create_app
    from api.settings import ApiSettings
    from orchestration.wiring import ServiceSettings, build_ask_service

    app = create_app(settings=ApiSettings(api_keys=PLACEHOLDER_KEY),
                     service=build_ask_service(ServiceSettings(mode="mock")))
    return app.openapi()


def render(spec: dict) -> str:
    return json.dumps(spec, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="Chỉ kiểm tra snapshot, không ghi")
    args = parser.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    text = render(build_spec())
    if args.check:
        current = SNAPSHOT.read_text(encoding="utf-8") if SNAPSHOT.exists() else ""
        if current != text:
            print(f"{SNAPSHOT} đã cũ: chạy python -m api.export_openapi", file=sys.stderr)
            return 1
        return 0
    SNAPSHOT.write_text(text, encoding="utf-8", newline="\n")
    print(f"Đã ghi {SNAPSHOT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
