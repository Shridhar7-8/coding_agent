import asyncio
import re  
from typing import List
from context import ContextManager
from models import Model
from typing import Set
from editor import SmartEditor  
from edit_prompts import EditPrompts



class Coder:
    """Basic code editing orchestrator"""
    
    def __init__(self, model: Model, files: List[str]):
        self.model = model
        self.files = files or []
        self.context_manager = ContextManager()
        self.chat_history = []
        self.editor = SmartEditor(self.context_manager.root_path)  
        self.edit_prompts = EditPrompts()  
        self.edit_format = "diff"

    async def run_single(self, message: str):
        """Run a single interaction with the model"""
        
        response = await self._process_message(message)
        print("Assistant:", response)


    async def run_chat_loop(self):
        """Interactive chat loop"""

        while True:
            try:
                user_input = input("> ")
                if user_input.lower() in ["exit", "quit"]:
                    break
                response = await self._process_message(user_input)
                print("Assistant:", response)
            
            except KeyboardInterrupt:
                print("\nGoodbye!")
                break
    
    
    async def _process_message(self, message: str) -> str:
        """Process message and return the model response"""

        mentioned_symbols = self._extract_mentioned_symbols(message)
        
        # If no files specified, scan the current directory for Python files
        files_to_analyze = self.files
        if not files_to_analyze:
            repo_info = self.context_manager.scan_repository()
            files_to_analyze = repo_info["files"][:10]  # Limit to first 10 files to avoid overwhelming
        
        context = self.context_manager.build_multilang_context(files_to_analyze, message)
        
        edit_prompt = self.edit_prompts.get_edit_prompt(  
            self.edit_format, context, message  
        )

        messages = [
            {
                "role": "system",
                "content": edit_prompt
            }
        ]

        if context.strip():
            messages.append({
                "role":"system",
                "content": f"Multi-language Repository Context:\n{context}"  
            })

        messages.append({
            "role": "user",
            "content": message
        })

        
        response = await self.model.send_completion(messages)

        if self._contains_edits(response):  
            edit_results = self.editor.apply_edits(response, self.edit_format)  
              
            if edit_results["success"]:  
                edited_files = ", ".join(edit_results["edited_files"])  
                response += f"\n\n Successfully applied edits to: {edited_files}"  
            else:  
                response += f"\n\n Failed to apply some edits. Errors: {edit_results['errors']}" 

        self.chat_history.append({"role": "user", "content": message})

        return response
    

    def _extract_mentioned_symbols(self, message: str) -> Set[str]:

        """Extract function/class names mentioned in user message"""  
     
        
        symbols = set()  
        
        # Look for function calls: word()  
        func_pattern = r'\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\('  
        symbols.update(re.findall(func_pattern, message))  
        
        # Look for class references: ClassName  
        class_pattern = r'\b([A-Z][a-zA-Z0-9_]*)\b'  
        symbols.update(re.findall(class_pattern, message))  
        
        return symbols
    

    def _contains_edits(self, response: str) -> bool:  
        """Check if response contains edit instructions"""  
        
        edit_indicators = [  
            "<<<<<<< SEARCH",  
            "```diff",  
            "--- ",  
            "+++ "  
        ]  
        return any(indicator in response for indicator in edit_indicators)  

