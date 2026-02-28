import sys
import os
import json
from axonix.core.stream_parser import StreamParser

def test_parser():
    print("── Testing StreamParser ──")
    
    events = []
    
    def on_text(t): events.append(("text", t))
    def on_thought(t): events.append(("thought", t))
    def on_action(tool, args): events.append(("action", tool, args))
    def on_endofop(s): events.append(("endofop", s))
    
    p = StreamParser(
        on_text=on_text,
        on_thought=on_thought,
        on_action=on_action,
        on_endofop=on_endofop
    )
    
    # Simulate a messy stream from an LLM
    chunks = [
        "Thinking about ", "it...\n",
        "<thought>\nI need to check", " the files.\n</thought>\n",
        "Okay, checking now.\n",
        "<action>\n{",
        '"tool": "file_list", ', 
        '"args": {"path": "."},', # trailing comma!
        "}\n</action>\n",
        "Done checking.\n",
        "<ENDOFOP>All files listed.</ENDOFOP>"
    ]
    
    print("Feeding chunks...")
    for c in chunks:
        p.feed(c)
    p.flush()
    
    print(f"\nEvents detected: {len(events)}")
    for e in events:
        print(f"  {e}")
        
    # Validation
    assert ("thought", "I need to check the files.") in events
    assert ("action", "file_list", {"path": "."}) in events
    assert ("endofop", "All files listed.") in events
    
    print("\n✅ StreamParser passed sanity check.")

if __name__ == "__main__":
    test_parser()
