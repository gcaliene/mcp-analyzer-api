import asyncio
from dotenv import load_dotenv
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_anthropic import ChatAnthropic
from langgraph.prebuilt import create_react_agent
import os

load_dotenv()

llm = ChatAnthropic(
    anthropic_api_key=os.environ["ANTHROPIC_API_KEY"],
    model="claude-3-5-sonnet-20240620"
)

async def main():
    client = MultiServerMCPClient(
        {
            "weather": {
                "url": "http://localhost:8000/sse",
                "transport": "sse",
            },
        }
    )
    tools = await client.get_tools()
    agent = create_react_agent(llm, tools)
    result = await agent.ainvoke(
        {"messages": "What is the weather in San Francisco?"}
    )
    print(result["messages"][-1].content)

if __name__ == "__main__":
    asyncio.run(main()) 