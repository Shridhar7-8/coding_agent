from typing import List
from context import ContextManager
from models import Model



class Coder:
    """Basic code editing orchestrator"""
    
    def __init__(self, model: Model, files: List[str]):
        self.model = model
        self.files = files or []
        self.context_manager = ContextManager()
        self.chat_history = []

    def run_single(self, message: str):
        """Run a single interaction with the model"""
        
        response = self._process_message(message)
        print("Assistant:", response)


    def run_chat_loop(self):
        """Interactive chat loop"""

        while True:
            try:
                user_input = input("> ")
                if user_input.lower() in ["exit", "quit"]:
                    break
                response = self._process_message(user_input)
                print("Assistant:", response)
            
            except KeyboardInterrupt:
                print("\nGoodbye!")
                break
    
    
    def _process_message(self, message: str) -> str:
        """Process message and return the model response"""

        context = self.context_manager.build_context(self.files, message)
        messages = [
            {
                "role": "system",
                "content": "You are a helpful coding assistant. Help the user with their code."
            }
        ]

        if context.strip():
            messages.append({
                "role":"system",
                "content": f"Here is the current codebase context:\n\n{context}"
            })

        messages.append({
            "role": "user",
            "content": message
        })

        response  = self.model.send_completion(messages)

        self.chat_history.append({"role": "user", "content": message})

        return response

