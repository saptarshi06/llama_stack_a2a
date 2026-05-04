import logging
import uuid
import json
from typing import Dict, Any, AsyncIterator, Optional
from llama_stack.core.datatypes import SafetyConfig

# Llama Stack imports for shields
from llama_stack_api import (
    RunShieldRequest,
    RunModerationRequest,
)

# Llama Stack core components
from llama_stack.core.routers.safety import SafetyRouter
from llama_stack.core.routing_tables.shields import ShieldsRoutingTable

from common.llm.ollama_client import OllamaClient
from common.llm.system_req_agent import SystemRequirementAgent
from common.llm.software_req_agent import SoftwareRequirementAgent
from common.llm.code_gen_agent import CodeGeneratorAgent

logger = logging.getLogger(__name__)


class Orchestrator:
    """Orchestrates multi-agent workflow with Llama Stack safety shields"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.ollama_config = config.get("ollama", {})
        
        # Initialize Ollama client
        self.ollama_client = OllamaClient(
            base_url=self.ollama_config.get("base_url"),
            model=self.ollama_config.get("model")
        )
        
        # # Initialize Llama Stack Safety System
        # self.shields_routing_table = ShieldsRoutingTable()
        
        # # Create safety config with default shield
        # safety_config = SafetyConfig(
        #     default_shield_id="system_req_quality_shield"
        # )
        
        # self.safety_router = SafetyRouter(
        #     routing_table=self.shields_routing_table,
        #     safety_config=safety_config
        # )
        
        self.safety_router = None

        # Initialize agents
        agents_config = config.get("agents", {})

        self.system_req_agent = SystemRequirementAgent(
            self.ollama_client,
            agents_config.get("system_requirement", {})
        )
        self.software_req_agent = SoftwareRequirementAgent(
            self.ollama_client,
            agents_config.get("software_requirement", {})
        )
        self.code_gen_agent = CodeGeneratorAgent(
            self.ollama_client,
            agents_config.get("code_generator", {})
        )
        
        # Session management
        self.sessions: Dict[str, Dict[str, Any]] = {}
        
        # Register shields on initialization
        import asyncio
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(self._register_shields())
        finally:
            loop.close()
    
    async def _register_shields(self):
        """Register built-in shields with the safety router"""
        try:
            # Register shield for system requirements
            system_req_shield = RunShieldRequest(
                shield_id="system_req_quality_shield",
                messages=[]  # Will be populated during runtime
            )
            
            logger.info("Shields registered successfully")
        except Exception as e:
            logger.error(f"Failed to register shields: {e}")

    async def process_request(
        self,
        user_message: str,
        session_id: str,
        language: Optional[str] = None,
        stream: bool = True
    ) -> AsyncIterator[Dict[str, Any]]:
    
        # Create or get session
        if session_id not in self.sessions:
            self.sessions[session_id] = {
                "history": [],
                "current_state": {},
                "last_agent": None
            }
        
        session = self.sessions[session_id]
        
        try:
            # ===== SHIELD 1: Moderate User Input (SKIP if safety_router is None) =====
            if self.safety_router:
                yield {"type": "pipeline_start", "step": 0, "message": "🛡️ Running safety checks on input..."}
                
                moderation_request = RunModerationRequest(input=user_message)
                
                try:
                    moderation_result = await self.safety_router.run_moderation(moderation_request)
                    if hasattr(moderation_result, 'flagged') and moderation_result.flagged:
                        yield {
                            "type": "error",
                            "message": "User input flagged by safety system",
                            "categories": getattr(moderation_result, 'categories', []),
                            "shield_triggered": True
                        }
                        return
                except Exception as e:
                    logger.warning(f"Moderation check failed (continuing anyway): {e}")
                    yield {"type": "info", "message": "Safety check temporarily unavailable, proceeding..."}
            else:
                yield {"type": "info",
                        #"message": "🛡️ Safety system initializing (shields will be active soon)..."
                    }
            
            # ===== Step 1: Generate System Requirements =====
            yield {"type": "pipeline_step", "step": 1, "agent": "system_requirement", 
                   #"message": "🔍 System Requirement Agent analyzing request..."
                   }
            
            system_req_result = None
            async for event in self.system_req_agent.generate(user_message, session_id):
                yield event
                if event.get("type") == "complete":
                    system_req_result = event.get("requirements")
            
            if not system_req_result or "error" in system_req_result:
                yield {"type": "error", "message": "Failed to generate system requirements", "details": system_req_result}
                return
            
            # ===== SHIELD 2: Validate System Requirements (SKIP if no safety_router) =====
            if self.safety_router:
                yield {"type": "info",
                       #"message": "🛡️ Validating system requirements with safety shield..."
                       }
                
                shield_request = RunShieldRequest(
                    shield_id="system_req_quality_shield",
                    messages=[{
                        "role": "assistant",
                        "content": json.dumps(system_req_result, indent=2)
                    }]
                )
                
                try:
                    shield_response = await self.safety_router.run_shield(shield_request)
                    if shield_response and hasattr(shield_response, 'violation') and shield_response.violation:
                        yield {
                            "type": "warning",
                            "shield": "system_req_quality_shield",
                            "violations": shield_response.violation.details if hasattr(shield_response.violation, 'details') else str(shield_response.violation),
                            #"message": "⚠️ System requirements validation found issues, but continuing..."
                        }
                    else:
                        yield {"type": "info",
                               #"message": "✅ System requirements passed validation"
                               }
                except Exception as e:
                    logger.warning(f"Shield validation failed (continuing anyway): {e}")
            
            session["current_state"]["system_requirements"] = system_req_result
            
            # ===== Step 2: Generate Software Requirements =====
            yield {"type": "pipeline_step", "step": 2, "agent": "software_requirement",
                   #"message": "📝 Software Requirement Agent creating specifications..."
                   }
            
            software_req_result = None
            async for event in self.software_req_agent.generate(system_req_result, session_id):
                yield event
                if event.get("type") == "complete":
                    software_req_result = event.get("specifications")
            
            if not software_req_result or "error" in software_req_result:
                yield {"type": "error", "message": "Failed to generate software requirements", "details": software_req_result}
                return
            
            # ===== SHIELD 3: Validate Software Specifications (SKIP if no safety_router) =====
            if self.safety_router:
                yield {"type": "info",
                       #"message": "🛡️ Validating software specifications with safety shield..."
                       }
                
                shield_request = RunShieldRequest(
                    shield_id="software_spec_shield",
                    messages=[{
                        "role": "assistant",
                        "content": json.dumps(software_req_result, indent=2)
                    }]
                )
                
                try:
                    shield_response = await self.safety_router.run_shield(shield_request)
                    if shield_response and hasattr(shield_response, 'violation') and shield_response.violation:
                        yield {
                            "type": "warning",
                            "shield": "software_spec_shield",
                            "violations": shield_response.violation.details if hasattr(shield_response.violation, 'details') else str(shield_response.violation),
                            #"message": "⚠️ Software specifications need review, but continuing..."
                        }
                    else:
                        yield {"type": "info", 
                               #"message": "✅ Software specifications passed validation"
                               }
                except Exception as e:
                    logger.warning(f"Shield validation failed (continuing anyway): {e}")
            
            session["current_state"]["software_specifications"] = software_req_result
            
            # ===== Step 3: Generate Code =====
            if not language or language == "":
                language = "appropriate language based on requirements"
            
            yield {"type": "pipeline_step", "step": 3, "agent": "code_generator", 
                   #"message": f"💻 Code Generator Agent writing code..."
                   }
            
            code_result = None
            async for event in self.code_gen_agent.generate(software_req_result, language, session_id):
                yield event
                if event.get("type") == "complete":
                    code_result = event.get("code")
                    session["current_state"]["generated_code"] = code_result
                elif event.get("type") == "error" and event.get("out_of_skillset"):
                    yield event
                    return
            
            # ===== SHIELD 4: Validate Code Quality (SKIP if no safety_router) =====
            if self.safety_router and code_result:
                yield {"type": "info", 
                       #"message": "🛡️ Running code quality and security checks..."
                       }
                
                shield_request = RunShieldRequest(
                    shield_id="code_quality_shield",
                    messages=[{
                        "role": "assistant",
                        "content": json.dumps(code_result, indent=2)
                    }]
                )
                
                try:
                    shield_response = await self.safety_router.run_shield(shield_request)
                    if shield_response and hasattr(shield_response, 'violation') and shield_response.violation:
                        yield {
                            "type": "warning",
                            "shield": "code_quality_shield",
                            "violations": shield_response.violation.details if hasattr(shield_response.violation, 'details') else str(shield_response.violation),
                            "message": "⚠️ Code quality issues detected - review before production use"
                        }
                    else:
                        yield {"type": "info", "message": "✅ Code passed all quality and security checks"}
                except Exception as e:
                    logger.warning(f"Code quality check failed: {e}")
            
            # Save to history
            session["history"].append({
                "request": user_message,
                "system_requirements": system_req_result,
                "software_specifications": software_req_result,
                "code": code_result,
                "language": language,
                "timestamp": str(uuid.uuid4())
            })
            
            yield {"type": "pipeline_complete", "message": "🎉 All agents completed successfully!"}
            
        except Exception as e:
            logger.error(f"Orchestrator error: {e}")
            yield {"type": "error", "message": f"Orchestration failed: {str(e)}"}
        
    async def health_check(self) -> Dict[str, bool]:
        """Check health of all components including shields"""
        ollama_healthy = await self.ollama_client.health_check()
            
        return {
                "ollama": ollama_healthy,
                "system_req_agent": True,
                "software_req_agent": True,
                "code_gen_agent": True,
                "shields": self.safety_router is not None,
                "overall": ollama_healthy
            }
    
    def get_session_history(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get conversation history for a session"""
        return self.sessions.get(session_id)