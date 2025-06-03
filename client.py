import asyncio
from dotenv import load_dotenv
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_anthropic import ChatAnthropic
from langgraph.prebuilt import create_react_agent
import os
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Any
from contextlib import asynccontextmanager

load_dotenv()

llm = ChatAnthropic(
    anthropic_api_key=os.environ["ANTHROPIC_API_KEY"],
    model="claude-3-5-sonnet-20240620"
)

app = FastAPI()

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
    app.state.tools = await app.state.client.get_tools()
    app.state.tools = [tool for tool in app.state.tools if tool.name != 'create_issue']
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
        system_prompt = "You are a helpful assistant that can answer questions and help with tasks."
        result = await agent.ainvoke({"messages": request.messages, "system": system_prompt })
        print('api route', result)
        return JSONResponse({"response": result["messages"][-1].content})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 