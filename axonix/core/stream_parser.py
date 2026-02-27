"""
Axonix StreamParser — Real-time streaming response parser.

Watches the token stream character by character.
Detects <thought>, <action>, <ENDOFOP> blocks mid-stream.
Fires callbacks immediately when a complete block is found.
The agent loop pauses on <action>, executes the tool, injects result, then resumes.
"""

import json
import re
from typing import Callable, Optional
from axonix.core.debug import debug, warn, error


class StreamParser:
    """
    State machine that processes a stream of text tokens.
    
    States:
        TEXT      — normal output, pass tokens through
        THOUGHT   — inside <thought>...</thought>
        ACTION    — inside <action>...</action>
        ENDOFOP   — inside <ENDOFOP>...</ENDOFOP>
    
    Callbacks:
        on_text(token)        — normal text token (not inside a tag)
        on_thought(text)      — full thought block content
        on_action(tool, args) — parsed tool name + args dict
        on_endofop(summary)   — task complete signal + summary
        on_error(msg)         — parse error
    """

    STATE_TEXT    = "text"
    STATE_THOUGHT = "thought"
    STATE_ACTION  = "action"
    STATE_ENDOFOP = "endofop"

    # Tag definitions: (open_tag, close_tag, state)
    TAGS = [
        ("<thought>",  "</thought>",  STATE_THOUGHT),
        ("<action>",   "</action>",   STATE_ACTION),
        ("<ENDOFOP>",  "</ENDOFOP>",  STATE_ENDOFOP),
    ]

    def __init__(
        self,
        on_text:    Optional[Callable] = None,
        on_thought: Optional[Callable] = None,
        on_action:  Optional[Callable] = None,
        on_endofop: Optional[Callable] = None,
        on_error:   Optional[Callable] = None,
    ):
        self.on_text    = on_text    or (lambda t: None)
        self.on_thought = on_thought or (lambda t: None)
        self.on_action  = on_action  or (lambda n, a: None)
        self.on_endofop = on_endofop or (lambda s: None)
        self.on_error   = on_error   or (lambda m: None)

        self._state    = self.STATE_TEXT
        self._buffer   = ""   # accumulates raw stream
        self._tag_buf  = ""   # partial tag detection buffer
        self._content  = ""   # content inside current tag

    def feed(self, token: str):
        """Feed a token (could be multiple chars) into the parser."""
        for ch in token:
            self._process_char(ch)

    def _process_char(self, ch: str):
        self._buffer += ch

        if self._state == self.STATE_TEXT:
            self._tag_buf += ch

            # Check if we've entered any open tag
            for open_tag, close_tag, state in self.TAGS:
                if self._tag_buf.endswith(open_tag):
                    # Flush text before the tag
                    pre_text = self._tag_buf[:-len(open_tag)]
                    if pre_text:
                        self.on_text(pre_text)
                    self._tag_buf  = ""
                    self._content  = ""
                    self._state    = state
                    debug(f"StreamParser: entering state '{state}'")
                    return

            # Check if tag_buf could be a partial open tag prefix
            # If not, flush safe chars to avoid holding too much
            is_partial = any(
                open_tag.startswith(self._tag_buf[-len(open_tag):])
                for open_tag, _, _ in self.TAGS
                if len(self._tag_buf) >= 1
            )
            # Simple heuristic: if buffer > longest tag, flush first char
            max_tag_len = max(len(t[0]) for t in self.TAGS)
            if len(self._tag_buf) > max_tag_len + 2:
                flush = self._tag_buf[0]
                self._tag_buf = self._tag_buf[1:]
                self.on_text(flush)

        else:
            # We're inside a tag — accumulate content
            self._content += ch

            # Check for close tag
            for open_tag, close_tag, state in self.TAGS:
                if state == self._state and self._content.endswith(close_tag):
                    # Extract content without the close tag
                    inner = self._content[:-len(close_tag)]
                    debug(f"StreamParser: closing state '{state}', content length={len(inner)}")
                    self._dispatch(state, inner.strip())
                    self._state   = self.STATE_TEXT
                    self._content = ""
                    self._tag_buf = ""
                    return

    def _dispatch(self, state: str, content: str):
        if state == self.STATE_THOUGHT:
            self.on_thought(content)

        elif state == self.STATE_ACTION:
            tool, args = self._parse_action(content)
            if tool:
                self.on_action(tool, args)
            else:
                self.on_error(f"Failed to parse action: {content[:200]}")

        elif state == self.STATE_ENDOFOP:
            self.on_endofop(content)

    def _parse_action(self, content: str):
        """
        Parse action block content as JSON.
        Expected: {"tool": "tool_name", "args": {...}}
        Returns: (tool_name, args_dict) or (None, {})
        """
        content = content.strip()
        # Strip markdown code fences if model wraps in ```
        content = re.sub(r'^```\w*\n?', '', content)
        content = re.sub(r'\n?```$', '', content)
        content = content.strip()

        try:
            obj = json.loads(content)
            tool = obj.get("tool") or obj.get("name") or obj.get("function")
            args = obj.get("args") or obj.get("arguments") or obj.get("parameters") or {}
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except Exception:
                    args = {}
            if tool:
                debug(f"StreamParser: parsed action tool='{tool}' args={args}")
                return str(tool), dict(args)
        except json.JSONDecodeError as e:
            warn(f"StreamParser: JSON parse error: {e}\nContent: {content[:300]}")

            # Fallback: try to extract tool name with regex
            m = re.search(r'"(?:tool|name|function)"\s*:\s*"([^"]+)"', content)
            if m:
                tool = m.group(1)
                warn(f"StreamParser: extracted tool name via regex: {tool}")
                return tool, {}

        return None, {}

    def flush(self):
        """Flush any remaining text in the buffer. Call at end of stream."""
        if self._tag_buf and self._state == self.STATE_TEXT:
            self.on_text(self._tag_buf)
            self._tag_buf = ""
        if self._content and self._state != self.STATE_TEXT:
            warn(f"StreamParser: stream ended inside tag state '{self._state}'. Partial content: {self._content[:100]}")

    def reset(self):
        """Reset parser state for reuse."""
        self._state   = self.STATE_TEXT
        self._buffer  = ""
        self._tag_buf = ""
        self._content = ""
