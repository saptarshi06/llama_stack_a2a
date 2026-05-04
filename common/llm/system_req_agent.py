import json
import logging
from typing import Dict, Any, AsyncIterator
from .ollama_client import OllamaClient

logger = logging.getLogger(__name__)


class SystemRequirementAgent:
    """Agent for generating system requirements from user input"""
    
    def __init__(self, ollama_client: OllamaClient, config: Dict[str, Any]):
        self.client = ollama_client
        self.config = config
        self.instructions = config.get("instructions", "")
        self.name = config.get("name", "System Requirement Analyst")
    
    async def generate(self, user_request: str, session_id: str) -> AsyncIterator[Dict[str, Any]]:
        """Generate system requirements from user request"""
        
        messages = [
            {"role": "system", "content": self.instructions},
            {"role": "user", "content": f"Generate system requirements for: {user_request}"}
        ]
        
        full_response = ""
        
        async for chunk in self.client.generate(messages, stream=True):
            if chunk.get("type") == "content":
                full_response += chunk["content"]
                yield {
                    "type": "stream",
                    "agent": "system_requirement",
                    "content": chunk["content"],
                    "message": "System Requirement Agent is analyzing your request..."
                }
            elif chunk.get("type") == "error":
                yield {
                    "type": "error",
                    "agent": "system_requirement",
                    "error": chunk["error"]
                }
        
        # Parse and validate JSON response
        try:
            # Extract JSON from response
            json_start = full_response.find('{')
            json_end = full_response.rfind('}') + 1
            if json_start != -1 and json_end > json_start:
                requirements = json.loads(full_response[json_start:json_end])
            else:
                requirements = {"error": "Invalid response format", "raw": full_response}
            
            yield {
                "type": "complete",
                "agent": "system_requirement",
                "requirements": requirements,
                "message": "System requirements generated successfully!"
            }
        except json.JSONDecodeError as e:
            yield {
                "type": "error",
                "agent": "system_requirement",
                "error": f"Failed to parse requirements: {e}",
                "raw_response": full_response
            }