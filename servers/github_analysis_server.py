from mcp.server.fastmcp import FastMCP
import requests
import re
from typing import List
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

mcp = FastMCP("GitHub Analysis MCP Server")

GITHUB_API_URL = "https://api.github.com/repos/{owner}/{repo}/contents/"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")


def extract_owner_repo(url: str) -> tuple[str, str]:
    match = re.match(r"https://github.com/([^/]+)/([^/]+)", url)
    if not match:
        raise ValueError("Invalid GitHub repo URL")
    print(match.group(1), match.group(2))
    return match.group(1), match.group(2)


def list_python_files(owner: str, repo: str) -> List[str]:
    api_url = GITHUB_API_URL.format(owner=owner, repo=repo)
    headers = {"Accept": "application/vnd.github.v3+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"
    resp = requests.get(api_url, headers=headers)
    if resp.status_code != 200:
        return []
    files = resp.json()
    return [f['name'] for f in files if f['name'].endswith('.py')]


@mcp.tool()
async def analyze_github_repo(url: str) -> str:
    """Analyze a public GitHub repo and return a summary."""
    try:
        owner, repo = extract_owner_repo(url)
    except Exception as e:
        return f"Error: {e}"
    py_files = list_python_files(owner, repo)
    if not py_files:
        return f"No Python files found or failed to fetch repo contents for {url}"
    summary = f"Repo {owner}/{repo} contains {len(py_files)} Python files: {', '.join(py_files)}"
    return summary


if __name__ == "__main__":
    mcp.run(transport="sse") 