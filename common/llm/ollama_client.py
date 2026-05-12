import json
import logging
from typing import AsyncIterator, Dict, Any, Optional
from openai import AsyncOpenAI
from common.mcp.mcp_client import MCPClient
from common.mcp.tool_registry import TOOLS

logger = logging.getLogger(__name__)


class OllamaClient:
    """Wrapper for Ollama with OpenAI-compatible API following Llama Stack patterns"""
    
    def __init__(self, base_url: str = "http://localhost:11434/v1", model: str = "llama3.2:3b"):
        self.client = AsyncOpenAI(
            base_url=base_url,
            api_key="ollama",  # Required but not used by Ollama
            timeout=60.0
        )
        self.mcp_client = MCPClient()
        self.model = model
    
    async def initialize(self):
        await self.mcp_client.connect()


    # async def generate(
    #     self,
    #     messages: list[Dict[str, str]],
    #     temperature: float = 0.7,
    #     max_tokens: int = 2048,
    #     stream: bool = True,
    #     tools: Optional[list] = None
    # ) -> AsyncIterator[Dict[str, Any]]:
    #     """Generate response following AsyncAgent pattern - ALWAYS returns async iterator"""
        
    #     try:
    #         if stream:
    #             response_stream = await self.client.chat.completions.create(
    #                 model=self.model,
    #                 messages=messages,
    #                 temperature=temperature,
    #                 max_tokens=max_tokens,
    #                 stream=True,
    #                 tools=tools or []
    #             )
    #             async for chunk in response_stream:
    #                 if chunk.choices[0].delta.content:
    #                     yield {"type": "content", "content": chunk.choices[0].delta.content}
    #                 elif chunk.choices[0].delta.tool_calls:
    #                     yield {"type": "tool_call", "tool_calls": chunk.choices[0].delta.tool_calls}
    #         else:
    #             response = await self.client.chat.completions.create(
    #                 model=self.model,
    #                 messages=messages,
    #                 temperature=temperature,
    #                 max_tokens=max_tokens,
    #                 stream=False,
    #                 tools=tools or []
    #             )
    #             yield {"type": "complete", "content": response.choices[0].message.content}
    #     except Exception as e:
    #         logger.error(f"Ollama generation error: {str(e)}")
    #         yield {"type": "error", "error": str(e)}
    

    async def generate_non_streaming(
        self,
        messages: list[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2048,
        #tools: Optional[list] = None
    ) -> Dict[str, Any]:
        """Non-streaming version that returns a single dict"""
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=False,
                tools=TOOLS,
                tool_choice="auto"
            )

            message = response.choices[0].message
            if message.tool_calls:
                messages.append({
                    "role": "assistant",
                    "content": message.content,
                    "tool_calls": [
                        {
                            "id": tool_call.id,
                            "type": "function",
                            "function": {
                                "name": tool_call.function.name,
                                "arguments": tool_call.function.arguments
                            }
                        }
                        for tool_call in message.tool_calls
                    ]
                })

                for tool_call in message.tool_calls:
                    tool_name = tool_call.function.name
                    arguments = json.loads(
                        tool_call.function.arguments
                    )

                    tool_result = await self.mcp_client.call_tool(
                        tool_name,
                        arguments
                    )

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": tool_name,
                        "content": str(tool_result)
                    })
                
                final_response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=False
                )

                return{
                    "type": "complete",
                    "content": final_response.choices[0].message.content
                }

            return {"type": "complete", "content": final_response.choices[0].message.content}
        
        except Exception as e:
            logger.error(f"Ollama generation error: {e}")
            return {"type": "error", "error": str(e)}
    
    async def generate(
        self,
        messages: list[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2048,
        stream: bool = True,
        tools: Optional[list] = TOOLS
    ) -> AsyncIterator[Dict[str, Any]]:
        """Generate response, automatically handling tool calls if tools provided.
        
        Always yields streaming chunks like {'type': 'content', 'content': '...'}
        but handles internal tool execution transparently.
        """
        if not tools:
            # No tools – pure streaming, original behaviour
            async for chunk in self._raw_stream(messages, temperature, max_tokens):
                yield chunk
            return

        # Tools provided – we may need to call them
        # First, try a non-streaming call to see if model wants tools
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=False,
                tools=TOOLS,
                tool_choice="auto"
            )
        except Exception as e:
            logger.error(f"Initial tool check failed: {e}")
            yield {"type": "error", "error": str(e)}
            return

        msg = response.choices[0].message
        if not msg.tool_calls:
            # No tool calls – the model replied directly (unlikely with tool_choice='auto', but handle)
            # Stream the content (which may be empty) by re‑prompting without tools to get stream
            # Or simply yield the static content as a single chunk
            if msg.content:
                yield {"type": "content", "content": msg.content}
            yield {"type": "complete"}  # signal end
            return

        # ---- Tool calling loop ----
        # Append assistant message with tool calls to conversation
        assistant_message = {
            "role": "assistant",
            "content": msg.content,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    }
                }
                for tc in msg.tool_calls
            ]
        }
        messages.append(assistant_message)

        # Execute each tool call and add results
        for tc in msg.tool_calls:
            tool_name = tc.function.name
            try:
                args = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                args = {}  # fallback
            try:
                tool_result = await self.mcp_client.call_tool(tool_name, args)
            except Exception as e:
                tool_result = {"status": "error", "message": str(e)}
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "name": tool_name,
                "content": json.dumps(tool_result)   # ensure string
            })

        # Now get final response from the model (with tool outcomes) – STREAM it
        try:
            async for chunk in self._raw_stream(messages, temperature, max_tokens):
                yield chunk
        except Exception as e:
            logger.error(f"Final streaming failed: {e}")
            yield {"type": "error", "error": str(e)}

    async def _raw_stream(self, messages, temperature, max_tokens):
        """Internal helper: yield content chunks from a streaming API call."""
        try:
            stream_resp = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
                tools=[]   # no tools in stream, already handled
            )
            async for chunk in stream_resp:
                if chunk.choices[0].delta.content:
                    yield {"type": "content", "content": chunk.choices[0].delta.content}
            yield {"type": "complete"}
        except Exception as e:
            logger.error(f"Streaming error: {e}")
            yield {"type": "error", "error": str(e)}
    
    async def health_check(self) -> bool:
        """Check if Ollama is running and model is available"""
        try:
            response = await self.client.models.list()
            models = [model.id for model in response.data]
            return self.model in models
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False