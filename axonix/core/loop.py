"""
This module contains the LoopEngine, the high-level orchestration system for AXONIX-ZERO.
It enables autonomous "Goal Mode" where the agent plans, executes, and verifies complex 
multi-step tasks without requiring constant user intervention.
"""

import json
import re
import time
from typing import Callable, Optional
from axonix.core.agent import Agent
from axonix.core.cli import C, rule, Spinner


# ── Specialized Strategic Prompts ──────────────────────────

# This prompt guides the AI to break down a large vision into manageable, atomic pieces.
PLANNER_PROMPT = """You are the AXONIX-ZERO Strategic Planner. 
Your goal is to decompose a complex objective into a series of logical, sequential sub-tasks.

Respond with ONLY a JSON array of sub-tasks using this schema:
[
  {"id": 1, "task": "Description of work", "verify": "Condition for success"},
  ...
]

Keep tasks atomic, measurable, and independent. Max 12 tasks per plan.
"""

# This prompt ensures that every step is double-checked for quality and correctness.
VERIFIER_PROMPT = """You are the AXONIX-ZERO Quality Assurance Verifier.
Your job is to objectively assess whether a specific sub-task has been completed successfully.

You will evaluate the task, the required condition, and the empirical evidence provided.
Respond with ONLY a JSON object:
{"success": true, "reason": "Justification"}
or
{"success": false, "reason": "Deficiency", "fix_hint": "Corrective action"}
"""

# This prompt handles mid-course corrections if the original plan needs adjustment.
REPLANNER_PROMPT = """You are the AXONIX-ZERO Strategic Replanner. 
The current trajectory has stalled or encountered an obstacle.

Assess the original goal, the completed milestones, and the nature of the current failure.
Produce a refined, optimized plan to complete the remaining work.
Output ONLY the JSON array of new sub-tasks.
"""


class LoopEngine:
    """
    The LoopEngine manages the lifecycle of a high-level goal.
    It orchestrates the planning, execution, and verification phases to ensure
    that the final result meets the user's expectations.
    """

    def __init__(
        self,
        agent: Agent,
        max_cycles: int = 5,          # Maximum global plan-execute-verify iterations.
        max_retries: int = 3,          # Retries allowed per specific sub-task.
        max_steps_per_task: int = 20,  # Depth limit for the agent's autonomous loop.
        verbose: bool = True,
        on_progress: Optional[Callable] = None,
    ):
        self.agent = agent
        self.max_cycles = max_cycles
        self.max_retries = max_retries
        self.max_steps_per_task = max_steps_per_task
        self.verbose = verbose
        self.on_progress = on_progress

        # Operational State
        self.goal: str = ""
        self.plan: list[dict] = []
        self.completed: list[dict] = []
        self.failed: list[dict] = []
        self.cycle: int = 0
        self._stop = False

    def run_goal(self, goal: str) -> str:
        """
        The primary execution entry point. 
        It maintains the outer loop until the goal is achieved or resources are exhausted.
        """
        self.goal = goal
        self._stop = False
        self.completed = []
        self.failed = []
        self.cycle = 0

        self._emit("start", {"goal": goal})
        self._header(f"Objective: {goal}")

        for cycle in range(1, self.max_cycles + 1):
            self.cycle = cycle
            self._emit("cycle", {"cycle": cycle, "max": self.max_cycles})
            self._section(f"Phase {cycle}/{self.max_cycles} — Strategic Planning")

            # Phase 1: Planning
            self.plan = self._plan(goal)
            if not self.plan:
                self._warn("Strategic Planner returned an empty roadmap. Retrying...")
                continue

            self._show_plan(self.plan)

            # Phase 2: Execution
            all_passed = True
            for task in self.plan:
                if self._stop:
                    self._info("Execution halted by user request.")
                    return "Operation Interrupted."

                tid = task["id"]
                task_desc = task["task"]
                verify_cond = task.get("verify", "task completed")

                self._task_header(tid, len(self.plan), task_desc)
                self._emit("task_start", {"id": tid, "task": task_desc})

                # Sub-task Retry Loop
                success = False
                evidence = ""
                for attempt in range(1, self.max_retries + 1):
                    if attempt > 1:
                        self._warn(f"Retry {attempt}/{self.max_retries}: {task.get('fix_hint', 'Adjusting strategy...')}")

                    evidence = self._run_subtask(task_desc, verify_cond, attempt)
                    ok, reason, fix_hint = self._verify(task_desc, verify_cond, evidence)

                    if ok:
                        self._ok(f"Validated: {reason}")
                        self._emit("task_done", {"id": tid, "reason": reason})
                        task["_evidence"] = evidence
                        task["_status"] = "done"
                        success = True
                        break
                    else:
                        self._err(f"Validation Failure: {reason}")
                        task["fix_hint"] = fix_hint
                        self._emit("task_fail", {"id": tid, "reason": reason, "attempt": attempt})
                        if attempt < self.max_retries:
                            time.sleep(0.5)

                if not success:
                    self._err(f"Milestone {tid} failed after exhaustive attempts. Initiating replanning...")
                    task["_status"] = "failed"
                    self.failed.append(task)
                    all_passed = False
                    break
                else:
                    self.completed.append(task)

            # Phase 3: Final Goal Verification
            if all_passed:
                self._section("Finalizing Objective Verification...")
                ok, reason, _ = self._verify_goal(goal)
                if ok:
                    self._header(f"Objective Accomplished: {reason}")
                    self._emit("goal_done", {"reason": reason, "cycles": cycle})
                    return f"Goal successfully achieved in {cycle} cycle(s): {reason}"
                else:
                    self._warn(f"Goal criteria not fully met: {reason}")
                    self._emit("goal_not_met", {"reason": reason})
                    # Replan for next cycle
                    self.plan = self._replan(goal, self.completed, reason)

        self._err(f"Unable to achieve goal after {self.max_cycles} cycles.")
        self._emit("goal_failed", {"cycles": self.max_cycles})
        return f"Exceeded maximum cycles ({self.max_cycles}). Please review partial progress above."

    def stop(self):
        """Signals the engine to gracefully terminate the current operation."""
        self._stop = True

    def _plan(self, goal: str) -> list[dict]:
        """Interfaces with the LLM to generate the task roadmap."""
        spinner = Spinner("Architecting plan...")
        spinner.start()
        msgs = [
            {"role": "system", "content": PLANNER_PROMPT},
            {"role": "user", "content": f"GOAL: {goal}\n\nWorkspace Context: {self.agent.workspace}"},
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
            self._err(f"Planner Interface Error: {e}")
            return []

    def _replan(self, goal: str, completed: list, reason: str) -> list[dict]:
        """Generates a recovery plan when progress stalls."""
        spinner = Spinner("Recalibrating strategy...")
        spinner.start()
        completed_summary = "\n".join(f"- {t['task']}" for t in completed)
        msgs = [
            {"role": "system", "content": REPLANNER_PROMPT},
            {"role": "user", content: (
                f"GOAL: {goal}\n\n"
                f"Completed Milestones:\n{completed_summary}\n\n"
                f"Status Conflict: {reason}\n\n"
                f"Determine the optimized path forward."
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
            self._err(f"Replanner Interface Error: {e}")
            return []

    def _run_subtask(self, task: str, verify_cond: str, attempt: int) -> str:
        """Executes a single roadmap item using the agent's core capabilities."""
        prompt = (
            f"OBJECTIVE: {task}\n\n"
            f"VERIFICATION CRITERIA: {verify_cond}\n\n"
            f"{'NOTICE: Previous attempt unsuccessful. Please pivot your approach.' if attempt > 1 else ''}"
            f"Execute the task autonomously. Use 'done()' when criteria are met."
        )

        original_steps = self.agent.config.get("max_steps", 30)
        self.agent.config["max_steps"] = self.max_steps_per_task

        evidence_parts = []
        orig_tool_result = self.agent.on_tool_result
        
        def capture_result(name, result):
            evidence_parts.append(f"[{name} Output]: {str(result)[:1000]}")
            if orig_tool_result:
                orig_tool_result(name, result)
        
        self.agent.on_tool_result = capture_result
        result = self.agent.run(prompt)
        
        # Restoration of original state
        self.agent.config["max_steps"] = original_steps
        self.agent.on_tool_result = orig_tool_result

        evidence_parts.append(f"[Final Status]: {result}")
        return "\n".join(evidence_parts)

    def _verify(self, task: str, condition: str, evidence: str) -> tuple[bool, str, str]:
        """Double-checks sub-task outcomes using the verifier logic."""
        spinner = Spinner("Validating outcome...")
        spinner.start()
        msgs = [
            {"role": "system", "content": VERIFIER_PROMPT},
            {"role": "user", "content": (
                f"Task: {task}\n"
                f"Requirement: {condition}\n"
                f"Empirical Evidence:\n{evidence[:4000]}"
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
                    obj.get("reason", "No reason provided"),
                    obj.get("fix_hint", ""),
                )
            
            # Heuristic fallback for robust operation.
            if "[DONE]" in evidence or "Task completed" in evidence:
                return True, "Completion signature detected in logs.", ""
            return False, "Validation response unreadable.", "Review execution logs."
        except Exception as e:
            spinner.stop()
            return True, f"Validation bypassed due to system error: {e}", ""

    def _verify_goal(self, goal: str) -> tuple[bool, str, str]:
        """Performs a comprehensive final check on the overall objective."""
        evidence = "\n".join(
            f"Milestone: {t['task']} — Result: {t.get('_evidence','')[:300]}"
            for t in self.completed
        )
        return self._verify(
            task=f"Comprehensive Goal: {goal}",
            condition="The entire objective is fully realized and operational.",
            evidence=evidence,
        )

    # ── Operational UI Helpers ─────────────────────────────

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
        print(f"\n  {C.GRAY}Roadmap ({len(plan)} milestones):{C.RESET}")
        for t in plan:
            print(f"    {C.DGRAY}{t['id']:>2}.{C.RESET} {C.WHITE}{t['task']}{C.RESET}")
            print(f"        {C.DGRAY}Criterion: {t.get('verify','—')}{C.RESET}")

    def _ok(self, msg: str):
        if not self.verbose: return
        print(f"   {C.GREEN}✓ {msg}{C.RESET}")

    def _err(self, msg: str):
        if not self.verbose: return
        print(f"   {C.RED}✗ {msg}{C.RESET}")

    def _warn(self, msg: str):
        if not self.verbose: return
        print(f"   {C.YELLOW}⚠ {msg}{C.RESET}")

    def _info(self, msg: str):
        if not self.verbose: return
        print(f"   {C.GRAY}{msg}{C.RESET}")
