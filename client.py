import asyncio
import logging
from dotenv import load_dotenv
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_anthropic import ChatAnthropic
from langgraph.prebuilt import create_react_agent
import os
from mcp.server.fastmcp import FastMCP
import inspect

load_dotenv()

llm = ChatAnthropic(
    anthropic_api_key=os.environ["ANTHROPIC_API_KEY"],
    model="claude-3-5-sonnet-20240620"
)

mcp = FastMCP("Aggregated MCP Server")

async def get_tools_and_agent():
    client = MultiServerMCPClient(
        {
            # "github_analysis": {
            #     "url": "http://localhost:8000/sse",
            #     "transport": "sse",
            # },
            "linear": {
                "command": "npx",
                "args": [
                    "-y", "mcp-remote", "https://mcp.linear.app/sse" 
                ],
                "transport": "stdio",
            },
            "gerson":{
                "command": "npx",
                "args": [
                    "-y", "mcp-remote", "https://mcp-auth0-oidc.gerson-398.workers.dev/sse"
                ],
                "transport": "stdio",
            }
        }
    )
    tools = await client.get_tools()
    tools = [tool for tool in tools if tool.name != 'create_issue']
    agent = create_react_agent(llm, tools)
    return tools, agent

# Store references to proxies to avoid late binding issues
registered_tool_proxies = {}

def make_tool_proxy(tool):
    async def tool_proxy(**kwargs):
        logging.info(f"Tool called: {tool.name} with args: {kwargs}")
        return await tool.invoke(**kwargs)
    tool_proxy.__name__ = tool.name
    tool_proxy.__doc__ = tool.description
    return tool_proxy

async def register_dynamic_tools():
    tools, agent = await get_tools_and_agent()
    # Register each tool as a proxy
    for tool in tools:
        proxy = make_tool_proxy(tool)
        registered_tool_proxies[tool.name] = proxy
        mcp.tool(name=tool.name, description=tool.description)(proxy)
    # Register the agent as a tool
    async def ask(messages: list):
        logging.info(f"Agent 'ask' called with messages: {messages}")
        system_prompt = "You are a helpful assistant that can answer questions and help with tasks."
        result = await agent.ainvoke({"messages": messages, "system": system_prompt})
        return {"response": result["messages"][-1].content}
    mcp.tool(name="ask", description="LLM agent that routes to all available tools.")(ask)

if __name__ == "__main__":
    asyncio.run(register_dynamic_tools())
    mcp.run(transport="sse")