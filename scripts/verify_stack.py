from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request


def fetch_json(url: str) -> tuple[int, object]:
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = resp.read().decode("utf-8")
        return resp.status, json.loads(data)


def fetch_text(url: str) -> tuple[int, str]:
    req = urllib.request.Request(url, headers={"Accept": "text/html,application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = resp.read().decode("utf-8", errors="replace")
        return resp.status, data


def check(name: str, func) -> bool:
    try:
        message = func()
        print(f"[OK] {name}: {message}")
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"[FAIL] {name}: {exc}")
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify DocQA local/dev or Docker deployment.")
    parser.add_argument("--backend-url", default="http://localhost:8000", help="Backend base URL")
    parser.add_argument("--frontend-url", default="http://localhost:8080", help="Frontend base URL")
    args = parser.parse_args()

    backend_url = args.backend_url.rstrip("/")
    frontend_url = args.frontend_url.rstrip("/")

    checks = [
        (
            "Backend Health",
            lambda: _check_backend_health(backend_url),
        ),
        (
            "Frontend Home",
            lambda: _check_frontend_home(frontend_url),
        ),
        (
            "Frontend Proxy Health",
            lambda: _check_frontend_proxy_health(frontend_url),
        ),
        (
            "Frontend Proxy API",
            lambda: _check_frontend_proxy_api(frontend_url),
        ),
    ]

    results = [check(name, func) for name, func in checks]
    if all(results):
        print("\nDeployment verification passed.")
        print("Next manual acceptance path:")
        print("1. 打开前端首页")
        print("2. 到设置页添加一个 provider")
        print("3. 到文档页上传一个 txt / md / pdf / docx")
        print("4. 到问答页新建会话并提问")
        print("5. 确认回答和来源面板都能显示")
        return 0

    print("\nDeployment verification failed. Please inspect the failed checks above.")
    return 1


def _check_backend_health(backend_url: str) -> str:
    status, data = fetch_json(f"{backend_url}/health")
    if status != 200:
        raise RuntimeError(f"unexpected status {status}")
    if data.get("status") != "ok":
        raise RuntimeError(f"unexpected body {data}")
    return f"status={data.get('status')} app={data.get('app')}"


def _check_frontend_home(frontend_url: str) -> str:
    status, body = fetch_text(frontend_url + "/")
    if status != 200:
        raise RuntimeError(f"unexpected status {status}")
    if "<!doctype html" not in body.lower():
        raise RuntimeError("did not receive HTML shell")
    return "index.html served"


def _check_frontend_proxy_health(frontend_url: str) -> str:
    status, data = fetch_json(f"{frontend_url}/health")
    if status != 200:
        raise RuntimeError(f"unexpected status {status}")
    if data.get("status") != "ok":
        raise RuntimeError(f"unexpected body {data}")
    return "frontend proxy -> backend health ok"


def _check_frontend_proxy_api(frontend_url: str) -> str:
    status, data = fetch_json(f"{frontend_url}/api/providers")
    if status != 200:
        raise RuntimeError(f"unexpected status {status}")
    if not isinstance(data, list):
        raise RuntimeError(f"unexpected body type {type(data).__name__}")
    return f"providers_endpoint_ok count={len(data)}"


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except urllib.error.URLError as exc:
        print(f"[FAIL] Network error: {exc}")
        raise SystemExit(1)
