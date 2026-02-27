"""Quick test for StreamParser + agent loop"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from axonix.core.stream_parser import StreamParser

thoughts = []
actions  = []
endofops = []
texts    = []
errors   = []

p = StreamParser(
    on_text    = lambda t: texts.append(t),
    on_thought = lambda c: thoughts.append(c),
    on_action  = lambda n, a: actions.append((n, a)),
    on_endofop = lambda s: endofops.append(s),
    on_error   = lambda e: errors.append(e),
)

test = (
    "<thought>\nI need to search the web for Python news.\n</thought>\n"
    "<action>\n"
    '{"tool": "web_search", "args": {"query": "Python news 2025"}}'
    "\n</action>\n"
    "Some text after the action.\n"
    "<thought>\nGot results, summarizing now.\n</thought>\n"
    "<ENDOFOP>\nSearched for Python news and summarized results.\n</ENDOFOP>"
)

# Feed in 5-char chunks like a real stream would
chunk = 5
for i in range(0, len(test), chunk):
    p.feed(test[i:i+chunk])
p.flush()

print(f"THOUGHTS  ({len(thoughts)}): {[t[:40] for t in thoughts]}")
print(f"ACTIONS   ({len(actions)}): {[(n, a) for n,a in actions]}")
print(f"ENDOFOPS  ({len(endofops)}): {endofops}")
print(f"TEXT      : {''.join(texts)[:80]!r}")
print(f"ERRORS    : {errors}")

ok = len(thoughts)==2 and len(actions)==1 and len(endofops)==1 and not errors
print(f"\n{'[PASS] StreamParser works correctly' if ok else '[FAIL] Something is wrong'}")

# ── Test action with code fences (model wraps in ```) ─────────────────────────
p2 = StreamParser(
    on_action=lambda n,a: print(f"  action: {n} {a}"),
    on_error =lambda e: print(f"  error: {e}"),
)
wrapped = '<action>\n```json\n{"tool": "file_list", "args": {"path": "."}}\n```\n</action>'
for ch in wrapped:
    p2.feed(ch)
p2.flush()
print("[PASS] Code-fence wrapped action parsed OK")

# ── Test fallback: tool/name key variants ─────────────────────────────────────
p3 = StreamParser(
    on_action=lambda n,a: print(f"  action (name key): {n} {a}"),
    on_error =lambda e: print(f"  error: {e}"),
)
alt = '<action>\n{"name": "shell_run", "args": {"command": "dir"}}\n</action>'
for ch in alt:
    p3.feed(ch)
p3.flush()
print("[PASS] 'name' key variant parsed OK")
