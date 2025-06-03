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
    # Do not block on OAuth here!
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
        prompt_template = f"""List all MCP tools (include descriptions and parameters), prompts, and resources from this url: {request.messages}, along with the hierarchical structure of the server components. Prioritize listing all MCP tools with descriptions and its' parameters."""
        result = await agent.ainvoke({"messages": prompt_template, "system": system_prompt })
        print('api route', result)
        return JSONResponse({"response": result["messages"][-1].content})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/oauth/login")
def oauth_login():
    print("oauth_login", LINEAR_CLIENT_ID, LINEAR_REDIRECT_URI, OAUTH_SCOPES)
    params = {
        "client_id": LINEAR_CLIENT_ID,
        "redirect_uri": LINEAR_REDIRECT_URI,
        "response_type": "code",
        "scope": OAUTH_SCOPES,
        "actor": "user",
        # "state": "secure_random_state",  # Replace with real CSRF protection
    }
    url = f"https://linear.app/oauth/authorize?{urllib.parse.urlencode(params)}"
    print("oauth_login", url)
    return RedirectResponse(url)

@app.get("/oauth/callback")
async def oauth_callback(request: Request):
    global linear_access_token
    code = request.query_params.get("code")
    state = request.query_params.get("state")
    if not code:
        return JSONResponse({"error": "Missing code"}, status_code=400)
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.linear.app/oauth/token",
            data={
                "code": code,
                "redirect_uri": LINEAR_REDIRECT_URI,
                "client_id": LINEAR_CLIENT_ID,
                "client_secret": LINEAR_CLIENT_SECRET,
                "grant_type": "authorization_code",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        resp.raise_for_status()
        data = resp.json()
        print("oauth_callback", data["access_token"])
        linear_access_token = data["access_token"]

    # Initialize the client and agent now that we have the token
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
                "transport": "stdio",  # or "subprocess" if that's what your client expects
            }
        }
    )
    app.state.tools = await app.state.client.get_tools()
    print("tools", app.state.tools)
    app.state.agent = create_react_agent(llm, app.state.tools)

    return JSONResponse({"message": "OAuth successful. You can now use the /ask endpoint."}) 