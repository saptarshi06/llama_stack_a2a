import json
import logging
from typing import Dict, Any, AsyncIterator
from .ollama_client import OllamaClient

logger = logging.getLogger(__name__)


class SoftwareRequirementAgent:
    """Agent for generating detailed software requirements from system requirements"""
    
    def __init__(self, ollama_client: OllamaClient, config: Dict[str, Any]):
        self.client = ollama_client
        self.config = config
        self.instructions = config.get("instructions", "")
        self.name = config.get("name", "Software Requirement Engineer")
    
    async def generate(self, system_requirements: Dict[str, Any], session_id: str) -> AsyncIterator[Dict[str, Any]]:
        """Generate software requirements from system requirements"""
        
        messages = [
            {"role": "system", "content": self.instructions},
            {"role": "user", "content": f"Create software specifications from these system requirements:\n{json.dumps(system_requirements, indent=2)}"}
        ]
        
        full_response = ""
        
        async for chunk in self.client.generate(messages, stream=True):
            if chunk.get("type") == "content":
                full_response += chunk["content"]
                yield {
                    "type": "stream",
                    "agent": "software_requirement",
                    "content": chunk["content"],
                    "message": "Software Requirement Agent is creating specifications..."
                }
            elif chunk.get("type") == "error":
                yield {
                    "type": "error",
                    "agent": "software_requirement",
                    "error": chunk["error"]
                }
        
        # Parse JSON response
        try:
            json_start = full_response.find('{')
            json_end = full_response.rfind('}') + 1
            if json_start != -1 and json_end > json_start:
                specifications = json.loads(full_response[json_start:json_end])
            else:
                specifications = {"error": "Invalid response format", "raw": full_response}
            
            yield {
                "type": "complete",
                "agent": "software_requirement",
                "specifications": specifications,
                "message": "Software specifications generated successfully!"
            }
        except json.JSONDecodeError as e:
            yield {
                "type": "error",
                "agent": "software_requirement",
                "error": f"Failed to parse specifications: {e}"
            }