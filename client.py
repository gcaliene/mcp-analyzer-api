import asyncio
from dotenv import load_dotenv
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_anthropic import ChatAnthropic
from langgraph.prebuilt import create_react_agent
import os
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Any
from contextlib import asynccontextmanager
import httpx
import urllib.parse

load_dotenv()

llm = ChatAnthropic(
    anthropic_api_key=os.environ["ANTHROPIC_API_KEY"],
    model="claude-3-5-sonnet-20240620"
)

app = FastAPI()
# print(os.environ["LINEAR_API_KEY"])

LINEAR_CLIENT_ID = os.environ["LINEAR_CLIENT_ID"]
LINEAR_CLIENT_SECRET = os.environ["LINEAR_CLIENT_SECRET"]
LINEAR_REDIRECT_URI = os.environ.get("LINEAR_REDIRECT_URI", "http://localhost:8001/oauth/callback")
OAUTH_SCOPES = "read,write,issues:create,comments:create,timeSchedule:write"

# In-memory token store (replace with persistent store in production)
linear_access_token = None

@asynccontextmanager
async def lifespan(app):
    app.state.client = MultiServerMCPClient(
        {
            "github_analysis": {
                "url": "http://localhost:8000/sse",
                "transport": "sse",
            },
            "linear": {
                "command": "npx",
                "args": [
                    "-y", "mcp-remote", "https://mcp.linear.app/sse"
                ],
                "transport": "stdio",
            }
        }
    )
    app.state.tools = await app.state.client.get_tools()
    for tool in app.state.tools:
        print(f"Tool: {tool.name}\n  Description: {tool.description}\n")
    app.state.agent = create_react_agent(llm, app.state.tools)
    yield

app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AskRequest(BaseModel):
    messages: Any

@app.post("/ask")
async def ask(request: AskRequest):
    try:
        agent = app.state.agent
        print("ask", request.messages)
        # System prompt would be better used here
        # System prompt: You are a helpful assistant that can answer questions and help with tasks.
        # User prompt: {request.messages}
        system_prompt = "You are a helpful assistant that can answer questions and help with tasks."
        # prompt_template = f"""List all MCP tools (include descriptions and parameters), prompts, and resources from this url: {request.messages}, along with the hierarchical structure of the server components. Prioritize listing all MCP tools with descriptions and its' parameters."""
        result = await agent.ainvoke({"messages": request.messages, "system": system_prompt })
        print('api route', result)
        return JSONResponse({"response": result["messages"][-1].content})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 