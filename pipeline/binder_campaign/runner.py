"""Execute a bounded task; resume only if inputs and validated outputs match."""
import hashlib
import csv
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import time


def digest(path):
    h = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    temporary.replace(path)


def validate_output(path, spec):
    path = Path(path)
    if not path.is_file() or path.stat().st_size == 0:
        raise ValueError("Missing or empty output: " + str(path))
    if spec.get("kind") == "metrics_json":
        data = json.loads(path.read_text())
        for key in spec["finite_keys"]:
            value = data[key]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError("Nonfinite/non-numeric metric: " + key)
    elif spec.get("kind") == "json":
        json.loads(path.read_text())
    elif spec.get("kind") == "csv":
        with path.open(newline="") as stream:
            reader = csv.DictReader(stream)
            if not reader.fieldnames or not set(spec.get("columns", [])) <= set(reader.fieldnames):
                raise ValueError("CSV missing required columns: " + str(path))
            rows = list(reader)
            if len(rows) < spec.get("min_rows", 1):
                raise ValueError("CSV has insufficient result rows: " + str(path))
    elif spec.get("kind") not in (None, "file"):
        raise ValueError("Unknown validator: " + spec["kind"])
    return digest(path)


def run_task(spec_path):
    spec_path = Path(spec_path).resolve()
    spec = json.loads(spec_path.read_text())
    cwd = Path(spec["cwd"]).resolve()
    if not cwd.is_dir():
        raise ValueError("Task cwd does not exist")
    command = spec["command"]
    if not command or not all(isinstance(x, str) for x in command):
        raise ValueError("Command must be a nonempty argv list")
    timeout = spec["timeout_seconds"]
    if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or not 0 < timeout <= 28800:
        raise ValueError("Explicit timeout must be >0 and <=8 hours")
    if not spec.get("inputs") or not spec.get("outputs") or not spec.get("revision"):
        raise ValueError("Inputs, outputs and tool revision are required")
    paths = lambda p: (cwd / p).resolve()
    inputs = {str(paths(p)): digest(paths(p)) for p in spec["inputs"]}
    fingerprint = hashlib.sha256(json.dumps({"spec": spec, "inputs": inputs}, sort_keys=True).encode()).hexdigest()
    state = paths(spec["state"])
    state.parent.mkdir(parents=True, exist_ok=True)
    lock = state.with_name(state.name + ".lock")
    try:
        fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise ValueError("Task lock exists; inspect the prior process before recovery: " + str(lock))
    os.write(fd, str(os.getpid()).encode())
    os.close(fd)
    try:
        prior = None
        if state.exists():
            prior = json.loads(state.read_text())
            if prior.get("fingerprint") != fingerprint:
                raise ValueError("Inputs/settings changed; use a new task directory")
            if prior.get("status") == "success":
                current = {str(paths(o["path"])): validate_output(paths(o["path"]), o) for o in spec["outputs"]}
                if prior.get("fingerprint") == fingerprint and prior.get("outputs") == current:
                    return {**prior, "resumed": True}
                raise ValueError("Inputs/settings/outputs changed; use a new task directory")
            if prior.get("status") != "failed":
                raise ValueError("Prior attempt is not marked failed; inspect before recovery")
        partial = {str(paths(o["path"])): digest(paths(o["path"])) if paths(o["path"]).is_file() else None for o in spec["outputs"]}
        if any(paths(o["path"]).exists() for o in spec["outputs"]):
            if not (prior and spec.get("native_resume") is True and prior.get("partial_outputs") == partial):
                raise ValueError("Unverified outputs already exist or changed; recover explicitly or use a new directory")
        attempt = prior.get("attempt", 1) + 1 if prior else 1
        if prior:
            write_json(state.parent / (state.stem+"-attempts") / (str(attempt-1)+".json"), prior)
        log_path = paths(spec["log"])
        log_path.parent.mkdir(parents=True, exist_ok=True)
        started = time.time()
        record = {"status":"running", "attempt":attempt, "fingerprint":fingerprint, "inputs":inputs,
                  "command":command, "revision":spec["revision"], "started_unix":started}
        write_json(state, record)
        process = None
        previous_handlers = {}
        def terminate(signum, _frame):
            raise InterruptedError("Task interrupted by signal " + str(signum))
        def send_to_child_group(sig):
            try:
                os.killpg(process.pid, sig)
            except ProcessLookupError:
                pass
            except PermissionError:
                # Some local execution environments disallow process-group signals.
                # The direct child is still ours; cluster Linux uses the group path.
                try:
                    process.send_signal(sig)
                except ProcessLookupError:
                    pass
        try:
            for sig in (signal.SIGTERM, signal.SIGINT):
                previous_handlers[sig] = signal.signal(sig, terminate)
            with log_path.open("a") as log:
                process = subprocess.Popen(command, cwd=str(cwd), stdout=log, stderr=subprocess.STDOUT,
                                           env={**os.environ, **spec.get("env", {})}, start_new_session=True)
                record["pid"] = process.pid
                write_json(state, record)
                result = process.wait(timeout=timeout)
            record["exit_code"] = result
            if result:
                raise RuntimeError("Subprocess exit status " + str(result))
            record["outputs"] = {str(paths(o["path"])): validate_output(paths(o["path"]), o) for o in spec["outputs"]}
            record["status"] = "success"
        except BaseException as exc:
            record["status"] = "failed"
            record["error"] = type(exc).__name__ + ": " + str(exc)
            if process is not None and process.poll() is None:
                send_to_child_group(signal.SIGTERM)
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    send_to_child_group(signal.SIGKILL)
                    process.wait()
            raise
        finally:
            for sig, handler in previous_handlers.items():
                signal.signal(sig, handler)
            record["elapsed_seconds"] = time.time() - started
            if record["status"] == "failed":
                record["partial_outputs"] = {str(paths(o["path"])): digest(paths(o["path"])) if paths(o["path"]).is_file() else None for o in spec["outputs"]}
            write_json(state, record)
        return record
    finally:
        lock.unlink()
