#!/usr/bin/env python3
"""
MCP Server for Multi-Agent System (No aiofiles dependency)
"""

import json
import logging
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
import os

from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
import mcp.server.stdio
import mcp.types as types

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize MCP Server
server = Server("multi-agent-tools")

# In-memory storage for session data (can be replaced with real DB)
session_data = {}
code_templates = {}
project_structure = {}


# ==================== HELPER FUNCTIONS ====================

async def async_write_file(filepath: str, content: str) -> bool:
    """Async file write using thread pool"""
    try:
        # Create directory if it doesn't exist
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        
        # Use asyncio.to_thread for file operations
        await asyncio.to_thread(_write_file_sync, filepath, content)
        return True
    except Exception as e:
        logger.error(f"Error writing file {filepath}: {e}")
        return False

def _write_file_sync(filepath: str, content: str):
    """Synchronous file write"""
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

async def async_read_file(filepath: str) -> str:
    """Async file read using thread pool"""
    try:
        return await asyncio.to_thread(_read_file_sync, filepath)
    except Exception as e:
        logger.error(f"Error reading file {filepath}: {e}")
        return ""

def _read_file_sync(filepath: str) -> str:
    """Synchronous file read"""
    with open(filepath, 'r', encoding='utf-8') as f:
        return f.read()


# ==================== TOOL DEFINITIONS ====================

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """List all available tools for all agents"""
    return [
        # System Requirement Agent Tools
        types.Tool(
            name="get_requirement_templates",
            description="Get predefined requirement templates for common system types",
            inputSchema={
                "type": "object",
                "properties": {
                    "system_type": {
                        "type": "string",
                        "enum": ["web_app", "api", "mobile_app", "desktop_app", "database"],
                        "description": "Type of system to get template for"
                    }
                },
                "required": ["system_type"]
            }
        ),
        
        types.Tool(
            name="validate_requirements",
            description="Validate system requirements for completeness and quality",
            inputSchema={
                "type": "object",
                "properties": {
                    "requirements": {
                        "type": "object",
                        "description": "Requirements object to validate"
                    }
                },
                "required": ["requirements"]
            }
        ),
        
        # Software Requirement Agent Tools
        types.Tool(
            name="get_software_architecture_patterns",
            description="Get architecture patterns for software specifications",
            inputSchema={
                "type": "object",
                "properties": {
                    "pattern_type": {
                        "type": "string",
                        "enum": ["microservices", "monolith", "event_driven", "layered", "hexagonal"],
                        "description": "Architecture pattern type"
                    }
                },
                "required": ["pattern_type"]
            }
        ),
        
        types.Tool(
            name="generate_api_spec",
            description="Generate OpenAPI/Swagger specification for APIs",
            inputSchema={
                "type": "object",
                "properties": {
                    "api_name": {"type": "string"},
                    "endpoints": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "path": {"type": "string"},
                                "method": {"type": "string"},
                                "description": {"type": "string"}
                            }
                        }
                    }
                },
                "required": ["api_name", "endpoints"]
            }
        ),
        
        # Code Generator Agent Tools
        types.Tool(
            name="get_code_template",
            description="Get code template for specific language and framework",
            inputSchema={
                "type": "object",
                "properties": {
                    "language": {
                        "type": "string",
                        "enum": ["python", "c", "cpp", "java", "assembly", "javascript", "typescript"],
                        "description": "Programming language"
                    },
                    "framework": {
                        "type": "string",
                        "description": "Framework (e.g., flask, fastapi, spring)"
                    },
                    "project_type": {
                        "type": "string",
                        "enum": ["api", "cli", "library", "web_app"],
                        "description": "Type of project"
                    }
                },
                "required": ["language", "project_type"]
            }
        ),
        
        types.Tool(
            name="save_generated_code",
            description="Save generated code to file system",
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {"type": "string"},
                    "filename": {"type": "string"},
                    "content": {"type": "string"},
                    "language": {"type": "string"}
                },
                "required": ["session_id", "filename", "content", "language"]
            }
        ),
        
        types.Tool(
            name="compile_code",
            description="Compile code (for compiled languages)",
            inputSchema={
                "type": "object",
                "properties": {
                    "language": {"type": "string"},
                    "filename": {"type": "string"},
                    "source_path": {"type": "string"}
                },
                "required": ["language", "filename", "source_path"]
            }
        ),
        
        # Intent Agent Tools
        types.Tool(
            name="analyze_intent_patterns",
            description="Analyze user message against known intent patterns",
            inputSchema={
                "type": "object",
                "properties": {
                    "message": {"type": "string"},
                    "context": {"type": "string"}
                },
                "required": ["message"]
            }
        ),
        
        # Orchestrator Tools
        types.Tool(
            name="save_conversation",
            description="Save conversation session to persistent storage",
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {"type": "string"},
                    "messages": {"type": "array"},
                    "timestamp": {"type": "string"}
                },
                "required": ["session_id", "messages"]
            }
        ),
        
        types.Tool(
            name="get_conversation_history",
            description="Retrieve conversation history for a session",
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {"type": "string"},
                    "limit": {"type": "integer", "default": 10}
                },
                "required": ["session_id"]
            }
        ),
        
        # Database Integration Tools
        types.Tool(
            name="query_code_repository",
            description="Query the code repository for similar solutions",
            inputSchema={
                "type": "object",
                "properties": {
                    "language": {"type": "string"},
                    "functionality": {"type": "string"},
                    "limit": {"type": "integer", "default": 5}
                },
                "required": ["language", "functionality"]
            }
        ),
        
        types.Tool(
            name="store_code_artifact",
            description="Store generated code artifact in database",
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {"type": "string"},
                    "code_data": {"type": "object"},
                    "metadata": {"type": "object"}
                },
                "required": ["session_id", "code_data"]
            }
        ),
        
        # Build & Test Tools
        types.Tool(
            name="run_tests",
            description="Run tests for generated code",
            inputSchema={
                "type": "object",
                "properties": {
                    "language": {"type": "string"},
                    "test_file": {"type": "string"},
                    "test_path": {"type": "string"}
                },
                "required": ["language", "test_file", "test_path"]
            }
        ),
        
        types.Tool(
            name="generate_documentation",
            description="Generate documentation from code",
            inputSchema={
                "type": "object",
                "properties": {
                    "language": {"type": "string"},
                    "source_code": {"type": "string"},
                    "output_format": {"type": "string", "enum": ["markdown", "html", "rst"], "default": "markdown"}
                },
                "required": ["language", "source_code"]
            }
        ),
        
        # New: Version Control Tool
        types.Tool(
            name="version_code",
            description="Version control for generated code",
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {"type": "string"},
                    "code_data": {"type": "object"},
                    "version_tag": {"type": "string"}
                },
                "required": ["session_id", "code_data"]
            }
        ),
        
        # New: Code Review Tool
        types.Tool(
            name="review_code",
            description="Perform code review on generated code",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {"type": "string"},
                    "language": {"type": "string"}
                },
                "required": ["code", "language"]
            }
        )
    ]


# ==================== TOOL IMPLEMENTATIONS ====================

@server.call_tool()
async def handle_call_tool(
    name: str, 
    arguments: dict | None
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """Handle tool execution"""
    
    try:
        if not arguments:
            arguments = {}
            
        if name == "get_requirement_templates":
            return await handle_get_requirement_templates(arguments)
        
        elif name == "validate_requirements":
            return await handle_validate_requirements(arguments)
        
        elif name == "get_software_architecture_patterns":
            return await handle_get_architecture_patterns(arguments)
        
        elif name == "generate_api_spec":
            return await handle_generate_api_spec(arguments)
        
        elif name == "get_code_template":
            return await handle_get_code_template(arguments)
        
        elif name == "save_generated_code":
            return await handle_save_generated_code(arguments)
        
        elif name == "compile_code":
            return await handle_compile_code(arguments)
        
        elif name == "analyze_intent_patterns":
            return await handle_analyze_intent(arguments)
        
        elif name == "save_conversation":
            return await handle_save_conversation(arguments)
        
        elif name == "get_conversation_history":
            return await handle_get_history(arguments)
        
        elif name == "query_code_repository":
            return await handle_query_repository(arguments)
        
        elif name == "store_code_artifact":
            return await handle_store_artifact(arguments)
        
        elif name == "run_tests":
            return await handle_run_tests(arguments)
        
        elif name == "generate_documentation":
            return await handle_generate_doc(arguments)
        
        elif name == "version_code":
            return await handle_version_code(arguments)
        
        elif name == "review_code":
            return await handle_review_code(arguments)
        
        else:
            return [types.TextContent(
                type="text",
                text=f"Unknown tool: {name}"
            )]
    
    except Exception as e:
        logger.error(f"Error executing tool {name}: {e}")
        return [types.TextContent(
            type="text",
            text=f"Error: {str(e)}"
        )]


# Tool-specific handlers
async def handle_get_requirement_templates(args: dict) -> list:
    system_type = args.get("system_type", "web_app")
    
    templates = {
        "web_app": {
            "system_name": "Web Application Template",
            "functional_requirements": [
                "User authentication and authorization",
                "Responsive user interface",
                "Database integration",
                "Input validation",
                "Error handling",
                "Logging and monitoring",
                "Session management"
            ],
            "non_functional_requirements": [
                "Response time < 200ms",
                "99.9% uptime",
                "Support 1000 concurrent users",
                "HTTPS encryption",
                "Accessibility compliance"
            ]
        },
        "api": {
            "system_name": "REST API Template",
            "functional_requirements": [
                "CRUD operations",
                "Authentication via JWT",
                "Rate limiting",
                "Request validation",
                "Response caching",
                "API versioning"
            ],
            "non_functional_requirements": [
                "Latency < 100ms",
                "Rate: 1000 requests/second",
                "OpenAPI documentation",
                "CORS support"
            ]
        },
        "database": {
            "system_name": "Database System Template",
            "functional_requirements": [
                "Data storage and retrieval",
                "Query optimization",
                "Backup and recovery",
                "Data integrity constraints",
                "Transaction support"
            ],
            "non_functional_requirements": [
                "ACID compliance",
                "Response time < 50ms",
                "99.99% availability",
                "Data encryption at rest"
            ]
        }
    }
    
    result = templates.get(system_type, templates["web_app"])
    return [types.TextContent(
        type="text",
        text=json.dumps(result, indent=2)
    )]


async def handle_validate_requirements(args: dict) -> list:
    requirements = args.get("requirements", {})
    
    issues = []
    warnings = []
    
    # Check required fields
    required_fields = ["functional_requirements", "non_functional_requirements"]
    for field in required_fields:
        if field not in requirements:
            issues.append(f"Missing required field: {field}")
    
    # Check functional requirements
    func_reqs = requirements.get("functional_requirements", [])
    if len(func_reqs) < 3:
        warnings.append("Too few functional requirements (minimum 3 recommended)")
    
    # Check non-functional requirements
    non_func_reqs = requirements.get("non_functional_requirements", [])
    if len(non_func_reqs) < 2:
        warnings.append("Too few non-functional requirements (minimum 2 recommended)")
    
    validation_result = {
        "valid": len(issues) == 0,
        "issues": issues,
        "warnings": warnings,
        "quality_score": max(0, 10 - len(issues) * 2 - len(warnings))
    }
    
    return [types.TextContent(
        type="text",
        text=json.dumps(validation_result, indent=2)
    )]


async def handle_get_architecture_patterns(args: dict) -> list:
    pattern_type = args.get("pattern_type", "microservices")
    
    patterns = {
        "microservices": {
            "name": "Microservices Architecture",
            "description": "Distributed services communicating via APIs",
            "pros": ["Independent deployment", "Technology flexibility", "Scalability"],
            "cons": ["Network complexity", "Data consistency", "Operational overhead"],
            "when_to_use": ["Large teams", "Complex domains", "Need for independent scaling"]
        },
        "monolith": {
            "name": "Monolithic Architecture",
            "description": "Single unified application",
            "pros": ["Simple deployment", "Easy testing", "Low latency"],
            "cons": ["Scaling limitations", "Tight coupling", "Long build times"],
            "when_to_use": ["Small teams", "Simple domains", "Rapid prototyping"]
        },
        "event_driven": {
            "name": "Event-Driven Architecture",
            "description": "Components communicate via events",
            "pros": ["Loose coupling", "Scalability", "Real-time processing"],
            "cons": ["Complexity", "Event ordering", "Debugging difficulty"],
            "when_to_use": ["Real-time systems", "IoT applications", "Async processing"]
        }
    }
    
    result = patterns.get(pattern_type, patterns["microservices"])
    return [types.TextContent(
        type="text",
        text=json.dumps(result, indent=2)
    )]


async def handle_generate_api_spec(args: dict) -> list:
    api_name = args.get("api_name", "MyAPI")
    endpoints = args.get("endpoints", [])
    
    spec = {
        "openapi": "3.0.0",
        "info": {
            "title": api_name,
            "version": "1.0.0",
            "description": f"API specification for {api_name}"
        },
        "paths": {}
    }
    
    for endpoint in endpoints:
        path = endpoint.get("path", "/")
        method = endpoint.get("method", "get").lower()
        description = endpoint.get("description", "")
        
        if path not in spec["paths"]:
            spec["paths"][path] = {}
        
        spec["paths"][path][method] = {
            "summary": description,
            "responses": {
                "200": {
                    "description": "Successful response"
                }
            }
        }
    
    return [types.TextContent(
        type="text",
        text=json.dumps(spec, indent=2)
    )]


async def handle_get_code_template(args: dict) -> list:
    language = args.get("language", "python")
    project_type = args.get("project_type", "api")
    framework = args.get("framework", None)
    
    templates = {
        "python": {
            "api": {
                "main.py": """from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy"}), 200

@app.route('/api/v1/resource', methods=['GET'])
def get_resource():
    return jsonify({"message": "Resource retrieved"}), 200

@app.route('/api/v1/resource', methods=['POST'])
def create_resource():
    data = request.json
    return jsonify({"message": "Resource created", "data": data}), 201

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
""",
                "requirements.txt": "flask\nflask-cors\n",
                "README.md": f"# {project_type.capitalize()} Application\n\n## Setup\n```bash\npip install -r requirements.txt\n```\n\n## Run\n```bash\npython main.py\n```"
            },
            "cli": {
                "main.py": """import argparse
import sys

def main():
    parser = argparse.ArgumentParser(description='CLI Application')
    parser.add_argument('--input', '-i', help='Input file')
    parser.add_argument('--output', '-o', help='Output file')
    
    args = parser.parse_args()
    
    if args.input:
        print(f"Processing {args.input}")
    
    if args.output:
        print(f"Writing to {args.output}")

if __name__ == '__main__':
    main()
""",
                "requirements.txt": "",
                "README.md": "# CLI Application\n\n## Usage\n```bash\npython main.py --input data.txt --output results.txt\n```"
            }
        },
        "javascript": {
            "api": {
                "server.js": """const express = require('express');
const app = express();
const port = 3000;

app.use(express.json());

app.get('/health', (req, res) => {
    res.json({ status: 'healthy' });
});

app.get('/api/v1/resource', (req, res) => {
    res.json({ message: 'Resource retrieved' });
});

app.post('/api/v1/resource', (req, res) => {
    const data = req.body;
    res.status(201).json({ message: 'Resource created', data });
});

app.listen(port, () => {
    console.log(`Server running at http://localhost:${port}`);
});
""",
                "package.json": """{
  "name": "api-app",
  "version": "1.0.0",
  "description": "REST API application",
  "main": "server.js",
  "scripts": {
    "start": "node server.js"
  },
  "dependencies": {
    "express": "^4.18.2"
  }
}""",
                "README.md": "# API Application\n\n## Setup\n```bash\nnpm install\n```\n\n## Run\n```bash\nnpm start\n```"
            }
        },
        "java": {
            "api": {
                "Main.java": """import com.sun.net.httpserver.HttpServer;
import java.io.IOException;
import java.net.InetSocketAddress;

public class Main {
    public static void main(String[] args) throws IOException {
        HttpServer server = HttpServer.create(new InetSocketAddress(8080), 0);
        
        server.createContext("/health", exchange -> {
            String response = "{\"status\": \"healthy\"}";
            exchange.sendResponseHeaders(200, response.length());
            exchange.getResponseBody().write(response.getBytes());
            exchange.close();
        });
        
        server.setExecutor(null);
        server.start();
        System.out.println("Server started on port 8080");
    }
}
""",
                "pom.xml": """<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
    <modelVersion>4.0.0</modelVersion>
    <groupId>com.example</groupId>
    <artifactId>api-app</artifactId>
    <version>1.0.0</version>
</project>"""
            }
        }
    }
    
    # Add framework-specific templates if specified
    if framework and language == "python":
        if framework == "fastapi":
            templates["python"]["api"]["main.py"] = """from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any

app = FastAPI(title="My API", version="1.0.0")

class Item(BaseModel):
    name: str
    description: str = None

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.get("/api/v1/resource")
async def get_resource():
    return {"message": "Resource retrieved"}

@app.post("/api/v1/resource")
async def create_resource(item: Item):
    return {"message": "Resource created", "data": item.dict()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
"""
            templates["python"]["api"]["requirements.txt"] = "fastapi\nuvicorn\npydantic\n"
    
    result = templates.get(language, {}).get(project_type, {})
    if not result:
        result = {"error": f"No template found for {language}/{project_type}"}
    
    return [types.TextContent(
        type="text",
        text=json.dumps(result, indent=2)
    )]


async def handle_save_generated_code(args: dict) -> list:
    session_id = args.get("session_id", "default")
    filename = args.get("filename", "output.txt")
    content = args.get("content", "")
    language = args.get("language", "unknown")
    
    # Create session directory
    session_dir = Path(f"./generated_code/{session_id}")
    
    # Save file using async file write
    file_path = session_dir / filename
    success = await async_write_file(str(file_path), content)
    
    result = {
        "saved": success,
        "path": str(file_path),
        "filename": filename,
        "language": language,
        "size": len(content)
    }
    
    return [types.TextContent(
        type="text",
        text=json.dumps(result, indent=2)
    )]


async def handle_compile_code(args: dict) -> list:
    language = args.get("language")
    filename = args.get("filename")
    source_path = args.get("source_path")
    
    compile_commands = {
        "c": f"gcc {source_path}/{filename} -o {source_path}/program",
        "cpp": f"g++ {source_path}/{filename} -o {source_path}/program",
        "java": f"javac {source_path}/{filename}"
    }
    
    if language not in compile_commands:
        result = {"error": f"No compilation command for {language}"}
    else:
        result = {
            "command": compile_commands[language],
            "language": language,
            "output": "Compilation command generated (simulated)"
        }
    
    return [types.TextContent(
        type="text",
        text=json.dumps(result, indent=2)
    )]


async def handle_analyze_intent(args: dict) -> list:
    message = args.get("message", "").lower()
    context = args.get("context", "")
    
    patterns = {
        "code_generation": ["write code", "generate code", "create a", "build a", "develop a", "implement"],
        "requirements_only": ["requirements", "specs", "what do i need", "prerequisites"],
        "software_only": ["software spec", "design document", "architecture"],
        "system_only": ["system requirements", "system design", "high level design"],
        "chat": ["hello", "hi", "how are you", "help"]
    }
    
    detected_intent = "chat"
    confidence = 0.0
    
    for intent, keywords in patterns.items():
        for keyword in keywords:
            if keyword in message:
                detected_intent = intent
                confidence = 0.8
                break
        if confidence > 0:
            break
    
    # Extract language hint
    languages = ["python", "java", "c++", "javascript", "typescript"]
    detected_language = None
    for lang in languages:
        if lang in message:
            detected_language = lang
            break
    
    result = {
        "intent": detected_intent,
        "confidence": confidence,
        "detected_language": detected_language,
        "message_length": len(message)
    }
    
    return [types.TextContent(
        type="text",
        text=json.dumps(result, indent=2)
    )]


async def handle_save_conversation(args: dict) -> list:
    session_id = args.get("session_id", "default")
    messages = args.get("messages", [])
    timestamp = args.get("timestamp", datetime.now().isoformat())
    
    # Store in memory (replace with real DB)
    if session_id not in session_data:
        session_data[session_id] = []
    
    session_data[session_id].append({
        "timestamp": timestamp,
        "conversation": messages
    })
    
    # Also save to file for persistence
    session_file = Path(f"./sessions/{session_id}.json")
    await async_write_file(str(session_file), json.dumps(session_data[session_id], indent=2))
    
    result = {
        "saved": True,
        "session_id": session_id,
        "total_messages": len(messages)
    }
    
    return [types.TextContent(
        type="text",
        text=json.dumps(result, indent=2)
    )]


async def handle_get_history(args: dict) -> list:
    session_id = args.get("session_id", "default")
    limit = args.get("limit", 10)
    
    # Try to load from memory first
    history = session_data.get(session_id, [])
    
    # If not in memory, try to load from file
    if not history:
        session_file = Path(f"./sessions/{session_id}.json")
        if session_file.exists():
            content = await async_read_file(str(session_file))
            if content:
                history = json.loads(content)
                session_data[session_id] = history
    
    recent = history[-limit:] if history else []
    
    result = {
        "session_id": session_id,
        "history": recent,
        "total": len(history)
    }
    
    return [types.TextContent(
        type="text",
        text=json.dumps(result, indent=2)
    )]


async def handle_query_repository(args: dict) -> list:
    language = args.get("language")
    functionality = args.get("functionality")
    limit = args.get("limit", 5)
    
    # Simulated repository lookup
    results = []
    for i in range(min(limit, 3)):
        results.append({
            "id": f"example_{i}",
            "language": language,
            "functionality": functionality,
            "description": f"Example {functionality} implementation in {language}",
            "code_snippet": f"# Sample code for {functionality}\n# This is a placeholder for actual repository query"
        })
    
    return [types.TextContent(
        type="text",
        text=json.dumps({"results": results, "count": len(results)}, indent=2)
    )]


async def handle_store_artifact(args: dict) -> list:
    session_id = args.get("session_id", "default")
    code_data = args.get("code_data", {})
    metadata = args.get("metadata", {})
    
    # Store in memory (replace with real DB)
    artifact_id = f"artifact_{len(code_templates)}"
    code_templates[artifact_id] = {
        "session_id": session_id,
        "code": code_data,
        "metadata": metadata,
        "timestamp": datetime.now().isoformat()
    }
    
    # Save to file
    artifact_file = Path(f"./artifacts/{artifact_id}.json")
    await async_write_file(str(artifact_file), json.dumps(code_templates[artifact_id], indent=2))
    
    result = {
        "stored": True,
        "artifact_id": artifact_id,
        "session_id": session_id
    }
    
    return [types.TextContent(
        type="text",
        text=json.dumps(result, indent=2)
    )]


async def handle_run_tests(args: dict) -> list:
    language = args.get("language")
    test_file = args.get("test_file")
    test_path = args.get("test_path")
    
    # Simulate test execution
    result = {
        "language": language,
        "test_file": test_file,
        "total_tests": 5,
        "passed": 4,
        "failed": 1,
        "coverage": 85.5,
        "results": [
            {"name": "test_case_1", "status": "PASSED", "duration": 0.01},
            {"name": "test_case_2", "status": "PASSED", "duration": 0.02},
            {"name": "test_case_3", "status": "FAILED", "duration": 0.015, "error": "AssertionError: Expected True, got False"},
            {"name": "test_case_4", "status": "PASSED", "duration": 0.01},
            {"name": "test_case_5", "status": "PASSED", "duration": 0.008}
        ]
    }
    
    return [types.TextContent(
        type="text",
        text=json.dumps(result, indent=2)
    )]


