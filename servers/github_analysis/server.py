from mcp.server.fastmcp import FastMCP
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from servers.github_analysis.utils import extract_owner_repo
from servers.github_analysis.analysis import analyze_files_advanced

mcp = FastMCP("GitHub Analysis MCP Server")

@mcp.tool()
async def analyze_github_repo(url: str) -> dict:
    """Analysis of a Model Context Protocol (MCP) server GitHub repo: prioritize listing all MCP tools with descriptions and its' parameters, list all defined prompts and resources, identify patterns used in server design and visualize the hierarchical structure of the server components."""
    print(f"[analyze_github_repo] Starting analysis for URL: {url}")
    try:
        owner, repo = extract_owner_repo(url)
        print(f"[analyze_github_repo] Extracted owners: {owner}, repo: {repo}")
    except Exception as e:
        print(f"[analyze_github_repo] Error extracting owner/repo: {e}")
        return {"error": str(e)}
    print(f"[analyze_github_repo] Starting file analysis for {owner}/{repo}")
    file_analyses = analyze_files_advanced(owner, repo)
    print(f"[analyze_github_repo] File analysis complete. {len(file_analyses)} files found.")
    if not file_analyses:
        print(f"[analyze_github_repo] No files found or failed to fetch repo contents for {url}")
        return {"error": f"No files found or failed to fetch repo contents for {url}"}

    summary = {"tools": [], "prompts": [], "resources": []}
    for f in file_analyses:
        mcp_analysis = f.get('mcp_analysis', {})
        tools = mcp_analysis.get('tools', [])
        prompts = mcp_analysis.get('prompts', [])
        resources = mcp_analysis.get('resources', [])
        print(f"[analyze_github_repo] Analyzing file: {f['name']} ({f['type']})")
        # Tools
        for tool in tools:
            tool_obj = {
                "name": tool.get("name", ""),
                "description": tool.get("description", ""),
                "parameters": tool.get("parameters", [])
            }
            summary["tools"].append(tool_obj)
        # Prompts
        for prompt in prompts:
            summary["prompts"].append({"name": prompt.get("name", ""), "description": ""})
        # Resources
        for resource in resources:
            summary["resources"].append({"name": resource.get("name", ""), "description": ""})
    print(f"[analyze_github_repo] Summary object generation complete.")
    print("summary", summary)
    return summary

if __name__ == "__main__":
    mcp.run(transport="sse") 