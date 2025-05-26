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
        }
    )
    app.state.tools = await app.state.client.get_tools()
    app.state.agent = create_react_agent(llm, app.state.tools)
    yield  # Startup done
    # (Optional) Add cleanup code here

app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Or specify your frontend URL
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
        prompt_template = f"""List all MCP tools (include descriptions and parameters), prompts, and resources from this url: {request.messages}, along with the hierarchical structure of the server components. Prioritize listing all MCP tools with descriptions and its' parameters."""
        result = await agent.ainvoke({"messages": prompt_template})
        print('api route', result)
        return JSONResponse({"response": result["messages"][-1].content})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 