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


def analyze_code_unified(source: str, filetype: str) -> dict:
    """Language-agnostic analysis: extract tools (functions), prompts, and resources for any language."""
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
    prompts = []
    resources = []
    lines = source.splitlines()
    for i, line in enumerate(lines):
        # Function/method extraction
        match = re.search(pattern, line)
        if match:
            name = match.group(1)
            params = match.group(2)
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
        # Prompt/resource extraction (variable assignment)
        assign_match = re.match(r'\s*(\w+)\s*[=:]', line)
        if assign_match:
            var_name = assign_match.group(1).lower()
            # Prompts
            if (
                var_name == 'prompt' or var_name.endswith('_prompt') or var_name == 'prompts' or var_name.endswith('_prompts')
            ):
                prompts.append({'name': assign_match.group(1)})
            # Resources
            if (
                var_name == 'resource' or var_name.endswith('_resource') or var_name == 'resources' or var_name.endswith('_resources')
            ):
                resources.append({'name': assign_match.group(1)})
    return {'tools': functions, 'prompts': prompts, 'resources': resources}


def analyze_markdown_code(source: str) -> dict:
    headings = [line for line in source.splitlines() if line.strip().startswith('#')]
    return {"heading_count": len(headings)}


def analyze_mcp_server_code(source: str) -> dict:
    """Analyze MCP server Python code for server architecture, tools, prompts, and resources."""
    try:
        tree = ast.parse(source)
    except Exception:
        return {"error": "Failed to parse Python file"}
    servers = []
    tools = []
    prompts = []
    resources = []
    class MCPVisitor(ast.NodeVisitor):
        def __init__(self):
            self.servers = []
            self.tools = []
            self.prompts = []
            self.resources = []
            self.current_server = None

        def visit_Assign(self, node):
            # Look for mcp = FastMCP("Server Name")
            if isinstance(node.value, ast.Call) and getattr(node.value.func, 'id', None) == 'FastMCP':
                if node.value.args and isinstance(node.value.args[0], ast.Constant):
                    self.current_server = node.targets[0].id
                    self.servers.append({
                        "var": self.current_server,
                        "name": node.value.args[0].value,
                        "tools": [],
                        "prompts": [],
                        "resources": []
                    })
            # Look for prompt/resource assignments
            for target in node.targets:
                if isinstance(target, ast.Name):
                    var_name = target.id.lower()
                    # Prompts
                    if (
                        var_name == 'prompt' or var_name.endswith('_prompt') or var_name == 'prompts' or var_name.endswith('_prompts')
                    ):
                        value = ast.get_docstring(node) if ast.get_docstring(node) else ''
                        self.prompts.append({
                            "name": target.id,
                            "value": value
                        })
                    # Resources
                    if (
                        var_name == 'resource' or var_name.endswith('_resource') or var_name == 'resources' or var_name.endswith('_resources')
                    ):
                        value = ast.get_docstring(node) if ast.get_docstring(node) else ''
                        self.resources.append({
                            "name": target.id,
                            "value": value
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
    # Attach tools, prompts, and resources to servers
    for server in visitor.servers:
        server["tools"] = [t for t in visitor.tools if t["server_var"] == server["var"]]
        server["prompts"] = visitor.prompts
        server["resources"] = visitor.resources
    return {"servers": visitor.servers, "tools": visitor.tools, "prompts": visitor.prompts, "resources": visitor.resources}


def should_ignore_test_file(name: str, path: str, ext: str) -> bool:
    """Return True if the file should be ignored as a test file (unit, integration, or e2e). Covers all languages and common patterns."""
    lower_name = name.lower()
    lower_path = path.lower()
    # Common test file patterns (unit, integration, e2e, spec)
    test_keywords = [
        'test', 'tests', 'spec', 'e2e', 'integration', 'unittest', 'describe'
    ]
    # Check for keywords in name or path
    for kw in test_keywords:
        if kw in lower_name or kw in lower_path:
            print(f"[should_ignore_test_file] Skipping {path} due to keyword '{kw}' in name or path.")
            return True
    # Common suffixes and prefixes for test files
    suffixes = [
        '_test', '_tests', '.spec', '.e2e', '.integration', '.unittest', '.it', '.describe'
    ]
    for suf in suffixes:
        if lower_name.endswith(f'{suf}.{ext}') or lower_name.endswith(suf):
            print(f"[should_ignore_test_file] Skipping {path} due to suffix '{suf}'.")
            return True
    prefixes = ['test_', 'spec_', 'e2e_', 'integration_', 'unittest_', 'it_', 'describe_']
    for pre in prefixes:
        if lower_name.startswith(pre):
            print(f"[should_ignore_test_file] Skipping {path} due to prefix '{pre}'.")
            return True
    # Language-specific patterns
    # JS/TS: .spec.js, .e2e.ts, .test.js, .test.ts
    if ext in {'js', 'ts'}:
        for pat in ['.spec.' + ext, '.e2e.' + ext, '.test.' + ext]:
            if lower_name.endswith(pat):
                print(f"[should_ignore_test_file] Skipping {path} due to JS/TS pattern '{pat}'.")
                return True
    # Python: test_*.py, *_test.py, *_spec.py, *_e2e.py
    if ext == 'py':
        for pat in ['_test.py', '_spec.py', '_e2e.py']:
            if lower_name.endswith(pat):
                print(f"[should_ignore_test_file] Skipping {path} due to Python pattern '{pat}'.")
                return True
        if lower_name.startswith('test_'):
            print(f"[should_ignore_test_file] Skipping {path} due to Python prefix 'test_'.")
            return True
    # Java: *Test.java, *Tests.java, *Spec.java, *E2E.java
    if ext == 'java':
        for pat in ['test.java', 'tests.java', 'spec.java', 'e2e.java']:
            if lower_name.endswith(pat):
                print(f"[should_ignore_test_file] Skipping {path} due to Java pattern '{pat}'.")
                return True
    # Go: *_test.go, *_e2e.go
    if ext == 'go':
        for pat in ['_test.go', '_e2e.go']:
            if lower_name.endswith(pat):
                print(f"[should_ignore_test_file] Skipping {path} due to Go pattern '{pat}'.")
                return True
    # Ruby: *_spec.rb, *_test.rb, *_e2e.rb
    if ext == 'rb':
        for pat in ['_spec.rb', '_test.rb', '_e2e.rb']:
            if lower_name.endswith(pat):
                print(f"[should_ignore_test_file] Skipping {path} due to Ruby pattern '{pat}'.")
                return True
    # PHP: *Test.php, *Spec.php, *E2E.php
    if ext == 'php':
        for pat in ['test.php', 'spec.php', 'e2e.php']:
            if lower_name.endswith(pat):
                print(f"[should_ignore_test_file] Skipping {path} due to PHP pattern '{pat}'.")
                return True
    # C/C++/C#: *Test.c, *Test.cpp, *Test.cs, *Spec.c, *E2E.cpp, etc.
    if ext in {'c', 'cpp', 'cs'}:
        for pat in ['test.' + ext, 'spec.' + ext, 'e2e.' + ext]:
            if lower_name.endswith(pat):
                print(f"[should_ignore_test_file] Skipping {path} due to C/C++/C# pattern '{pat}'.")
                return True
    return False


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
    ignore_exts = {"md", "json", "toml", "ini", "env", "cfg", "conf", "yml", "yaml"}
    ignore_names = {"Dockerfile"}
    ignore_patterns = ["docker-compose", ".github/", ".gitlab/", ".github", ".gitlab"]
    code_exts = {"py", "js", "ts", "java", "go", "rb", "php", "cpp", "c", "cs"}
    for f in files:
        ext = f['name'].split('.')[-1] if '.' in f['name'] else ''
        if should_ignore_test_file(f['name'], f['path'], ext):
            print(f"[analyze_files_advanced] Skipping test file: {f['path']}")
            continue
        if f['type'] == 'file' and 'download_url' in f and f['download_url']:
            if ext in ignore_exts or f['name'] in ignore_names or any(p in f['path'] for p in ignore_patterns):
                print(f"[analyze_files_advanced] Skipping ignored file: {f['path']}")
                continue
            if ext not in code_exts:
                print(f"[analyze_files_advanced] Skipping non-code file: {f['path']}")
                continue
            print(f"[analyze_files_advanced] Analyzing file: {f['path']}")
            file_resp = requests.get(f['download_url'])
            if file_resp.status_code == 200:
                content = file_resp.text
                lines = content.splitlines()
                file_info = {
                    "name": f["path"],
                    "type": ext if ext else 'unknown',
                    "lines": len(lines),
                    "non_empty_lines": sum(1 for line in lines if line.strip()),
                    "size_bytes": len(content.encode('utf-8')),
                }
                print(f"[analyze_files_advanced] Running unified code analysis on: {f['path']}")
                file_info["mcp_analysis"] = analyze_code_unified(content, ext)
                results.append(file_info)
            else:
                print(f"[analyze_files_advanced] Failed to download file: {f['path']} (status {file_resp.status_code})")
        elif f['type'] == 'dir' and 'path' in f:
            sub_path = f['path']
            if not sub_path.startswith('/'):
                sub_path = '/' + sub_path
            print(f"[analyze_files_advanced] Traversing into folder: {sub_path} to check its contents.")
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
    return summary


if __name__ == "__main__":
    mcp.run(transport="sse") 