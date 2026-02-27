"""
Full end-to-end agent test.
Sends a simple task, watches the streaming loop, prints events.
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
os.environ["AXONIX_DEBUG"] = "1"

from axonix.core.agent import Agent

agent = Agent(
    provider="ollama",
    model_name="gemma3-4b",
    base_url="http://localhost:11434",
    temperature=0.2,
    max_tokens=2048,
    max_steps=10,
    workspace=".",
)

thoughts_seen  = []
actions_seen   = []
results_seen   = []
tokens_seen    = []

agent.on_thought     = lambda c: (thoughts_seen.append(c), print(f"\n[THOUGHT] {c[:80]}"))
agent.on_tool_call   = lambda n,a: (actions_seen.append(n), print(f"\n[TOOL CALL] {n} {a}"))
agent.on_tool_result = lambda n,r: (results_seen.append(r), print(f"\n[RESULT] {r[:80]}"))
agent.on_token       = lambda t: (tokens_seen.append(t), print(t, end="", flush=True))

print("="*60)
print("TASK: List the files in the current directory")
print("="*60)

result = agent.run("List the files in the current directory and tell me what you see.")

print("\n" + "="*60)
print(f"FINAL RESULT: {result}")
print(f"Thoughts: {len(thoughts_seen)}, Tool calls: {len(actions_seen)}, Results: {len(results_seen)}")
print("="*60)
