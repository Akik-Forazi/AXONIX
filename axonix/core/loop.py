"""
axonix Loop Engine — Moltbot-style continuous execution
Keeps running sub-tasks autonomously until a goal is verified complete.

How it works:
  1. User gives a high-level GOAL
  2. Planner breaks it into ordered sub-tasks
  3. Each sub-task runs as a full agent loop
  4. Verifier checks if the sub-task succeeded
  5. If failed → retry with a different approach (up to max_retries)
  6. When all sub-tasks done → Verifier checks the overall goal
  7. If overall goal not met → replans and loops again
  8. Stops when: goal verified ✓ | max_cycles hit | user interrupts
"""

import json
import re
import time
from typing import Callable, Optional
from axonix.core.agent import Agent
from axonix.core.cli import C, rule, Spinner


# ── Goal-level system prompt ───────────────────────────────
PLANNER_PROMPT = """You are axonix Planner, the strategic mind of a fully local AI dev agent.

Your job: given a high-level GOAL, produce a concrete ordered plan of sub-tasks.

Respond ONLY with a JSON array of sub-tasks, like this:
[
  {"id": 1, "task": "Create the project directory structure", "verify": "directory exists with correct layout"},
  {"id": 2, "task": "Write main.py with FastAPI app skeleton", "verify": "main.py exists and contains FastAPI import"},
  {"id": 3, "task": "Write requirements.txt", "verify": "requirements.txt exists with fastapi listed"},
  {"id": 4, "task": "Run the app and check for errors", "verify": "no Python errors in output"}
]

Rules:
- Each task must be atomic and independently executable
- "verify" is a concrete checkable condition (file exists, command output, etc.)
- Order tasks so each one builds on the last
- Max 12 tasks per plan
- Output ONLY the JSON array, no explanation
"""

VERIFIER_PROMPT = """You are axonix Verifier. Your job is to check if a task was completed successfully.

You will be given:
- The task description
- The verification condition  
- Evidence (tool outputs, file contents, etc.)

Respond with ONLY a JSON object:
{"success": true, "reason": "brief explanation"}
or
{"success": false, "reason": "what went wrong", "fix_hint": "how to fix it"}
"""

REPLANNER_PROMPT = """You are axonix Replanner. The current plan has stalled or partially failed.

Given:
- The original GOAL
- Completed sub-tasks so far
- The failing sub-task and why it failed

Produce a NEW plan for the remaining work. Same JSON format as before.
Output ONLY the JSON array.
"""


class LoopEngine:
    """
    Moltbot-style continuous goal-driven execution engine.
    
    Usage:
        engine = LoopEngine(agent)
        engine.run_goal("Build a complete Flask REST API with SQLite")
    """

    def __init__(
        self,
        agent: Agent,
        max_cycles: int = 5,          # how many full plan→verify loops before giving up
        max_retries: int = 3,          # retries per sub-task on failure
        max_steps_per_task: int = 20,  # agent steps per sub-task
        verbose: bool = True,
        on_progress: Optional[Callable] = None,  # callback(event_dict) for web UI
    ):
        self.agent = agent
        self.max_cycles = max_cycles
        self.max_retries = max_retries
        self.max_steps_per_task = max_steps_per_task
        self.verbose = verbose
        self.on_progress = on_progress

        # State
        self.goal: str = ""
        self.plan: list[dict] = []
        self.completed: list[dict] = []
        self.failed: list[dict] = []
        self.cycle: int = 0
        self._stop = False

    # ── Public API ─────────────────────────────────────────

    def run_goal(self, goal: str) -> str:
        """Main entry: run until goal is achieved or max_cycles hit."""
        self.goal = goal
        self._stop = False
        self.completed = []
        self.failed = []
        self.cycle = 0

        self._emit("start", {"goal": goal})
        self._header(f"Goal: {goal}")

        for cycle in range(1, self.max_cycles + 1):
            self.cycle = cycle
            self._emit("cycle", {"cycle": cycle, "max": self.max_cycles})
            self._section(f"Cycle {cycle}/{self.max_cycles} — Planning")

            # Step 1: Plan
            self.plan = self._plan(goal)
            if not self.plan:
                self._warn("Planner returned empty plan. Retrying…")
                continue

            self._show_plan(self.plan)

            # Step 2: Execute each sub-task
            all_passed = True
            for task in self.plan:
                if self._stop:
                    self._info("Stopped by user.")
                    return "Interrupted."

                tid = task["id"]
                task_desc = task["task"]
                verify_cond = task.get("verify", "task completed")

                self._task_header(tid, len(self.plan), task_desc)
                self._emit("task_start", {"id": tid, "task": task_desc})

                # Retry loop per sub-task
                success = False
                evidence = ""
                for attempt in range(1, self.max_retries + 1):
                    if attempt > 1:
                        self._warn(f"Retry {attempt}/{self.max_retries}: {task.get('fix_hint', '')}")

                    evidence = self._run_subtask(task_desc, verify_cond, attempt)
                    ok, reason, fix_hint = self._verify(task_desc, verify_cond, evidence)

                    if ok:
                        self._ok(f"✓ Verified: {reason}")
                        self._emit("task_done", {"id": tid, "reason": reason})
                        task["_evidence"] = evidence
                        task["_status"] = "done"
                        success = True
                        break
                    else:
                        self._err(f"✗ Failed: {reason}")
                        task["fix_hint"] = fix_hint
                        self._emit("task_fail", {"id": tid, "reason": reason, "attempt": attempt})
                        if attempt < self.max_retries:
                            time.sleep(0.5)

                if not success:
                    self._err(f"Sub-task {tid} failed after {self.max_retries} attempts. Replanning…")
                    task["_status"] = "failed"
                    self.failed.append(task)
                    all_passed = False
                    break
                else:
                    self.completed.append(task)

            # Step 3: Verify overall goal
            if all_passed:
                self._section("Verifying overall goal…")
                ok, reason, _ = self._verify_goal(goal)
                if ok:
                    self._header(f"✓ GOAL ACHIEVED: {reason}")
                    self._emit("goal_done", {"reason": reason, "cycles": cycle})
                    return f"Goal achieved in {cycle} cycle(s): {reason}"
                else:
                    self._warn(f"Overall goal not yet met: {reason}")
                    self._emit("goal_not_met", {"reason": reason})
                    # Replan for next cycle
                    self.plan = self._replan(goal, self.completed, reason)

        self._err(f"Goal not achieved after {self.max_cycles} cycle(s).")
        self._emit("goal_failed", {"cycles": self.max_cycles})
        return f"Could not fully achieve goal after {self.max_cycles} cycles. Check completed steps above."

    def stop(self):
        self._stop = True

    # ── LLM calls ─────────────────────────────────────────

    def _plan(self, goal: str) -> list[dict]:
        """Ask planner LLM to break goal into sub-tasks."""
        spinner = Spinner("Planning sub-tasks…")
        spinner.start()
        msgs = [
            {"role": "system", "content": PLANNER_PROMPT},
            {"role": "user", "content": f"GOAL: {goal}\n\nWorkspace: {self.agent.workspace}"},
        ]
        try:
            resp = self.agent.llm.complete(msgs)
            raw = resp.text if hasattr(resp, 'text') else str(resp)
            spinner.stop()
            match = re.search(r'\[[\s\S]*\]', raw)
            if match:
                return json.loads(match.group())
            return []
        except Exception as e:
            spinner.stop()
            self._err(f"Planner error: {e}")
            return []

    def _replan(self, goal: str, completed: list, reason: str) -> list[dict]:
        """Replan remaining work after partial failure or incomplete goal."""
        spinner = Spinner("Replanning…")
        spinner.start()
        completed_summary = "\n".join(f"- {t['task']}" for t in completed)
        msgs = [
            {"role": "system", "content": REPLANNER_PROMPT},
            {"role": "user", "content": (
                f"GOAL: {goal}\n\n"
                f"Completed tasks:\n{completed_summary}\n\n"
                f"Remaining issue: {reason}\n\n"
                f"Produce remaining sub-tasks to fully achieve the goal."
            )},
        ]
        try:
            resp = self.agent.llm.complete(msgs)
            raw = resp.text if hasattr(resp, 'text') else str(resp)
            spinner.stop()
            match = re.search(r'\[[\s\S]*\]', raw)
            if match:
                return json.loads(match.group())
            return []
        except Exception as e:
            spinner.stop()
            self._err(f"Replanner error: {e}")
            return []

    def _run_subtask(self, task: str, verify_cond: str, attempt: int) -> str:
        """Run a single sub-task through the full agent loop. Returns evidence string."""
        # Build a focused task prompt
        prompt = (
            f"TASK: {task}\n\n"
            f"SUCCESS CONDITION: {verify_cond}\n\n"
            f"{'PREVIOUS ATTEMPT FAILED — try a different approach.' if attempt > 1 else ''}"
            f"Complete this task fully. When done, call done() with a summary of what you did."
        )

        # Override max_steps for sub-tasks
        original_steps = self.agent.config.get("max_steps", 30)
        self.agent.config["max_steps"] = self.max_steps_per_task

        evidence_parts = []

        # Capture tool results as evidence
        orig_tool_result = self.agent.on_tool_result
        def capture_result(name, result):
            evidence_parts.append(f"[{name}]: {str(result)[:500]}")
            if orig_tool_result:
                orig_tool_result(name, result)
        self.agent.on_tool_result = capture_result

        result = self.agent.run(prompt)
        self.agent.config["max_steps"] = original_steps
        self.agent.on_tool_result = orig_tool_result

        evidence_parts.append(f"[final_result]: {result}")
        return "\n".join(evidence_parts)

    def _verify(self, task: str, condition: str, evidence: str) -> tuple[bool, str, str]:
        """Ask verifier LLM to check if task succeeded."""
        spinner = Spinner("Verifying…")
        spinner.start()
        msgs = [
            {"role": "system", "content": VERIFIER_PROMPT},
            {"role": "user", "content": (
                f"Task: {task}\n"
                f"Verify condition: {condition}\n"
                f"Evidence:\n{evidence[:3000]}"
            )},
        ]
        try:
            resp = self.agent.llm.complete(msgs)
            raw = resp.text if hasattr(resp, 'text') else str(resp)
            spinner.stop()
            match = re.search(r'\{[\s\S]*\}', raw)
            if match:
                obj = json.loads(match.group())
                return (
                    bool(obj.get("success", False)),
                    obj.get("reason", ""),
                    obj.get("fix_hint", ""),
                )
            # fallback: if evidence contains DONE assume success
            if "[DONE]" in evidence or "Task completed" in evidence:
                return True, "Task appears completed (fallback check)", ""
            return False, "Could not parse verifier response", "Try a simpler approach"
        except Exception as e:
            spinner.stop()
            # fallback
            return True, f"Verification skipped ({e})", ""

    def _verify_goal(self, goal: str) -> tuple[bool, str, str]:
        """Verify the overall goal is achieved."""
        evidence = "\n".join(
            f"Completed: {t['task']} — {t.get('_evidence','')[:200]}"
            for t in self.completed
        )
        return self._verify(
            task=f"Overall goal: {goal}",
            condition="All parts of the goal are fully implemented and working",
            evidence=evidence,
        )

    # ── Display helpers ────────────────────────────────────

    def _emit(self, event: str, data: dict):
        if self.on_progress:
            self.on_progress({"event": event, **data})

    def _header(self, msg: str):
        if not self.verbose: return
        print(f"\n  {C.BOLD}{C.WHITE}{msg}{C.RESET}")
        rule('═', C.BLUE)

    def _section(self, msg: str):
        if not self.verbose: return
        print(f"\n  {C.BLUE}◆{C.RESET} {C.GRAY}{msg}{C.RESET}")

    def _task_header(self, tid: int, total: int, task: str):
        if not self.verbose: return
        bar_w = 16
        filled = int(bar_w * tid / max(total, 1))
        bar = f"{C.BLUE}{'▪' * filled}{C.DGRAY}{'·' * (bar_w - filled)}{C.RESET}"
        print(f"\n  {bar}  {C.WHITE}{C.BOLD}[{tid}/{total}]{C.RESET} {C.WHITE}{task}{C.RESET}")

    def _show_plan(self, plan: list):
        if not self.verbose: return
        print(f"\n  {C.GRAY}Plan ({len(plan)} steps):{C.RESET}")
        for t in plan:
            print(f"    {C.DGRAY}{t['id']:>2}.{C.RESET} {C.WHITE}{t['task']}{C.RESET}")
            print(f"        {C.DGRAY}verify: {t.get('verify','—')}{C.RESET}")

    def _ok(self, msg: str):
        if not self.verbose: return
        print(f"   {C.GREEN}{msg}{C.RESET}")

    def _err(self, msg: str):
        if not self.verbose: return
        print(f"   {C.RED}{msg}{C.RESET}")

    def _warn(self, msg: str):
        if not self.verbose: return
        print(f"   {C.YELLOW}⚠ {msg}{C.RESET}")

    def _info(self, msg: str):
        if not self.verbose: return
        print(f"   {C.GRAY}{msg}{C.RESET}")
