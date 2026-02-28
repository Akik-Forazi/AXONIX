"""
This module provides a secure interface for executing operating system commands.
It is specifically designed to be cross-platform aware, with special handling for 
Windows command environments to ensure seamless interaction for the user.
"""

import subprocess
import sys
import io
import os
import platform
import contextlib
import traceback

# Detecting the host operating system to adjust command interpretation.
IS_WINDOWS = platform.system() == "Windows"


class ShellTools:
    """
    Manages shell-level interactions, allowing AXONIX-ZERO to run system utilities,
    scripts, and Python snippets directly.
    """
    def __init__(self, workspace: str = "."):
        self.workspace = os.path.abspath(workspace)

    def run(self, command: str, timeout: int = 30) -> str:
        """
        Executes a shell command and returns the results.
        Automatically suggests Windows equivalents if common Unix commands are used.
        """
        if IS_WINDOWS:
            # Helpful mapping to assist users transitioning from Unix environments.
            unix_cmds = {
                "ls": "dir", "cat": "type", "rm": "del", 
                "cp": "copy", "mv": "move", "grep": "findstr", 
                "touch": "echo.>"
            }
            first_word = command.strip().split()[0] if command.strip() else ""
            if first_word in unix_cmds:
                win_equiv = unix_cmds[first_word]
                return (
                    f"Notice: '{first_word}' is a Unix command. Using Windows '{win_equiv}' instead.\n"
                    f"Running command: {win_equiv}\n"
                ) + self._run_raw(command.replace(first_word, win_equiv, 1), timeout)

        return self._run_raw(command, timeout)

    def _run_raw(self, command: str, timeout: int = 30) -> str:
        """
        Internal method to handle the low-level process execution and output capture.
        """
        try:
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

            # Formatting the execution report for clarity.
            parts = [f"Command Execution: {command}", f"Exit Status: {code}"]
            if out: parts.append(f"Standard Output:\n{out}")
            if err: parts.append(f"Standard Error:\n{err}")
            if not out and not err:
                parts.append("(No output recorded)")
            return "\n".join(parts)

        except subprocess.TimeoutExpired:
            return f"Error: Command timed out after {timeout} seconds."
        except Exception as e:
            return f"Error: Shell execution failed. {e}"

    def run_python(self, code: str) -> str:
        """
        Safely executes a Python snippet within the current process context
        and captures any output or errors generated.
        """
        out_buf = io.StringIO()
        err_buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(out_buf), contextlib.redirect_stderr(err_buf):
                # Using compile ensures we catch syntax errors early.
                exec(compile(code, "<axonix-runtime>", "exec"), {})
            
            out = out_buf.getvalue()
            err = err_buf.getvalue()
            
            parts = [f"Python Execution Report ({len(code)} characters executed)"]
            if out: parts.append(f"Output:\n{out}")
            if err: parts.append(f"Errors/Warnings:\n{err}")
            if not out and not err: parts.append("(Code executed successfully with no output)")
            return "\n".join(parts)
        except Exception:
            return f"Python Runtime Error:\n{traceback.format_exc()}"
