import os
import ast
from pathlib import Path
from collections import defaultdict, counter
from typing import List, Dict, Set, Any


class ContextManager:
    """ Manages code context for LLM interactions"""

    def __init__(self, root_path: str = ".", map_tokens: int = 1024):
        self.root_path = Path(root_path)
        self.file_cache = {}
        self.context_budget = map_tokens
        self.map_mul_no_files = 8
        self.tags_cache = {}

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
    
    def get_file_symbols(self, file_path: str) -> Dict[str, List[str]]:
        """ Extracts functions, classes, and variables from python files """

        if file_path in self.tags_cache:
            return self.tags_cache[file_path]

        symbols = {"functions": [], "classes": [], "variables": []}

        try:
            content = self.get_file_content(file_path)
            tree = ast.parse(content)

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    symbols["functions"].append({
                        "name": node.name,
                        "line": node.lineno,
                        "args": [arg.arg for arg in node.args.args],
                        "signature": self._get_function_signature(node)
                    })

                elif isinstance(node, ast.ClassDef):
                    symbols["classes"].append({
                        "name": node.name,
                        "line": node.lineno,
                        "methods": [n.name for n in node.body if isinstance(n, ast.FunctionDef)]
                    })

                elif isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            symbols["variables"].append({
                                "name": target.id,
                                "line": node.lineno
                            })

            self.tags_cache[file_path] = symbols
            return symbols
        
        except Exception as e:
            print(f"Error parsing {file_path}: {e}")
            return symbols

    def _get_function_signature(self, node: ast.FunctionDef) -> str:
        """ Generate function signature string """
        args = []
        for arg in node.args.args:
            args.append(arg.arg)
        return f"{node.name}({', '.join(args)})"
    
    def calculate_relevance_scores(self, files: List[str], mentioned_symbols: Set[str] = None) -> Dict[str, float]:
        """ calculates relevance scores for file and symbols """

        if not mentioned_symbols:
            mentioned_symbols = set()

        scores = defaultdict(float)
        symbol_refrences = defaultdict(list)

        for file_path in files:
            content = self.get_file_content(file_path)
            symbols = self.get_file_symbols(file_path)

            for func in symbols["functions"]:
                base_score = 1.0
                if func["name"] in mentioned_symbols:
                    base_score *= 10
                if not func["name"].startswith("_"):
                    base_score *= 2

                ref_count = sum(1 for f in files if f!=file_path
                                and func["name"] in self.get_file_content(f))
                base_score *= (1+ref_count*0.5)
                scores[f"{file_path}:{func['name']}"] = base_score

            for cls in symbols["classes"]:  
                base_score = 2.0
                if cls["name"] in mentioned_symbols:  
                    base_score *= 10  
                if not cls["name"].startswith("_"):  
                    base_score *= 2  
                      
                ref_count = sum(1 for f in files if f != file_path   
                              and cls["name"] in self.get_file_content(f))  
                base_score *= (1 + ref_count * 0.5)  
                  
                scores[f"{file_path}:{cls['name']}"] = base_score  
          
        return dict(scores)


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
