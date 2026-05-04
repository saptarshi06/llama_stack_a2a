# Copyright (c) Meta Platforms, Inc. and affiliates.
# Based on Llama Stack AsyncAgent pattern

import json
import logging
from typing import AsyncIterator, Dict, Any, Optional
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


class OllamaClient:
    """Wrapper for Ollama with OpenAI-compatible API following Llama Stack patterns"""
    
    def __init__(self, base_url: str = "http://localhost:11434/v1", model: str = "llama3.2:3b"):
        self.client = AsyncOpenAI(
            base_url=base_url,
            api_key="ollama",  # Required but not used by Ollama
            timeout=60.0
        )
        self.model = model
    
    async def generate(
        self,
        messages: list[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2048,
        stream: bool = True,
        tools: Optional[list] = None
    ) -> AsyncIterator[Dict[str, Any]]:
        """Generate response following AsyncAgent pattern - ALWAYS returns async iterator"""
        
        try:
            if stream:
                response_stream = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=True,
                    tools=tools or []
                )
                async for chunk in response_stream:
                    if chunk.choices[0].delta.content:
                        yield {"type": "content", "content": chunk.choices[0].delta.content}
                    elif chunk.choices[0].delta.tool_calls:
                        yield {"type": "tool_call", "tool_calls": chunk.choices[0].delta.tool_calls}
            else:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=False,
                    tools=tools or []
                )
                yield {"type": "complete", "content": response.choices[0].message.content}
        except Exception as e:
            logger.error(f"Ollama generation error: {str(e)}")
            yield {"type": "error", "error": str(e)}
    
    async def generate_non_streaming(
        self,
        messages: list[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2048
    ) -> Dict[str, Any]:
        """Non-streaming version that returns a single dict"""
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=False
            )
            return {"type": "complete", "content": response.choices[0].message.content}
        except Exception as e:
            logger.error(f"Ollama generation error: {e}")
            return {"type": "error", "error": str(e)}
    
    async def health_check(self) -> bool:
        """Check if Ollama is running and model is available"""
        try:
            response = await self.client.models.list()
            models = [model.id for model in response.data]
            return self.model in models
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False