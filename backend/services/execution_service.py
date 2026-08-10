"""
services/execution_service.py
Sandboxed multi-file project execution service.
Executes team-submitted code in an isolated Docker container or resource-limited subprocess sandbox.
"""

import logging
import os
import shlex
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Dict, Any, Optional

from utils.file_validation import validate_challenge_filename, FileValidationError

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 15
MAX_OUTPUT_CHARS = 50_000


_DOCKER_AVAILABLE_CACHE = None


def is_docker_available() -> bool:
    """Check if Docker daemon is installed and accessible (cached)."""
    global _DOCKER_AVAILABLE_CACHE
    if _DOCKER_AVAILABLE_CACHE is not None:
        return _DOCKER_AVAILABLE_CACHE

    docker_bin = shutil.which("docker")
    if not docker_bin:
        _DOCKER_AVAILABLE_CACHE = False
        return False
    try:
        res = subprocess.run(
            [docker_bin, "info"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=1,
        )
        _DOCKER_AVAILABLE_CACHE = (res.returncode == 0)
    except Exception:
        _DOCKER_AVAILABLE_CACHE = False
    return _DOCKER_AVAILABLE_CACHE



def run_submission_code(
    files: Dict[str, str],
    run_command: Optional[str] = None,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> Dict[str, Any]:
    """
    Assemble the full set of submission files in a temporary project directory
    and execute the project's test/entry command in a sandboxed environment.

    Args:
        files: Mapping of filename -> file content string.
        run_command: Command string to run (e.g. "pytest", "python main.py").
        timeout_seconds: Hard wall-clock timeout in seconds.

    Returns:
        Structured result dict:
        {"passed": bool, "exit_code": int, "stdout": str, "stderr": str, "duration_ms": int}
    """
    if not run_command or not run_command.strip():
        run_command = "pytest"

    cmd_str = run_command.strip()
    start_time = time.time()

    with tempfile.TemporaryDirectory(prefix="submission_exec_") as tmp_dir_str:
        tmp_dir = Path(tmp_dir_str)

        # 1. Assemble files safely
        for filename, content in files.items():
            try:
                safe_name = validate_challenge_filename(filename)
            except FileValidationError as e:
                duration_ms = int((time.time() - start_time) * 1000)
                return {
                    "passed": False,
                    "exit_code": -1,
                    "stdout": "",
                    "stderr": f"Security validation error on file '{filename}': {str(e)}",
                    "duration_ms": duration_ms,
                }
            file_path = tmp_dir / safe_name
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content or "", encoding="utf-8")

        # 2. Run in Docker sandbox if available
        if is_docker_available():
            try:
                docker_cmd = [
                    "docker", "run", "--rm",
                    "--net=none",
                    "--read-only",
                    "--tmpfs", "/tmp:rw,exec,nosuid,size=64m",
                    "--memory=256m",
                    "--cpus=1.0",
                    "--pids-limit=64",
                    "-v", f"{str(tmp_dir.resolve())}:/workspace:ro",
                    "-w", "/workspace",
                    "python:3.11-slim",
                    "sh", "-c", cmd_str,
                ]
                proc = subprocess.run(
                    docker_cmd,
                    capture_output=True,
                    text=True,
                    timeout=timeout_seconds,
                )
                duration_ms = int((time.time() - start_time) * 1000)
                passed = proc.returncode == 0
                return {
                    "passed": passed,
                    "exit_code": proc.returncode,
                    "stdout": proc.stdout or "",
                    "stderr": proc.stderr or "",
                    "duration_ms": duration_ms,
                }
            except subprocess.TimeoutExpired:
                duration_ms = int((time.time() - start_time) * 1000)
                return {
                    "passed": False,
                    "exit_code": -1,
                    "stdout": "",
                    "stderr": f"Execution timed out after {timeout_seconds} seconds.",
                    "duration_ms": duration_ms,
                }
            except Exception as e:
                logger.warning(f"Docker execution failed, falling back to subprocess sandbox: {e}")

        # 3. Subprocess Sandbox Fallback
        clean_env = {
            "PATH": os.environ.get("PATH", ""),
            "PYTHONPATH": str(tmp_dir),
            "PYTHONUNBUFFERED": "1",
            "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
            "WINDIR": os.environ.get("WINDIR", ""),
        }

        # Use shlex to safely split command arguments
        try:
            cmd_args = shlex.split(cmd_str, posix=(os.name != "nt"))
        except Exception:
            cmd_args = cmd_str.split()

        try:
            # Pre-execution setup for POSIX resource limits if on Unix
            preexec_fn = None
            if os.name != "nt":
                try:
                    import resource

                    def limit_resources():
                        # CPU time limit in seconds
                        resource.setrlimit(resource.RLIMIT_CPU, (timeout_seconds, timeout_seconds))
                        # Address space limit — tightened from 512MB to 256MB to match
                        # the Docker path's --memory=256m for consistent behavior
                        # regardless of which execution path actually runs.
                        mem_limit = 256 * 1024 * 1024
                        resource.setrlimit(resource.RLIMIT_AS, (mem_limit, mem_limit))
                        # NEW: cap the number of processes/threads this can spawn,
                        # preventing a fork bomb from exhausting server resources.
                        resource.setrlimit(resource.RLIMIT_NPROC, (32, 32))
                        # NEW: cap open file descriptors, preventing resource
                        # exhaustion via opening many files/sockets.
                        resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
                        # NEW: cap the size of any single file the submission writes,
                        # preventing disk-fill via a runaway write loop.
                        max_file_size = 10 * 1024 * 1024  # 10 MB
                        resource.setrlimit(resource.RLIMIT_FSIZE, (max_file_size, max_file_size))

                    preexec_fn = limit_resources
                except Exception:
                    pass
            else:
                # On Windows, resource.setrlimit is unavailable.
                # Windows relies on the wall-clock timeout (timeout=timeout_seconds on subprocess.run)
                # as the primary safety net. CPU and memory limits via rlimit are POSIX-only enhancements.
                pass

            proc = subprocess.run(
                cmd_args,
                cwd=str(tmp_dir),
                env=clean_env,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                preexec_fn=preexec_fn,
            )
            duration_ms = int((time.time() - start_time) * 1000)
            passed = proc.returncode == 0

            def _truncate(text: str) -> str:
                if len(text) > MAX_OUTPUT_CHARS:
                    return text[:MAX_OUTPUT_CHARS] + "\n\n[... output truncated ...]"
                return text

            stdout = _truncate(proc.stdout or "")
            stderr = _truncate(proc.stderr or "")

            return {
                "passed": passed,
                "exit_code": proc.returncode,
                "stdout": stdout,
                "stderr": stderr,
                "duration_ms": duration_ms,
            }
        except subprocess.TimeoutExpired:
            duration_ms = int((time.time() - start_time) * 1000)
            return {
                "passed": False,
                "exit_code": -1,
                "stdout": "",
                "stderr": f"Execution timed out after {timeout_seconds} seconds.",
                "duration_ms": duration_ms,
            }
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            return {
                "passed": False,
                "exit_code": -1,
                "stdout": "",
                "stderr": f"Execution error: {str(e)}",
                "duration_ms": duration_ms,
            }
