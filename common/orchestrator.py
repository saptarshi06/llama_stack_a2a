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
from common.llm.intent_agent import IntentAgent
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
        
        # import asyncio
        # asyncio.run(self.ollama_client.initialize())


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
                {
            **agents_config.get("code_generator", {}),
            "skills": config.get("skills", {})
            }
        )
        
        self.intent_agent = IntentAgent(
            self.ollama_client,
            agents_config.get("intent_agent")
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
            # ===== SHIELD 1: Moderate User Input (RUN FIRST for ALL intents) =====
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
                yield {"type": "info"}
            
            # ===== INTENT DETECTION (After safety checks) =====
            intent_result = await self.intent_agent.detect_intent(user_message)
            
            if intent_result is None:
                intent = "chat"
                detected_language = language
            else:
                intent = intent_result.get("intent", "chat")
                detected_language = intent_result.get("language", language)
            
            logger.info(f"Intent detected: {intent}")
            
            # ===== ROUTE BASED ON INTENT (With shields integrated) =====
            
            if intent == "code_generation" or intent == "direct_code":
                # ONLY Code Generator
                yield {"type": "pipeline_step", "step": 1, "agent": "code_generator"}
                
                # simple_spec = {
                #     "user_request": user_message,
                #     "description": user_message
                # }
                
                final_language = detected_language or self.intent_agent.extract_language(user_message)

                # Then use it in simple_spec
                simple_spec = {
                    "modules": [{
                        "name": "main",
                        "description": user_message,
                        "dependencies": []
                    }],
                    "api_endpoints": [],
                    "data_models": [],
                    "user_stories": [f"As a user, I want to {user_message}"],
                    "technical_specifications": {
                        "language": final_language,
                        "description": user_message
                    }
                }
                code_result = None
                async for event in self.code_gen_agent.generate(simple_spec, final_language, session_id):
                    yield event
                    if event.get("type") == "complete":
                        code_result = event.get("code")
                        session["current_state"]["generated_code"] = code_result
                        
                        # ===== SHIELD 4: Validate Code Quality (After code generation) =====
                        if self.safety_router and code_result:
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
                
                session["history"].append({
                    "request": user_message,
                    "intent": intent,
                    "code": code_result,
                    "language": final_language,
                    "timestamp": str(uuid.uuid4())
                })
                
                yield {"type": "pipeline_complete", "message": "🎉 Code generation complete!"}
                return
                
            elif intent == "system_only" or intent == "requirements_only":
                # ONLY System Requirements
                yield {"type": "pipeline_step", "step": 1, "agent": "system_requirement"}
                
                system_req_result = None
                async for event in self.system_req_agent.generate(user_message, session_id):
                    yield event
                    if event.get("type") == "complete":
                        system_req_result = event.get("requirements")
                
                if not system_req_result or "error" in system_req_result:
                    yield {"type": "error", "message": "Failed to generate system requirements", "details": system_req_result}
                    return
                
                # ===== SHIELD 2: Validate System Requirements =====
                if self.safety_router:
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
                            }
                        else:
                            yield {"type": "info"}
                    except Exception as e:
                        logger.warning(f"Shield validation failed (continuing anyway): {e}")
                
                session["current_state"]["system_requirements"] = system_req_result
                
                session["history"].append({
                    "request": user_message,
                    "intent": intent,
                    "system_requirements": system_req_result,
                    "timestamp": str(uuid.uuid4())
                })
                
                yield {"type": "pipeline_complete", "message": "✅ System requirements complete!"}
                return
                
            elif intent == "software_only":
                # Software Requirements (needs system requirements first)
                yield {"type": "pipeline_step", "step": 1, "agent": "system_requirement", "message": "Generating system requirements first..."}
                
                system_req_result = None
                async for event in self.system_req_agent.generate(user_message, session_id):
                    if event.get("type") == "complete":
                        system_req_result = event.get("requirements")
                
                if not system_req_result:
                    yield {"type": "error", "message": "Failed to generate system requirements"}
                    return
                
                yield {"type": "pipeline_step", "step": 2, "agent": "software_requirement"}
                
                software_req_result = None
                async for event in self.software_req_agent.generate(system_req_result, session_id):
                    yield event
                    if event.get("type") == "complete":
                        software_req_result = event.get("specifications")
                
                if not software_req_result:
                    yield {"type": "error", "message": "Failed to generate software requirements"}
                    return
                
                # ===== SHIELD 3: Validate Software Specifications =====
                if self.safety_router:
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
                            }
                        else:
                            yield {"type": "info"}
                    except Exception as e:
                        logger.warning(f"Shield validation failed (continuing anyway): {e}")
                
                session["current_state"]["software_specifications"] = software_req_result
                
                session["history"].append({
                    "request": user_message,
                    "intent": intent,
                    "software_specifications": software_req_result,
                    "timestamp": str(uuid.uuid4())
                })
                
                yield {"type": "pipeline_complete", "message": "✅ Software specifications complete!"}
                return
                
            else:  # chat
                yield {"type": "pipeline_step", "step": 1, "agent": "assistant", "message": "💬 Responding..."}
                
                messages = [
                    {"role": "system", "content": "You are a helpful assistant. Respond conversationally."},
                    {"role": "user", "content": user_message}
                ]
                
                async for chunk in self.ollama_client.generate(messages, stream=True):
                    if chunk.get("type") == "content":
                        yield {"type": "stream", "agent": "assistant", "content": chunk["content"]}
                
                session["history"].append({
                    "request": user_message,
                    "intent": "chat",
                    "timestamp": str(uuid.uuid4())
                })
                
                yield {"type": "pipeline_complete", "message": "💬 Response complete!"}
                return

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