"""
This little tool watches the stream of text coming from the AI.
It's looking for special tags like <thought>, <action>, and <ENDOFOP>.
As soon as it sees a complete block, it lets the agent know so we can act on it immediately.
"""

import json
import re
from typing import Callable, Optional
from axonix.core.debug import debug, warn, error


class StreamParser:
    """
    Think of this as a "tag-watcher". It reads the AI's output character by character
    and figures out if it's just normal talking, a thought, or an action.
    """

    STATE_TEXT    = "text"
    STATE_THOUGHT = "thought"
    STATE_ACTION  = "action"
    STATE_ENDOFOP = "endofop"

    # These are the tags we're keeping an eye out for.
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
        # We set up callbacks so other parts of the program can react
        # when we find something interesting in the stream.
        self.on_text    = on_text    or (lambda t: None)
        self.on_thought = on_thought or (lambda t: None)
        self.on_action  = on_action  or (lambda n, a: None)
        self.on_endofop = on_endofop or (lambda s: None)
        self.on_error   = on_error   or (lambda m: None)

        self._state    = self.STATE_TEXT
        self._buffer   = ""   # Keeps track of the raw text
        self._tag_buf  = ""   # Used to spot tags as they start
        self._content  = ""   # The stuff inside the tags

    def feed(self, token: str):
        """Feed a bit of text into the watcher."""
        for ch in token:
            self._process_char(ch)

    def _process_char(self, ch: str):
        # We look at every single character to make sure we don't miss a tag.
        self._buffer += ch

        if self._state == self.STATE_TEXT:
            self._tag_buf += ch

            # Have we started a new tag?
            for open_tag, close_tag, state in self.TAGS:
                if self._tag_buf.endswith(open_tag):
                    # Send any text we found BEFORE the tag started.
                    pre_text = self._tag_buf[:-len(open_tag)]
                    if pre_text:
                        self.on_text(pre_text)
                    self._tag_buf  = ""
                    self._content  = ""
                    self._state    = state
                    debug(f"Parser: Spotted an opening tag for '{state}'.")
                    return

            # Keep the tag buffer small so we don't hold onto too much text.
            max_tag_len = max(len(t[0]) for t in self.TAGS)
            if len(self._tag_buf) > max_tag_len + 2:
                flush = self._tag_buf[0]
                self._tag_buf = self._tag_buf[1:]
                self.on_text(flush)

        else:
            # We're inside a tag, so we just collect everything until we see the end.
            self._content += ch

            # Is the tag finished?
            for open_tag, close_tag, state in self.TAGS:
                if state == self._state and self._content.endswith(close_tag):
                    inner = self._content[:-len(close_tag)]
                    debug(f"Parser: Found the end of the '{state}' block.")
                    self._dispatch(state, inner.strip())
                    self._state   = self.STATE_TEXT
                    self._content = ""
                    self._tag_buf = ""
                    return

    def _dispatch(self, state: str, content: str):
        # Time to tell the rest of the app what we found!
        if state == self.STATE_THOUGHT:
            self.on_thought(content)

        elif state == self.STATE_ACTION:
            tool, args = self._parse_action(content)
            if tool:
                self.on_action(tool, args)
            else:
                self.on_error(f"I couldn't quite figure out this action: {content[:100]}")

        elif state == self.STATE_ENDOFOP:
            self.on_endofop(content)

    def _parse_action(self, content: str):
        """
        We try our best to turn the AI's action request into something the computer understands.
        """
        content = content.strip()
        # Clean up any markdown formatting the AI might have added.
        content = re.sub(r'^```\w*\n?', '', content)
        content = re.sub(r'\n?```$', '', content)
        content = content.strip()

        # Let's fix common little mistakes like trailing commas.
        content = re.sub(r',(\s*[}\]])', r'\1', content)

        try:
            obj = json.loads(content)
            tool = obj.get("tool") or obj.get("name") or obj.get("function")
            args = obj.get("args") or obj.get("arguments") or obj.get("parameters") or {}
            if isinstance(args, str):
                try: args = json.loads(args)
                except: args = {}
            if tool:
                return str(tool), dict(args)
        except json.JSONDecodeError:
            # If JSON fails, we'll try a last-ditch effort with regex to find the tool name.
            m = re.search(r'"(?:tool|name|function)"\s*:\s*"([^"]+)"', content)
            if m:
                tool = m.group(1)
                return tool, {}

        return None, {}

    def flush(self):
        """Send any leftovers when the stream ends."""
        if self._tag_buf and self._state == self.STATE_TEXT:
            self.on_text(self._tag_buf)
            self._tag_buf = ""

    def reset(self):
        """Get ready for a fresh start."""
        self._state   = self.STATE_TEXT
        self._buffer  = ""
        self._tag_buf = ""
        self._content = ""
