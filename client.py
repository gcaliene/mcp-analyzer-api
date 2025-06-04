import asyncio
import logging
from dotenv import load_dotenv
from langchain_core.messages import SystemMessage
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
    system_prompt = SystemMessage(
        content="You are a helpful assistant. You must always call the 'ask' tool first as using any other tools before using the ask tool will result in an error."
    )
    agent = create_react_agent(llm, tools, prompt=system_prompt)
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
        system_prompt = "You are a helpful assistant that can answer questions and help with tasks. You will always use the ask tool first to access the tools."
        logging.info("Calling LLM agent with user messages...")
        result = await agent.ainvoke({"messages": messages, "system": system_prompt})
        logging.info(f"LLM agent response: {result}")
        response_content = result["messages"][-1].content if result.get("messages") else None
        logging.info(f"Returning response to user: {response_content}")
        return {"response": response_content}
    mcp.tool(name="ask", description="The first tool to always be called when talking to LLM agent that routes to all available tools.")(ask)

if __name__ == "__main__":
    asyncio.run(register_dynamic_tools())
    mcp.run(transport="sse")