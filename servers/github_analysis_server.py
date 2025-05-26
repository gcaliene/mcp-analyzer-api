from mcp.server.fastmcp import FastMCP
import requests
import re
from typing import List
import os
import ast

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


def analyze_files_advanced(owner: str, repo: str, path: str = "") -> list[dict]:
    api_url = GITHUB_API_URL.format(owner=owner, repo=repo) + path
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
                content = file_resp.text
                lines = content.splitlines()
                file_info = {
                    "name": f["path"],
                    "type": f['name'].split('.')[-1] if '.' in f['name'] else 'unknown',
                    "lines": len(lines),
                    "non_empty_lines": sum(1 for line in lines if line.strip()),
                    "size_bytes": len(content.encode('utf-8')),
                }
                # Optional: language-specific analysis
                if f['name'].endswith('.py'):
                    file_info["python_analysis"] = analyze_python_code(content)
                elif f['name'].endswith('.md'):
                    file_info["markdown_analysis"] = analyze_markdown_code(content)
                results.append(file_info)
        elif f['type'] == 'dir' and 'path' in f:
            sub_results = analyze_files_advanced(owner, repo, f['path'])
            results.extend(sub_results)
    return results


@mcp.tool()
async def analyze_github_repo(url: str) -> str:
    """Advanced analysis of a public GitHub repo: functions, classes, comments, imports, and more."""
    try:
        owner, repo = extract_owner_repo(url)
    except Exception as e:
        return f"Error: {e}"
    file_analyses = analyze_files_advanced(owner, repo)
    if not file_analyses:
        return f"No files found or failed to fetch repo contents for {url}"
    summary_lines = []
    for f in file_analyses:
        line = f"{f['name']} ({f['type']}): {f['lines']} lines"
        if f['type'] == 'py' and 'python_analysis' in f:
            pa = f['python_analysis']
            if 'error' in pa:
                line += f" | Python analysis error: {pa['error']}"
            else:
                line += f" | funcs: {pa['function_count']}, classes: {pa['class_count']}, comments: {pa['comment_count']}, docstrings: {pa['docstring_count']}, imports: {', '.join(pa['imports'])}"
        elif f['type'] == 'md' and 'markdown_analysis' in f:
            ma = f['markdown_analysis']
            line += f" | headings: {ma['heading_count']}"
        summary_lines.append(line)
    summary = f"Advanced analysis for repo {owner}/{repo}:\n" + "\n".join(summary_lines)
    return summary


if __name__ == "__main__":
    mcp.run(transport="sse") 