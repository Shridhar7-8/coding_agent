import re
from pathlib import Path
from typing import List, Dict, Any, Tuple


class EditFormat:
    """ Base class for different edit formats """

    def __init__(self, name: str):
        self.name = name

    def parse_edits(self, response: str) -> List[Tuple[str, str, str]]:
        """ Parse LLM response into (filename, operation, content) tuples """
        raise NotImplementedError
    
    def apply_edit(self, file_path: str, edit_content: str) -> bool:
        """ Apply single edit """
        raise NotImplementedError
    

class UnifiedDiffFormat(EditFormat):
    """Unified diff format similar to `diff -U0`"""

    def __init__(self):
        super().__init__("udiff")

    def parse_edits(self, response: str) -> List[Tuple[str, str, str]]:
        """ Parse unified diff format from LLM response """
        
        edits = []

        diff_pattern = r'```diff\n(.*?)\n```'
        diff_blocks = re.findall(diff_pattern, response, re.DOTALL)

        for diff_block in diff_blocks:
            file_path = self._extract_file_path(diff_block)
            if file_path:
                edits.append(file_path, "modify", diff_block)

        return edits
    

    def _extract_file_path(self, diff_content: str) -> str:
        """ Extract file path from diff header """

        lines = diff_content.split('\n')

        for line in lines:
            if line.startswith('--- ') or line.startswith('+++ '):
                if 'dev/null' not in line:
                    return line.split(' ', 1)[1].strip()
        return None
    

    def apply_edit(self, file_path: str, diff_content: str) -> bool:
        """ Apply unified diff to file """

        try:
            hunks = self._parse_diff_hunks(diff_content)
            if Path(file_path).exists():
                with open(file_path, 'r', encoding='utf-8') as f:
                    original_lines = f.readlines()
            else:
                original_lines = []

            for hunk in reversed(hunks):
                original_lines = self._apply_hunk(original_lines, hunk)

            with open(file_path, 'w', encoding='utf-8') as f:
                f.writelines(original_lines)

            return True
        
        except Exception as e:
            print(f"Error applying diff to {file_path}: {e}")
            return False
        
class SearchReplaceFormat(EditFormat):  
    """Search/replace block format (SEARCH/REPLACE)"""  
      
    def __init__(self):  
        super().__init__("diff")  
      
    def parse_edits(self, response: str) -> List[Tuple[str, str, str]]:  
        """Parse search/replace blocks from LLM response"""  
        edits = []  
          
        # Multiple patterns to handle different formatting
        patterns = [
            # Pattern with python code block 
            r'```python\s*\n(\S+\.[\w]+)\s*\n<<<<<<< SEARCH\n(.*?)\n=======\n(.*?)\nREPLACE\n>>>>>>> ?\s*\n```',
            # Pattern without language specifier
            r'```\s*\n(\S+\.[\w]+)\s*\n<<<<<<< SEARCH\n(.*?)\n=======\n(.*?)\nREPLACE\n>>>>>>> ?\s*\n```',
            # Original pattern
            r'(\S+\.[\w]+)\s*```[\w]*\n<<<<<<< SEARCH\n(.*?)\n=======\n(.*?)\n>>>>>>> REPLACE\n```',
            # Pattern without code block wrapper
            r'(\S+\.[\w]+)\s*\n<<<<<<< SEARCH\n(.*?)\n=======\n(.*?)\n>>>>>>> ?REPLACE',
            # Very flexible pattern
            r'(\S+\.[\w]+).*?<<<<<<< SEARCH\n(.*?)\n=======\n(.*?)(?:\nREPLACE\n)?>>>>>>> ?(?:REPLACE)?',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, response, re.DOTALL)
            if matches:
                break  
          
        for file_path, search_content, replace_content in matches:  
            edits.append((file_path, "search_replace", {  
                "search": search_content,  
                "replace": replace_content  
            }))  
          
        return edits  
      
    def apply_edit(self, file_path: str, edit_data: Dict) -> bool:  
        """Apply search/replace edit to file"""  
        try:  
            # Read file content  
            with open(file_path, 'r', encoding='utf-8') as f:  
                content = f.read()  
              
            search_text = edit_data["search"]  
            replace_text = edit_data["replace"]  
              
            # First try exact string replacement  
            if search_text in content:  
                new_content = content.replace(search_text, replace_text, 1)  
                  
                # Write back to file  
                with open(file_path, 'w', encoding='utf-8') as f:  
                    f.write(new_content)  
                  
                return True  
            else:  
                # Try with normalized whitespace if exact match fails
                import textwrap
                
                # Normalize the search text (dedent and strip)
                normalized_search = textwrap.dedent(search_text).strip()
                
                # Try to find a match with normalized whitespace
                content_lines = content.split('\n')
                search_lines = normalized_search.split('\n')
                
                # Look for the pattern in the file
                for i in range(len(content_lines) - len(search_lines) + 1):
                    file_segment = '\n'.join(content_lines[i:i+len(search_lines)])
                    file_segment_normalized = textwrap.dedent(file_segment).strip()
                    
                    if file_segment_normalized == normalized_search:
                        # Found a match! Replace it
                        new_lines = content_lines[:i] + replace_text.split('\n') + content_lines[i+len(search_lines):]
                        new_content = '\n'.join(new_lines)
                        
                        with open(file_path, 'w', encoding='utf-8') as f:  
                            f.write(new_content)  
                        
                        return True
                
                print(f"Search text not found in {file_path}")
                print(f"Looking for: {repr(search_text)}")
                return False  
                  
        except Exception as e:  
            print(f"Error applying search/replace to {file_path}: {e}")  
            return False