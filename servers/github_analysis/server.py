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
async def analyze_github_repo(url: str) -> str:
    """Analysis of a Model Context Protocol (MCP) server GitHub repo: list all MCP tools with descriptions and its' parameters, list all defined prompts and resources, identify patterns used in server design and visualize the hierarchical structure of the server components."""
    print(f"[analyze_github_repo] Starting analysis for URL: {url}")
    try:
        owner, repo = extract_owner_repo(url)
        print(f"[analyze_github_repo] Extracted owners: {owner}, repo: {repo}")
    except Exception as e:
        print(f"[analyze_github_repo] Error extracting owner/repo: {e}")
        return f"Error: {e}"
    print(f"[analyze_github_repo] Starting file analysis for {owner}/{repo}")
    file_analyses = analyze_files_advanced(owner, repo)
    print(f"[analyze_github_repo] File analysis complete. {len(file_analyses)} files found.")
    if not file_analyses:
        print(f"[analyze_github_repo] No files found or failed to fetch repo contents for {url}")
        return f"No files found or failed to fetch repo contents for {url}"
    summary_lines = []
    mcp_structures = []
    for f in file_analyses:
        line = f"{f['name']} ({f['type']})"
        mcp_analysis = f.get('mcp_analysis', {})
        tools = mcp_analysis.get('tools', [])
        prompts = mcp_analysis.get('prompts', [])
        resources = mcp_analysis.get('resources', [])
        print(f"[analyze_github_repo] Analyzing file: {f['name']} ({f['type']})")
        if not (tools or prompts or resources):
            print(f"[analyze_github_repo] Skipping {f['name']} ({f['type']}) - no tools, prompts, or resources found.")
            continue
        mcp = mcp_analysis
        if 'servers' in mcp and mcp['servers']:
            for server in mcp['servers']:
                mcp_structures.append(server)
                print(f"[analyze_github_repo] MCP server found: {server['name']} with {len(server['tools'])} tools.")
        if tools:
            print(f"[analyze_github_repo] Found {len(tools)} tool(s) in {f['name']}")
            line += "\n  Tools:"
            for tool in tools:
                params = tool.get('params', '')
                if isinstance(params, list):
                    params = ', '.join(params)
                line += f"\n    └─ {tool['name']}({params})"
                if tool.get('doc'):
                    line += f"\n        Description: {tool['doc']}"
        if prompts:
            print(f"[analyze_github_repo] Found {len(prompts)} prompt(s) in {f['name']}")
            line += "\n  Prompts:"
            for prompt in prompts:
                line += f"\n    └─ {prompt['name']}"
        if resources:
            print(f"[analyze_github_repo] Found {len(resources)} resource(s) in {f['name']}")
            line += "\n  Resources:"
            for resource in resources:
                line += f"\n    └─ {resource['name']}"
        summary_lines.append(line)
    if mcp_structures:
        summary_lines.append("\nMCP Server Architecture:")
        for server in mcp_structures:
            summary_lines.append(f"Server: {server['name']}")
            if server.get('tools'):
                summary_lines.append("  Tools:")
                for tool in server['tools']:
                    summary_lines.append(f"    └─ {tool['name']}({', '.join(tool['params'])})")
                    if tool['doc']:
                        summary_lines.append(f"        Description: {tool['doc']}")
            if server.get('prompts'):
                summary_lines.append("  Prompts:")
                for prompt in server['prompts']:
                    summary_lines.append(f"    └─ {prompt['name']}")
            if server.get('resources'):
                summary_lines.append("  Resources:")
                for resource in server['resources']:
                    summary_lines.append(f"    └─ {resource['name']}")
    print(f"[analyze_github_repo] Summary generation complete.")
    summary = f"Advanced analysis for repo {owner}/{repo}:\n" + "\n".join(summary_lines)
    print("summary", summary)
    return summary

if __name__ == "__main__":
    mcp.run(transport="sse") 