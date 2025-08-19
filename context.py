import os
from pathlib import Path
from typing import List, Dict, Set, Any


class ContextManager:
    """ Manages code context for LLM interactions"""

    def __init__(self, root_path: str = "."):
        self.root_path = Path(root_path)
        self.file_cache = {}
        self.context_budget = 4000

    def scan_repository(self) -> Dict[str, Any]:
        """scans the repository"""

        repo_info = {
            "files": [],
            "structure": {},
            "total_files": 0,
            "languages": set()
        }

        for root, dirs, files in os.walk(self.root_path):
            dirs[:] = [d for d in dirs if not d.startswith('.') and d != '__pycache__']
            for file in files:
                if self._should_include_file(file):
                    file_path = Path(root) / file
                    relative_path = file_path.relative_to(self.root_path)
                    repo_info["files"].append(str(relative_path))
                    repo_info["languages"].add(file_path.suffix) 
        
        repo_info["total_files"] = len(repo_info["files"])
        return repo_info


    def _should_include_file(self, file_name: str) -> bool:
        """Determines if a file should be included in the context"""
        
        extensions = {'.py', '.js', '.html', '.css', '.java', '.ts', '.cpp',
                       '.c', '.h', '.txt', '.md'}
        ignore_files = {'__pycache__', '.git', '.pyc', '.log'}

        return (
            Path(file_name).suffix in extensions and 
            not any(ignore in file_name for ignore in ignore_files)
        )

    def get_file_content(self, file_path: str) -> str:
        """ Get and cache file content """

        if file_path in self.file_cache:
            return self.file_cache[file_path]
        
        try:
            with open(Path(self.root_path) / file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                self.file_cache[file_path] = content
                return content
        except Exception as e:
            return f"Error reading file {file_path}: {e}"
        

    def build_context(self, files: List[str], query: str = "") -> str:
        """ Builds context for the LLM"""

        context_parts = []
        current_tokens = 0

        repo_info = self.scan_repository()
        overview = f"""Repository: {repo_info['total_files']} files, 
                       Languages: {', '.join(repo_info['languages'])}\n\n"""
        context_parts.append(overview)
        current_tokens += len(overview)//4

        for file_path in files:
            if current_tokens >= self.context_budget:
                break

            content = self.get_file_content(file_path)
            file_section = f"==={file_path} ===\n{content}\n\n"

            file_tokens = len(file_section)//4
            if current_tokens + file_tokens <= self.context_budget:
                context_parts.append(file_section)
                current_tokens += file_tokens
            else:
                remaining_budget = self.context_budget - current_tokens
                truncated_content = content[:remaining_budget * 4]
                context_parts.append(f"=== {file_path} (truncated) ===\n{truncated_content}\n\n")
                break

        return "".join(context_parts)
