"""
Shell Tools — Windows-aware, runs CMD not bash
"""

import subprocess
import sys
import io
import os
import platform
import contextlib
import traceback

IS_WINDOWS = platform.system() == "Windows"


class ShellTools:
    def __init__(self, workspace: str = "."):
        self.workspace = os.path.abspath(workspace)

    def run(self, command: str, timeout: int = 30) -> str:
        """Run a shell command. Uses CMD on Windows, sh on Unix."""
        # Reject unix-only commands on Windows with helpful hint
        if IS_WINDOWS:
            unix_cmds = {"ls": "dir", "cat": "type", "rm": "del", "cp": "copy", "mv": "move", "grep": "findstr", "touch": "echo.>"}
            first_word = command.strip().split()[0] if command.strip() else ""
            if first_word in unix_cmds:
                win_equiv = unix_cmds[first_word]
                return (
                    f"[SHELL] '{first_word}' is not available on Windows.\n"
                    f"Use '{win_equiv}' instead, or use file_read/file_list tools.\n"
                    f"Retrying with Windows equivalent…\n"
                ) + self._run_raw(command.replace(first_word, win_equiv, 1), timeout)

        return self._run_raw(command, timeout)

    def _run_raw(self, command: str, timeout: int = 30) -> str:
        try:
            if IS_WINDOWS:
                result = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    cwd=self.workspace,
                    executable=None,  # use cmd.exe via shell=True
                )
            else:
                result = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    cwd=self.workspace,
                )

            out  = result.stdout.strip()
            err  = result.stderr.strip()
            code = result.returncode

            parts = [f"[SHELL] $ {command}", f"[exit: {code}]"]
            if out:  parts.append(f"[stdout]\n{out}")
            if err:  parts.append(f"[stderr]\n{err}")
            if not out and not err:
                parts.append("[no output]")
            return "\n".join(parts)

        except subprocess.TimeoutExpired:
            return f"[ERROR] Timed out after {timeout}s: {command}"
        except Exception as e:
            return f"[ERROR] Shell error: {e}"

    def run_python(self, code: str) -> str:
        """Execute Python code in-process and capture output."""
        out_buf = io.StringIO()
        err_buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(out_buf), contextlib.redirect_stderr(err_buf):
                exec(compile(code, "<axonix>", "exec"), {})
            out = out_buf.getvalue()
            err = err_buf.getvalue()
            parts = [f"[PYTHON] Executed {len(code)} chars"]
            if out: parts.append(f"[output]\n{out}")
            if err: parts.append(f"[stderr]\n{err}")
            if not out and not err: parts.append("[no output]")
            return "\n".join(parts)
        except Exception:
            return f"[PYTHON ERROR]\n{traceback.format_exc()}"
