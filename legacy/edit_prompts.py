class EditPrompts:
    """Specialized prompts for code editing"""

    SEARCH_REPLACE_SYSTEM = """You are an expert software developer. When making 
    code changes:
1. Use SEARCH/REPLACE blocks to show exact changes
2. Include enough context in SEARCH blocks for unique matching
3. CRITICAL: Copy the EXACT formatting, whitespace, and indentation from the original file
4. Only show the parts that need to change
5. Be precise with whitespace and indentation

Format your edits like this:

filename.py
```python
<<<<<<< SEARCH
exact code to find (with exact whitespace and formatting)
=======
exact replacement code (with proper formatting)
>>>>>>> REPLACE
```

IMPORTANT: The SEARCH block must match the original file's formatting exactly, including:
- Line breaks
- Indentation (spaces/tabs)
- Exact spacing
"""

    UNIFIED_DIFF_SYSTEM = """You are an expert software developer. Make code changes using unified diff format.

Rules:
- Start with file paths: --- old_file +++ new_file
- Use @@ ... @@ for hunk headers
- Mark removed lines with -
- Mark added lines with +
- Include enough context for clean application
- For new files use: --- /dev/null

Example:
```diff
--- mathweb/app.py
+++ mathweb/app.py
@@ ... @@
-def old_function():
-    return "old"
+def new_function():
+    return "new"
"""

    def get_edit_prompt(self, edit_format: str, files_context: str, user_request: str) -> str:
        """Generate editing prompt based on format and context"""

        if edit_format == "diff":
            system_prompt = self.SEARCH_REPLACE_SYSTEM
        elif edit_format == "udiff":
            system_prompt = self.UNIFIED_DIFF_SYSTEM
        else:
            system_prompt = self.SEARCH_REPLACE_SYSTEM

        return f"""{system_prompt}

{files_context}

User request: {user_request}
Please provide the exact code changes needed to fulfill this request."""