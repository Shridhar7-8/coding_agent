import subprocess  
import tempfile  
from pathlib import Path  
from typing import Dict, Any
from typing import List, Dict, Set, Tuple  
from edit_formats import UnifiedDiffFormat, SearchReplaceFormat
  
class SmartEditor:  
    """Smart code editing system with validation"""  
      
    def __init__(self, root_path: str = "."):  
        self.root_path = Path(root_path)  
        self.edit_formats = {  
            "udiff": UnifiedDiffFormat(),  
            "diff": SearchReplaceFormat(),  
        }  
        self.backup_dir = None  
      
    def apply_edits(self, response: str, edit_format: str = "diff") -> Dict[str, Any]:  
        """Apply edits from LLM response with validation"""  
        results = {  
            "edited_files": set(),  
            "failed_files": set(),  
            "errors": [],  
            "success": False  
        }  
          
        try:  
            # Parse edits from response  
            format_handler = self.edit_formats.get(edit_format)  
            if not format_handler:  
                raise ValueError(f"Unknown edit format: {edit_format}")  
              
            edits = format_handler.parse_edits(response)  
              
            if not edits:  
                results["errors"].append("No edits found in response")  
                return results  
              
            # Create backup before applying edits  
            self._create_backup(edits)  
              
            # Apply each edit  
            for file_path, operation, edit_content in edits:  
                full_path = self.root_path / file_path  
                  
                try:  
                    # Ensure directory exists  
                    full_path.parent.mkdir(parents=True, exist_ok=True)  
                      
                    # Apply the edit  
                    success = format_handler.apply_edit(str(full_path), edit_content)  
                      
                    if success:  
                        results["edited_files"].add(file_path)  
                        print(f"✓ Applied edit to {file_path}")  
                    else:  
                        results["failed_files"].add(file_path)  
                        print(f"✗ Failed to apply edit to {file_path}")  
                          
                except Exception as e:  
                    results["failed_files"].add(file_path)  
                    results["errors"].append(f"Error editing {file_path}: {e}")  
                    print(f"✗ Error editing {file_path}: {e}")  
              
            # Validate edits  
            validation_results = self._validate_edits(results["edited_files"])  
            results.update(validation_results)  
              
            results["success"] = len(results["edited_files"]) > 0 and len(results["failed_files"]) == 0  
              
        except Exception as e:  
            results["errors"].append(f"Edit application failed: {e}")  
            self._restore_backup()  
          
        return results  
      
    def _create_backup(self, edits: List[Tuple]) -> None:  
        """Create backup of files before editing"""  
        if not edits:  
            return  
              
        self.backup_dir = tempfile.mkdtemp(prefix="aider_backup_")  
          
        for file_path, _, _ in edits:  
            full_path = self.root_path / file_path  
            if full_path.exists():  
                backup_path = Path(self.backup_dir) / file_path  
                backup_path.parent.mkdir(parents=True, exist_ok=True)  
                  
                # Copy file to backup  
                import shutil  
                shutil.copy2(full_path, backup_path)  
      
    def _validate_edits(self, edited_files: Set[str]) -> Dict[str, Any]:  
        """Validate edited files for syntax errors"""  
        validation_results = {  
            "syntax_errors": [],  
            "lint_warnings": []  
        }  
          
        for file_path in edited_files:  
            full_path = self.root_path / file_path  
              
            # Python syntax validation  
            if file_path.endswith('.py'):  
                try:  
                    with open(full_path, 'r', encoding='utf-8') as f:  
                        content = f.read()  
                      
                    compile(content, str(full_path), 'exec')  
                    print(f"✓ {file_path} syntax valid")  
                      
                except SyntaxError as e:  
                    error_msg = f"Syntax error in {file_path}:{e.lineno}: {e.msg}"  
                    validation_results["syntax_errors"].append(error_msg)  
                    print(f"✗ {error_msg}")  
          
        return validation_results  
      
    def _restore_backup(self) -> None:  
        """Restore files from backup if edit failed"""  
        if not self.backup_dir or not Path(self.backup_dir).exists():  
            return  
              
        import shutil  
        for backup_file in Path(self.backup_dir).rglob('*'):  
            if backup_file.is_file():  
                relative_path = backup_file.relative_to(self.backup_dir)  
                original_path = self.root_path / relative_path  
                shutil.copy2(backup_file, original_path)  
                print(f"Restored {relative_path} from backup")