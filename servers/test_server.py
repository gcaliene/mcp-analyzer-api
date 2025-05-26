from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Test MCP Server")

@mcp.tool()
async def test_get_weather(location: str) -> str:
    """Get weather for location."""
    print("This is a log from the SSE Server")
    return "Hot as hell"

if __name__ == "__main__":
    mcp.run(transport="sse") 