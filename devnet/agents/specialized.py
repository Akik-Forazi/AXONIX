"""
Specialized Agents - Pre-built agents for specific tasks
"""

from devnet.core.agent import Agent


class CoderAgent(Agent):
    """Agent specialized for writing, editing and debugging code."""

    EXTRA_PROMPT = """
You are specialized in coding tasks. When given a coding task:
1. Understand the requirements
2. Plan the implementation
3. Write the code using file_write
4. Test it using shell_python or shell_run
5. Fix any errors
6. Return the final result
"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.messages[0]["content"] += self.EXTRA_PROMPT


class ResearchAgent(Agent):
    """Agent specialized for research tasks."""

    EXTRA_PROMPT = """
You are specialized in research tasks. When given a research topic:
1. Search the web for information
2. Fetch relevant pages
3. Synthesize the information
4. Save key findings to memory
5. Write a comprehensive report to a file
"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.messages[0]["content"] += self.EXTRA_PROMPT


class FileAgent(Agent):
    """Agent specialized for file/project management."""

    EXTRA_PROMPT = """
You are specialized in file and project management. You excel at:
- Organizing file structures
- Bulk file operations
- Finding and editing content across many files
- Creating project scaffolding
"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.messages[0]["content"] += self.EXTRA_PROMPT
