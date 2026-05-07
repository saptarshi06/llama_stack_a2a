from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp import ClientSession


class MCPClient:
    def __init__(self):
        self.session = None
        self.stdio_context = None

    async def connect(self):
        # read, write = await stdio_client(
        #     command="python",
        #     args=["mcp_server/server.py"]
        # )

        server_params = StdioServerParameters(
            command="python",
            args=["mcp_server/server.py"]
        )

        self.stdio_context = stdio_client(server_params)

        read, write = await self.stdio_context.__aenter__()
        self.session = ClientSession(read, write)
        await self.session.initialize()

    async def call_tool(self, tool_name: str, arguments: dict):
        result = await self.session.call_tool(
            tool_name,
            arguments
        )
        return result
    
    async def close(self):

        if self.stdio_context:
            await self.stdio_context.__aexit__(
                None,
                None,
                None
            )