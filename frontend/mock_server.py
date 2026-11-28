"""Serve the Streamlit demo fixtures over HTTP on localhost."""

import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from requests import Timeout

from frontend.mock_api import ask


HTTP_ERRORS = {
    "[mock:http401]": (401, "AUTH_REQUIRED", "Mock API key required"),
    "[mock:http422]": (422, "INVALID_REQUEST", "Mock request validation failed"),
}


class MockAskHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        if self.path != "/api/v1/ask":
            self.send_error(404)
            return

        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 32_768:
                raise ValueError("Invalid request body size")
            request = json.loads(self.rfile.read(size))
            if not isinstance(request, dict) or not isinstance(request.get("query"), str):
                raise ValueError("query must be a string")
        except ValueError:
            self.send_error(400, "Expected a JSON object with a string query")
            return

        query = request["query"].strip().casefold()
        if query in HTTP_ERRORS:
            status, code, message = HTTP_ERRORS[query]
            self.send_json(status, {"error_code": code, "message": message})
            return

        if query == "[mock:network_timeout]":
            time.sleep(3)
            self.send_json(200, ask("[mock:success]"))
            return

        status = 200
        if query == "[mock:http503]":
            request["query"] = "[mock:error]"
            status = 503

        try:
            response = ask(
                request["query"],
                as_of_date=request.get("as_of_date"),
                request_id=request.get("request_id"),
            )
        except Timeout:
            self.send_error(504, "Mock upstream timeout")
            return

        if status == 503:
            response["error_code"] = "LLM_UNAVAILABLE"
            response["error"] = {"message": "Mô phỏng Qwen không kết nối được.", "retryable": True}
        elif response.get("error_code") == "INTERNAL_ERROR":
            status = 500
        elif response.get("error_code") == "LLM_TIMEOUT":
            status = 504
        self.send_json(status, response)

    def send_json(self, status: int, response: dict) -> None:
        body = json.dumps(response, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass  # The client may have timed out before the mock responded.


if __name__ == "__main__":
    with ThreadingHTTPServer(("127.0.0.1", 8001), MockAskHandler) as server:
        print("Mock API: http://127.0.0.1:8001/api/v1/ask", flush=True)
        server.serve_forever()
