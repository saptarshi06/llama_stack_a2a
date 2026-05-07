import json
import logging
from typing import Dict, Any, AsyncIterator, List, Optional
from .ollama_client import OllamaClient

logger = logging.getLogger(__name__)


class SkillsRegistry:
    """Registry for managing available coding skills/languages"""
    
    def __init__(self, config: Dict[str, Any]):
        self.supported_languages = config.get("supported_languages", ["python", "c", "cpp", "java", "assembly"])
        self.language_aliases = config.get("language_aliases", {})
    
    def validate_language(self, language: str) -> tuple[bool, str, Optional[str]]:
        """Validate if language is supported, return (is_supported, normalized_language, error_message)"""
        
        normalized = language.lower().strip()
        
        # Check aliases
        if normalized in self.language_aliases:
            normalized = self.language_aliases[normalized]
        
        if normalized in self.supported_languages:
            return True, normalized, None
        else:
            error_msg = f"Language '{language}' is not supported. Supported languages: {', '.join(self.supported_languages)}"
            # Suggest closest match
            suggestion = self._suggest_language(normalized)
            if suggestion:
                error_msg += f"\n\nDid you mean: {suggestion}?"
            return False, normalized, error_msg
    
    def _suggest_language(self, language: str) -> Optional[str]:
        """Suggest closest matching language"""
        import difflib
        matches = difflib.get_close_matches(language, self.supported_languages, n=1, cutoff=0.6)
        return matches[0] if matches else None
    
    def get_all_skills(self) -> List[str]:
        """Return list of all supported languages"""
        return self.supported_languages

class CodeGeneratorAgent:
    """Agent for generating code with language validation"""
    
    def __init__(self, ollama_client: OllamaClient, config: Dict[str, Any]):
        self.client = ollama_client
        self.config = config
        self.instructions = config.get("instructions", "")
        self.name = config.get("name", "Code Generator")
        self.skills_registry = SkillsRegistry(config.get("skills", {}))

    async def generate(
        self,
        specifications: Dict[str, Any],
        language: str,
        session_id: str
    ) -> AsyncIterator[Dict[str, Any]]:
        """Generate code based on specifications - LLM will handle language validation"""
        
        # Just pass the language to LLM - let it decide if supported
        messages = [
            {"role": "system", "content": self.instructions},
            {"role": "user", "content": f"Generate code in {language} (if you support it) from these specifications:\n{json.dumps(specifications, indent=2)}\n\nRequested Language: {language}\n\nIMPORTANT: If {language} is not in your supported languages list, respond with an error message clearly stating which languages you DO support."}
        ]
        
        full_response = ""
        
        async for chunk in self.client.generate(messages, stream=True):
            if chunk.get("type") == "content":
                full_response += chunk["content"]
                yield {
                    "type": "stream",
                    "agent": "code_generator",
                    "content": chunk["content"],
                    "message": f"Code Generator Agent is writing code..."
                }
            elif chunk.get("type") == "error":
                yield {
                    "type": "error",
                    "agent": "code_generator",
                    "error": chunk["error"]
                }
        
        # Parse response - LLM will handle language validation in its response
        try:
            json_start = full_response.find('{')
            json_end = full_response.rfind('}') + 1
            if json_start != -1 and json_end > json_start:
                code_output = json.loads(full_response[json_start:json_end])
                
                # Check if LLM returned an error about unsupported language
                if code_output.get("error") == "unsupported_language":
                    yield {
                        "type": "error",
                        "agent": "code_generator",
                        "error": code_output.get("message", f"Language not supported"),
                        "supported_languages": code_output.get("supported_languages", ["Python", "C", "C++", "Java", "Assembly"]),
                        "out_of_skillset": True
                    }
                    return
            else:
                code_output = {
                    "language": language,
                    "files": [{"filename": f"main.{self._get_extension(language)}", "content": full_response, "description": "Generated code"}],
                    "build_instructions": f"To run: Use appropriate compiler/interpreter",
                    "test_examples": ["Test the generated code"]
                }
            
            yield {
                "type": "complete",
                "agent": "code_generator",
                "code": code_output,
                "language": language,
                "message": f"✅ Code generated successfully!"
            }
        except json.JSONDecodeError as e:
            yield {
                "type": "error",
                "agent": "code_generator",
                "error": f"Failed to parse code output: {e}",
                "raw_code": full_response
            }
    
    def _get_extension(self, language: str) -> str:
        """Get file extension for language"""
        extensions = {
            "python": "py",
            "c": "c",
            "cpp": "cpp",
            "java": "java",
            "assembly": "asm"
        }
        return extensions.get(language, "txt")