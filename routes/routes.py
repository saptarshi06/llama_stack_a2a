# Copyright (c) Meta Platforms, Inc. and affiliates.
# Flask Routes for Multi-Agent System

import json
import logging
from flask import Blueprint, request, Response, stream_with_context, jsonify
from common.orchestrator import Orchestrator
import yaml
import uuid
logger = logging.getLogger(__name__)

# Load configuration
with open("ollama_config.yaml", "r") as f:
    config = yaml.safe_load(f)

# Initialize orchestrator (singleton)
orchestrator = Orchestrator(config)

# Create blueprint
api_bp = Blueprint("api", __name__)


@api_bp.route("/chat", methods=["POST"])
def chat():
    """Handle chat requests with streaming response"""
    data = request.json
    session_id = data.get("session_id", "default")
    user_message = data.get("message", "")
    if session_id == "default":
        session_id = str(uuid.uuid4())
    #session_id = data.get("session_id")
    language = data.get("language", None)
    
    if not user_message:
        return jsonify({"error": "No message provided"}), 400
    
    def generate():
        """Generate streaming response"""
        import asyncio
        
        # Create async generator function
        async def async_generator():
            async for event in orchestrator.process_request(user_message, session_id, language):
                yield f"data: {json.dumps(event)}\n\n"
        
        # Run async generator in event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            async_gen = async_generator()
            while True:
                try:
                    # Get next item from async generator
                    item = loop.run_until_complete(async_gen.__anext__())
                    yield item
                except StopAsyncIteration:
                    break
        finally:
            loop.close()
    
    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"
        }
    )


@api_bp.route("/health", methods=["GET"])
def health():
    """Health check endpoint"""
    import asyncio
    
    async def check():
        return await orchestrator.health_check()
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        health_status = loop.run_until_complete(check())
    finally:
        loop.close()
    
    return jsonify(health_status)


@api_bp.route("/skills", methods=["GET"])
def get_skills():
    """Get all available skills/languages"""
    from common.llm.code_gen_agent import SkillsRegistry
    
    skills_config = config.get("skills", {})
    registry = SkillsRegistry(skills_config)
    
    return jsonify({
        "supported_languages": registry.get_all_skills(),
        "aliases": skills_config.get("language_aliases", {})
    })


@api_bp.route("/session/<session_id>/history", methods=["GET"])
def get_session_history(session_id: str):
    """Get conversation history for a session"""
    if session_id in orchestrator.sessions:
        return jsonify({
            "session_id": session_id,
            "history": orchestrator.sessions[session_id]["history"]
        })
    else:
        return jsonify({"error": "Session not found"}), 404