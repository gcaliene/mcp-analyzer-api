import asyncio
from dotenv import load_dotenv
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_anthropic import ChatAnthropic
from langgraph.prebuilt import create_react_agent
import os
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
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

class AskRequest(BaseModel):
    messages: Any

@app.post("/ask")
async def ask(request: AskRequest):
    try:
        agent = app.state.agent
        result = await agent.ainvoke({"messages": request.messages})
        return JSONResponse({"response": result["messages"][-1].content})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 