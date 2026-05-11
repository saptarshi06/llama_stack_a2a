import json
import logging
from typing import Dict, Any, Optional
from .ollama_client import OllamaClient

logger = logging.getLogger(__name__)


class IntentAgent:
    """Agent to detect user intent and route to appropriate agents"""
    
    def __init__(self, ollama_client: OllamaClient, config: Dict[str, Any]):
        self.client = ollama_client
        self.config = config
        self.instructions = config.get("instructions", "")
        self.name = config.get("name", "Intent Detection Agent")
   
    async def detect_intent(self, user_message: str) -> Optional[Dict[str, Any]]:
        """Detect intent from user message and return routing decision.
        
        Returns:
            Dict with intent data, or None if parsing failed
        """
        
        messages = [
            {"role": "system", "content": self.instructions},
            {"role": "user", "content": user_message}
        ]
        
        full_response = ""
        async for chunk in self.client.generate(messages, stream=True):
            if chunk.get("type") == "content":
                full_response += chunk["content"]
        
        # Parse JSON response
        try:
            # Try to extract JSON from response
            json_start = full_response.find('{')
            json_end = full_response.rfind('}') + 1
            
            if json_start != -1 and json_end > json_start:
                intent_data = json.loads(full_response[json_start:json_end])
                
                # Validate required fields
                if "intent" not in intent_data:
                    logger.warning(f"Intent data missing 'intent' field: {intent_data}")
                    return None
                
                # Validate intent type is valid
                valid_intents = ["code_generation", "software_only", "system_only", "others"]
                if intent_data["intent"] not in valid_intents:
                    logger.warning(f"Invalid intent type: {intent_data['intent']}")
                
                return intent_data
            else:
                logger.warning(f"No JSON found in intent response: {full_response[:200]}")
                return None
                
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse intent JSON: {e}, Response: {full_response[:200]}")
            return None
    
    def _get_agents_for_intent(self, intent: str) -> list:
        """Get default agents needed for a given intent"""
        agent_map = {
            "code_generation": ["code_gen"],
            "software_only": ["software_req"],
            "system_only": ["system_req"]
        }
        return agent_map.get(intent, [])
    
    def extract_language(self, user_message: str) -> Optional[str]:
        """Extract programming language from user message (simple keyword matching)"""
        message_lower = user_message.lower()
        languages = {
            "python": ["python", "py"],
            "c": ["c language", "c code", " plain c"],
            "cpp": ["c++", "cpp", "c plus plus"],
            "java": ["java"],
            "assembly": ["assembly", "asm"]
        }
        
        for lang, keywords in languages.items():
            for keyword in keywords:
                if keyword in message_lower:
                    return lang
        return None