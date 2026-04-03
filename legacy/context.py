import os
import ast
import warnings
from pathlib import Path
from collections import defaultdict, Counter
from typing import List, Dict, Set, Any
warnings.simplefilter("ignore", category=FutureWarning)
from grep_ast.tsl import get_language, get_parser
from grep_ast import filename_to_lang


class ContextManager:
    """ Manages code context for LLM interactions"""

    def __init__(self, root_path: str = ".", map_tokens: int = 1024):
        self.root_path = Path(root_path)
        self.file_cache = {}
        self.context_budget = map_tokens
        self.map_mul_no_files = 8
        self.tags_cache = {}
        self.context_cache = {}  
        self.file_mtimes = {}   

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
    
    def _get_file_symbols_ast(self, file_path: str) -> Dict[str, List[Dict]]:
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
    


    def _get_file_symbols_ast_treesitter(self, file_path: str) -> Dict[str, List[Dict]]:  
        """Extract symbols using tree-sitter for multi-language support"""  
        
        if file_path in self.tags_cache:  
            return self.tags_cache[file_path]  
              
        symbols = {"functions": [], "classes": [], "variables": []}  
          
        try:  
            # Determine language from filename  
            lang = filename_to_lang(file_path)  
            if not lang:  
                return symbols  
                  
            # Get tree-sitter parser for the language  
            parser = get_parser(lang)  
            if not parser:  
                return symbols  
                  
            # Parse the file content  
            content = self.get_file_content(file_path)  
            tree = parser.parse(bytes(content, "utf-8"))  
              
            # Extract symbols using tree-sitter queries  
            symbols = self._extract_symbols_from_tree(tree, content, lang)  
              
            self.tags_cache[file_path] = symbols  
            return symbols  
              
        except Exception as e:  
            print(f"Error parsing {file_path} with tree-sitter: {e}")  
            # Fallback to AST for Python files  
            if file_path.endswith('.py'):  
                return self._get_file_symbols_ast(file_path)  
            return symbols




    def _extract_symbols_from_tree(self, tree, content: str, lang: str) -> Dict[str, List[Dict]]:  
        """Extract symbols from tree-sitter parse tree"""  
        
        symbols = {"functions": [], "classes": [], "variables": []}  
        content_lines = content.split('\n')  
          
        def traverse_node(node):  
            """Recursively traverse tree nodes to find definitions"""  
            node_type = node.type  
              
            # Function definitions  
            if node_type in ['function_definition', 'method_definition', 'function_declaration']:  
                name_node = self._find_name_node(node)  
                if name_node:  
                    symbols["functions"].append({  
                        "name": name_node.text.decode('utf-8'),  
                        "line": node.start_point[0] + 1,  
                        "signature": self._get_node_signature(node, content_lines),  
                        "kind": "function"  
                    })  
              
            # Class definitions  
            elif node_type in ['class_definition', 'class_declaration', 'interface_declaration']:  
                name_node = self._find_name_node(node)  
                if name_node:  
                    methods = self._extract_class_methods(node)  
                    symbols["classes"].append({  
                        "name": name_node.text.decode('utf-8'),  
                        "line": node.start_point[0] + 1,  
                        "methods": methods,  
                        "kind": "class"  
                    })  
              
            # Variable definitions  
            elif node_type in ['variable_declaration', 'assignment', 'const_declaration']:  
                name_node = self._find_name_node(node)  
                if name_node:  
                    symbols["variables"].append({  
                        "name": name_node.text.decode('utf-8'),  
                        "line": node.start_point[0] + 1,  
                        "kind": "variable"  
                    })  
              
            # Recursively process child nodes  
            for child in node.children:  
                traverse_node(child)  
          
        traverse_node(tree.root_node)  
        return symbols  
      
    
    def _find_name_node(self, node):  
        """Find the name node within a definition node"""  
        
        for child in node.children:  
            if child.type in ['identifier', 'name']:  
                return child  
        return None  
      
    
    def _get_node_signature(self, node, content_lines: List[str]) -> str:  
        """Extract function signature from node"""  
        
        start_line = node.start_point[0]  
        end_line = min(node.end_point[0] + 1, len(content_lines))  
          
        # Get the first few lines of the definition  
        signature_lines = content_lines[start_line:min(start_line + 3, end_line)]  
        return ' '.join(line.strip() for line in signature_lines if line.strip())  
      
    
    def _extract_class_methods(self, class_node) -> List[str]:  
        """Extract method names from a class node"""  
        
        methods = []  
        for child in class_node.children:  
            if child.type in ['function_definition', 'method_definition']:  
                name_node = self._find_name_node(child)  
                if name_node:  
                    methods.append(name_node.text.decode('utf-8'))  
        return methods

    
    def analyze_dependencies(self, files: List[str]) -> Dict[str, Set[str]]:  
        """Analyze dependencies between files and symbols"""  
        dependencies = defaultdict(set)  
        all_symbols = {}  
          
        # First pass: collect all symbols  
        for file_path in files:  
            symbols = self._get_file_symbols_ast_treesitter(file_path)  
            for category in symbols:  
                for symbol in symbols[category]:  
                    symbol_key = f"{file_path}:{symbol['name']}"  
                    all_symbols[symbol['name']] = symbol_key  
          
        # Second pass: find references  
        for file_path in files:  
            content = self.get_file_content(file_path)  
            file_dependencies = set()  
              
            # Look for symbol references in content  
            for symbol_name, symbol_key in all_symbols.items():  
                if symbol_name in content and not symbol_key.startswith(file_path):  
                    file_dependencies.add(symbol_key)  
              
            dependencies[file_path] = file_dependencies  
          
        return dict(dependencies)  
      
    def build_dependency_graph(self, files: List[str]) -> Dict[str, float]:  
        """Build PageRank-style dependency graph"""  
        dependencies = self.analyze_dependencies(files)  
        symbol_scores = defaultdict(float)  
          
        # Calculate importance based on references  
        for file_path, deps in dependencies.items():  
            for dep in deps:  
                symbol_scores[dep] += 1.0  
          
        # Normalize scores  
        max_score = max(symbol_scores.values()) if symbol_scores else 1.0  
        for symbol in symbol_scores:  
            symbol_scores[symbol] /= max_score  
          
        return dict(symbol_scores)
    


    def build_multilang_context(self, files: List[str], query: str = "") -> str:  
        """Build context with multi-language support"""  
        
        context_parts = []  
        language_stats = defaultdict(int)  
          
        # Analyze repository languages  
        repo_info = self.scan_repository()  
        for lang in repo_info["languages"]:  
            language_stats[lang] = sum(1 for f in files if f.endswith(lang))  
          
        # Repository overview with language breakdown  
        overview = f"Repository: {len(files)} files\n"  
        overview += f"Languages: {dict(language_stats)}\n\n"  
        context_parts.append(overview)  
          
        # Build dependency graph  
        dep_scores = self.build_dependency_graph(files)  
          
        # Process files by importance  
        file_importance = defaultdict(float)  
        for file_path in files:  
            symbols = self._get_file_symbols_ast_treesitter(file_path)  
            for category in symbols:  
                for symbol in symbols[category]:  
                    symbol_key = f"{file_path}:{symbol['name']}"  
                    file_importance[file_path] += dep_scores.get(symbol_key, 0.1)  
          
        # Sort files by importance  
        sorted_files = sorted(files, key=lambda f: file_importance[f], reverse=True)  
          
        # Add file contexts within token budget  
        current_tokens = len(overview) // 4  
        for file_path in sorted_files:  
            if current_tokens >= self.context_budget:  
                break  
                  
            symbols = self._get_file_symbols_ast_treesitter(file_path)  
            file_section = self._format_multilang_symbols(file_path, symbols)  
              
            section_tokens = len(file_section) // 4  
            if current_tokens + section_tokens <= self.context_budget:  
                context_parts.append(file_section)  
                current_tokens += section_tokens  
          
        return "".join(context_parts)  
      
    def _format_multilang_symbols(self, file_path: str, symbols: Dict) -> str:  
        """Format symbols for multiple languages"""  
        
        lines = [f"{file_path}:\n"]  
          
        # Add classes with methods  
        for cls in symbols["classes"]:  
            lines.append(f"  class {cls['name']}:\n")  
            for method in cls.get("methods", []):  
                lines.append(f"    {method}\n")  
          
        # Add functions  
        for func in symbols["functions"]:  
            signature = func.get("signature", func["name"])  
            lines.append(f"  {signature}\n")  
          
        # Add important variables  
        for var in symbols["variables"][:5]:  # Limit variables  
            lines.append(f"  {var['name']}\n")  
          
        lines.append("\n")  
        return "".join(lines)


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
            symbols = self.__get_file_symbols_ast_ast(file_path)

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
        



    def build_optimized_context(self, files: List[str], query: str = "",
                              mentioned_symbols: Set[str] = None) -> str:
        
        """ Build context with intelligent selection and truncation """

        max_tokens = self.context_budget
        if not files:
            max_tokens = min(max_tokens*self.map_mul_no_files, 32000)
        scores = self.calculate_relevance_scores(files, mentioned_symbols)
        sorted_symbols = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return self._binary_search_context(sorted_symbols, max_tokens, files)
    

    def _binary_search_context(self, sorted_symbols: List, max_tokens: int, 
                               files: List[str]) -> str:
        
        """ binary search to find optimal context within token budget """

        if not sorted_symbols:
            return self._build_basic_context(files[:3])
        
        lower_bound = 0
        upper_bound = len(sorted_symbols)
        best_context = ""
        best_tokens = 0

        while lower_bound <= upper_bound:
            middle = (lower_bound+upper_bound) // 2

            context = self._build_context_from_symbols(sorted_symbols[:middle], files)
            token_count = len(context) // 4  # Rough estimate of tokens

            if token_count <= max_tokens:
                best_context = context
                best_tokens = token_count
                lower_bound = middle + 1
            else:
                upper_bound = middle - 1

        return best_context or self._build_basic_context(files[:2])


    def _build_context_from_symbols(self, symbol_items: List, files: List[str]) -> str:
        
        """Build context string from selected symbols"""
     
        context_parts = []
        included_files = set()

        repo_info = self.scan_repository()
        overview = f"Repository: {len(repo_info['files'])} files\n"
        overview += f"Languages: {', '.join(repo_info['languages'])}\n\n"
        context_parts.append(overview)

        for symbol_key, score in symbol_items:
            file_path, symbol_name = symbol_key.split(":", 1)

            if file_path not in included_files:
                symbols = self._get_file_symbols_ast(file_path)
                file_section = self._format_file_symbols(file_path, symbols, symbol_name)
                context_parts.append(file_section)
                included_files.add(file_path)

        return "".join(context_parts)
    
    
    
    def _format_file_symbols(self, file_path: str, symbols: Dict, highlight_symbol: str = None) -> str:  
        
        """Format file symbols in tree-like structure"""  
        lines = [f"{file_path}:\n"]  
          
         
        for cls in symbols["classes"]:  
            marker = "★ " if cls["name"] == highlight_symbol else "  "  
            lines.append(f"{marker}class {cls['name']}:\n")  
            for method in cls["methods"]:  
                lines.append(f"    def {method}()\n")  
          
        
        for func in symbols["functions"]:  
            marker = "★ " if func["name"] == highlight_symbol else "  "  
            lines.append(f"{marker}def {func['signature']}\n")  
          
        lines.append("\n")  
        return "".join(lines)
    
    
    
    def get_cached_context(self, cache_key: str) -> str:  
        
        """Get cached context if still valid"""  
        
        if cache_key not in self.context_cache:  
            return None  
              
        cached_data = self.context_cache[cache_key]  

        # Check if any files have been modified  
        for file_path in cached_data["files"]:  
            try:  
                current_mtime = os.path.getmtime(self.root_path / file_path)  
                if file_path not in self.file_mtimes or self.file_mtimes[file_path] != current_mtime:  
                    # File modified, invalidate cache  
                    del self.context_cache[cache_key]  
                    return None  
            except OSError:  
                # File doesn't exist anymore  
                del self.context_cache[cache_key]  
                return None  
                  
        return cached_data["context"]  
    

      
    def cache_context(self, cache_key: str, context: str, files: List[str]):  
        
        """Cache context with file modification times"""  
        
        file_mtimes = {}  
        for file_path in files:  
            try:  
                file_mtimes[file_path] = os.path.getmtime(self.root_path / file_path)  
            except OSError:  
                continue  
                  
        self.context_cache[cache_key] = {  
            "context": context,  
            "files": files,  
            "mtimes": file_mtimes  
        }  
        self.file_mtimes.update(file_mtimes)
        

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


    def _build_basic_context(self, files: List[str]) -> str:

        """Fallback context builder for when optimization fails"""  
        
        context_parts = []  
        repo_info = self.scan_repository()  
        overview = f"Repository: {len(repo_info['files'])} files\n"  
        overview += f"Languages: {', '.join(repo_info['languages'])}\n\n"  
        context_parts.append(overview)  
        
        for file_path in files:  
            symbols = self._get_file_symbols_ast(file_path)  
            file_section = self._format_file_symbols(file_path, symbols)  
            context_parts.append(file_section)  
        
        return "".join(context_parts)
    
    
    
    def get_file_symbols(self, file_path: str) -> Dict[str, List[Dict]]:  
        """Main symbol extraction method with fallback strategy"""  
        
        # tree-sitter first
        try:  
            return self.get_file_symbols_treesitter(file_path)  
        except Exception as e:  
            print(f"Tree-sitter failed for {file_path}, falling back to AST: {e}")  
            
            # Fallback to AST implementation  
            if file_path.endswith('.py'):  
                return self._get_file_symbols_ast(file_path)
            
            return {"functions": [], "classes": [], "variables": []}


    def get_context_for_message(self, files: List[str], message: str) -> str:
        """Choose appropriate context strategy based on situation"""

        # If no files specified, use optimized repository overview
        if not files:
            return self.build_optimized_context([], message)
        
        # If few files, use full content  
        if len(files) <= 3:  
            return self.build_context(files, message)  
        
        # If many files, use optimized approach  
        return self.build_optimized_context(files, message)