import os
import openai
from typing import List, Any, Dict


class Model:
    """simple LLM wrapper"""

    def __init__(self, model_name: str = "gpt-4"):
        self.model_name = model_name
        self.api_key = os.getenv("OPENAI_API_KEY")

        if not self.api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set.")
        
        try:
            self.Client = openai.AsyncOpenAI(api_key=self.api_key)
        except ImportError:
            raise ImportError("pip install openai is required")
        
    def count_tokens(self,text:str) -> int:
        """simple token count"""

        return len(text)//4

    async def send_completion(self, messages: List[Dict[str, str]]) -> str:
        """send a message to the model and get response"""
        try:
            response = await self.Client.chat.completions.create(
                model = self.model_name,
                messages = messages,
                temperature = 0.1,
                max_tokens = 2000,
            )

            return response.choices[0].message.content
        
        except Exception as e:
            print(f"Error in send_completion: {e}")
            return "Error: Unable to get a response from the model."
        
    def parse_response(self, response:str) -> Dict[str, Any]:
        """parse the response for the model"""

        return {
            "response": response,
            "files_to_edit": [],
            "explanation": response
        }