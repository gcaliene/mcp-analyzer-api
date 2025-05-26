from mcp.server.fastmcp import FastMCP
import requests
import re
from typing import List
import os
import ast
import inspect
from urllib.parse import quote

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


def list_repo_files(owner: str, repo: str) -> List[str]:
    api_url = GITHUB_API_URL.format(owner=owner, repo=repo)
    headers = {"Accept": "application/vnd.github.v3+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"
    resp = requests.get(api_url, headers=headers)
    if resp.status_code != 200:
        return []
    files = resp.json()
    return [f['name'] for f in files if f['type'] == 'file']


def analyze_files_with_line_counts(owner: str, repo: str) -> list[tuple[str, int]]:
    api_url = GITHUB_API_URL.format(owner=owner, repo=repo)
    headers = {"Accept": "application/vnd.github.v3+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"
    resp = requests.get(api_url, headers=headers)
    if resp.status_code != 200:
        return []
    files = resp.json()
    results = []
    for f in files:
        if f['type'] == 'file' and 'download_url' in f and f['download_url']:
            file_resp = requests.get(f['download_url'])
            if file_resp.status_code == 200:
                line_count = len(file_resp.text.splitlines())
                results.append((f['name'], line_count))
    return results


def analyze_python_code(source: str) -> dict:
    try:
        tree = ast.parse(source)
    except Exception:
        return {"error": "Failed to parse Python file"}
    functions = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
    classes = [n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
    imports = [n.names[0].name for n in ast.walk(tree) if isinstance(n, ast.Import)]
    import_froms = [n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module]
    # Count comments and docstrings
    comment_count = sum(1 for line in source.splitlines() if line.strip().startswith('#'))
    docstring_count = sum(1 for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.Module)) and ast.get_docstring(node))
    return {
        "functions": functions,
        "classes": classes,
        "imports": imports + import_froms,
        "function_count": len(functions),
        "class_count": len(classes),
        "comment_count": comment_count,
        "docstring_count": docstring_count,
    }


def analyze_markdown_code(source: str) -> dict:
    headings = [line for line in source.splitlines() if line.strip().startswith('#')]
    return {"heading_count": len(headings)}


def analyze_mcp_server_code(source: str) -> dict:
    """Analyze MCP server Python code for server architecture, tools, and hierarchy."""
    try:
        tree = ast.parse(source)
    except Exception:
        return {"error": "Failed to parse Python file"}
    servers = []
    tools = []
    class MCPVisitor(ast.NodeVisitor):
        def __init__(self):
            self.servers = []
            self.tools = []
            self.current_server = None

        def visit_Assign(self, node):
            # Look for mcp = FastMCP("Server Name")
            if isinstance(node.value, ast.Call) and getattr(node.value.func, 'id', None) == 'FastMCP':
                if node.value.args and isinstance(node.value.args[0], ast.Constant):
                    self.current_server = node.targets[0].id
                    self.servers.append({
                        "var": self.current_server,
                        "name": node.value.args[0].value,
                        "tools": []
                    })
            self.generic_visit(node)

        def visit_FunctionDef(self, node):
            # Look for @mcp.tool() decorator
            for decorator in node.decorator_list:
                if isinstance(decorator, ast.Call) and getattr(getattr(decorator.func, 'attr', None), 'lower', lambda: None)() == 'tool':
                    # Find which server this tool is registered to (assume 'mcp' by default)
                    server_var = 'mcp'
                    docstring = ast.get_docstring(node) or ''
                    params = [arg.arg + (f': {ast.unparse(arg.annotation)}' if arg.annotation else '') for arg in node.args.args]
                    tool_info = {
                        "name": node.name,
                        "params": params,
                        "doc": docstring,
                        "server_var": server_var
                    }
                    self.tools.append(tool_info)
            self.generic_visit(node)

    visitor = MCPVisitor()
    visitor.visit(tree)
    # Attach tools to servers
    for server in visitor.servers:
        server["tools"] = [t for t in visitor.tools if t["server_var"] == server["var"]]
    return {"servers": visitor.servers, "tools": visitor.tools}


def analyze_code_generic(source: str, filetype: str) -> dict:
    """Language-agnostic analysis: extract function/method definitions and comments for any language."""
    import re
    # Patterns for common languages (expand as needed)
    patterns = {
        'py': r'def\s+(\w+)\s*\(([^)]*)\)',
        'js': r'function\s+(\w+)\s*\(([^)]*)\)',
        'ts': r'function\s+(\w+)\s*\(([^)]*)\)',
        'java': r'(?:public|private|protected)?\s*(?:static)?\s*\w+\s+(\w+)\s*\(([^)]*)\)',
        'go': r'func\s+(\w+)\s*\(([^)]*)\)',
        'rb': r'def\s+(\w+)\s*\(([^)]*)\)',
        'php': r'function\s+(\w+)\s*\(([^)]*)\)',
        'cpp': r'(?:\w+\s+)+?(\w+)\s*\(([^)]*)\)\s*\{',
        'c': r'(?:\w+\s+)+?(\w+)\s*\(([^)]*)\)\s*\{',
        'cs': r'(?:public|private|protected)?\s*(?:static)?\s*\w+\s+(\w+)\s*\(([^)]*)\)',
    }
    pattern = patterns.get(filetype, r'(\w+)\s*\(([^)]*)\)')
    functions = []
    lines = source.splitlines()
    for i, line in enumerate(lines):
        match = re.search(pattern, line)
        if match:
            name = match.group(1)
            params = match.group(2)
            # Try to get docstring/comment above or on the same line
            doc = ''
            for j in range(i-1, max(i-4, -1), -1):
                comment_line = lines[j].strip()
                if comment_line.startswith('#') or comment_line.startswith('//') or comment_line.startswith('/*') or comment_line.startswith('*'):
                    doc = comment_line + '\n' + doc
                else:
                    break
            functions.append({
                'name': name,
                'params': params,
                'doc': doc.strip()
            })
    return {'functions': functions}


def analyze_files_advanced(owner: str, repo: str, path: str = "") -> list[dict]:
    api_url = GITHUB_API_URL.format(owner=owner, repo=repo)
    if path:
        if not path.startswith('/'):
            path = '/' + path
        api_url += quote(path)
    print(f"[analyze_files_advanced] Fetching: {api_url}")
    headers = {"Accept": "application/vnd.github.v3+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"
    resp = requests.get(api_url, headers=headers)
    if resp.status_code != 200:
        print(f"[analyze_files_advanced] Failed to fetch {api_url} (status {resp.status_code})")
        return []
    files = resp.json()
    print(f"[analyze_files_advanced] {len(files)} items found at {api_url}")
    results = []
    for f in files:
        if f['type'] == 'file' and 'download_url' in f and f['download_url']:
            print(f"[analyze_files_advanced] Analyzing file: {f['path']}")
            file_resp = requests.get(f['download_url'])
            if file_resp.status_code == 200:
                content = file_resp.text
                lines = content.splitlines()
                file_info = {
                    "name": f["path"],
                    "type": f['name'].split('.')[-1] if '.' in f['name'] else 'unknown',
                    "lines": len(lines),
                    "non_empty_lines": sum(1 for line in lines if line.strip()),
                    "size_bytes": len(content.encode('utf-8')),
                }
                ext = file_info['type']
                if ext == 'py':
                    print(f"[analyze_files_advanced] Running MCP and Python analysis on: {f['path']}")
                    file_info["mcp_analysis"] = analyze_mcp_server_code(content)
                    file_info["python_analysis"] = analyze_python_code(content)
                elif ext == 'md':
                    print(f"[analyze_files_advanced] Running Markdown analysis on: {f['path']}")
                    file_info["markdown_analysis"] = analyze_markdown_code(content)
                else:
                    print(f"[analyze_files_advanced] Running generic analysis on: {f['path']}")
                    file_info["generic_analysis"] = analyze_code_generic(content, ext)
                results.append(file_info)
            else:
                print(f"[analyze_files_advanced] Failed to download file: {f['path']} (status {file_resp.status_code})")
        elif f['type'] == 'dir' and 'path' in f:
            sub_path = f['path']
            if not sub_path.startswith('/'):
                sub_path = '/' + sub_path
            print(f"[analyze_files_advanced] Entering directory: {sub_path}")
            sub_results = analyze_files_advanced(owner, repo, sub_path)
            results.extend(sub_results)
    print(f"[analyze_files_advanced] Completed analysis for: {api_url}")
    return results


@mcp.tool()
async def analyze_github_repo(url: str) -> str:
    """Advanced analysis of a public GitHub repo: functions, classes, comments, imports, MCP server architecture, and more."""
    print(f"[analyze_github_repo] Starting analysis for URL: {url}")
    try:
        owner, repo = extract_owner_repo(url)
        print(f"[analyze_github_repo] Extracted owner: {owner}, repo: {repo}")
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
        line = f"{f['name']} ({f['type']}): {f['lines']} lines"
        # Python MCP server breakdown
        if f['type'] == 'py' and 'mcp_analysis' in f:
            mcp = f['mcp_analysis']
            if 'servers' in mcp and mcp['servers']:
                for server in mcp['servers']:
                    mcp_structures.append(server)
                    print(f"[analyze_github_repo] MCP server found: {server['name']} with {len(server['tools'])} tools.")
        # Generic function breakdown for all languages
        if 'generic_analysis' in f and f['generic_analysis']['functions']:
            line += "\n  Functions:"
            for func in f['generic_analysis']['functions']:
                line += f"\n    └─ {func['name']}({func['params']})"
                if func['doc']:
                    line += f"\n        Description: {func['doc']}"
        summary_lines.append(line)
    # Add MCP server architecture breakdown
    if mcp_structures:
        summary_lines.append("\nMCP Server Architecture:")
        for server in mcp_structures:
            summary_lines.append(f"Server: {server['name']}")
            for tool in server['tools']:
                summary_lines.append(f"  └─ Tool: {tool['name']}({', '.join(tool['params'])})")
                if tool['doc']:
                    summary_lines.append(f"      Description: {tool['doc']}")
    print(f"[analyze_github_repo] Summary generation complete.")
    summary = f"Advanced analysis for repo {owner}/{repo}:\n" + "\n".join(summary_lines)
    return summary


if __name__ == "__main__":
    mcp.run(transport="sse") 