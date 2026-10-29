"""Read effective Codex configuration and quota availability without starting a model turn."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import queue
import shutil
import subprocess
import threading
import time


def check(root: Path) -> dict:
    executable = shutil.which("codex")
    if not executable:
        raise RuntimeError("Codex executable unavailable")
    responses = queue.Queue()
    process = subprocess.Popen([executable, "app-server", "--strict-config", "--stdio"],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, encoding="utf-8", cwd=root)

    def read_responses():
        for line in process.stdout:
            try:
                responses.put(json.loads(line))
            except json.JSONDecodeError:
                pass

    def drain_diagnostics():
        # Do not publish local MCP environment or account details.
        for _ in process.stderr:
            pass

    threading.Thread(target=read_responses, daemon=True).start()
    threading.Thread(target=drain_diagnostics, daemon=True).start()

    def send(value):
        process.stdin.write(json.dumps(value) + "\n")
        process.stdin.flush()

    def response(identifier):
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            item = responses.get(timeout=max(0.1, deadline - time.monotonic()))
            if item.get("id") == identifier:
                return item
        raise TimeoutError(identifier)

    report = {"schema": "oma.research.effective-configuration/1", "recorded_utc": datetime.now(timezone.utc).isoformat(),
              "thread_started": False, "model_turn_started": False, "configuration_verified": False,
              "actual_coordinator_identity_attested": False, "worker_capacity_attested": False,
              "notice": "Fresh disk configuration only; the active conversation must separately attest its real model and worker capacity."}
    try:
        send({"id": 1, "method": "initialize", "params": {"clientInfo": {"name": "oma_preflight", "title": "OMA research preflight", "version": "1.0"}}})
        if "result" not in response(1):
            raise RuntimeError("Initialization rejected")
        send({"method": "initialized", "params": {}})
        send({"id": 2, "method": "config/read", "params": {"cwd": str(root), "includeLayers": False}})
        answer = response(2)
        if "result" not in answer:
            report["configuration_error_code"] = answer.get("error", {}).get("code")
        else:
            config = answer["result"]["config"]
            agent_fields = ("enabled", "max_concurrent_threads_per_session", "default_subagent_model", "default_subagent_reasoning_effort")
            agents = {k: config.get("agents", {}).get(k) for k in agent_fields}
            report["effective_disk_configuration"] = {"model": config.get("model"), "model_reasoning_effort": config.get("model_reasoning_effort"), "agents": agents}
            report["configuration_verified"] = report["effective_disk_configuration"] == {
                "model": "gpt-6-astra", "model_reasoning_effort": "max", "agents": {
                    "enabled": True, "max_concurrent_threads_per_session": 100,
                    "default_subagent_model": "gpt-6.1-sol", "default_subagent_reasoning_effort": "max"}}
        send({"id": 3, "method": "account/rateLimits/read", "params": {}})
        answer = response(3)
        report["account_rate_limits_read_ok"] = "result" in answer
        if "result" in answer:
            report["quota_windows_present"] = bool(answer["result"].get("rateLimits") or answer["result"].get("rateLimitsByLimitId"))
            report["account_worker_concurrency"] = "NOT_EXPOSED_BY_RATE_LIMIT_API"
        else:
            report["account_read_error_code"] = answer.get("error", {}).get("code")
    except Exception as error:
        report["preflight_error"] = type(error).__name__
    finally:
        process.stdin.close()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.terminate()
            process.wait(timeout=5)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = args.output.resolve()
    if (root / "evidence/research").resolve() not in output.parents or output.exists():
        parser.error("Use a fresh file under evidence/research; prior evidence is not overwritten")
    result = check(root)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2)
        handle.write("\n")
    print(json.dumps(result, indent=2))
    return 0 if result["configuration_verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
