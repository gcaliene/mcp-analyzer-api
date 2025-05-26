from servers.github_analysis.utils import should_ignore_test_file, GITHUB_API_URL, GITHUB_TOKEN
import requests
import re
from urllib.parse import quote

def analyze_code_unified(source: str, filetype: str) -> dict:
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
    mcp_patterns = {
        'py': r'@mcp\.tool\s*\(',
        'go': r'mcp\.NewTool\(',
        'js': r'mcp\.newTool\(',
        'ts': r'mcp\.newTool\(',
        'java': r'new\s+MCPTool\(',
        'cs': r'new\s+MCPTool\(',
    }
    pattern = patterns.get(filetype, r'(\w+)\s*\(([^)]*)\)')
    mcp_pattern = mcp_patterns.get(filetype)
    functions = []
    prompts = []
    resources = []
    lines = source.splitlines()
    if filetype == 'go' or filetype in {'js', 'ts', 'java', 'cs'}:
        func_indices = []
        for i, line in enumerate(lines):
            match = re.match(pattern, line)
            if match:
                func_indices.append((i, match.group(1), match.group(2)))
        func_indices.append((len(lines), None, None))
        for idx in range(len(func_indices) - 1):
            start, name, params = func_indices[idx]
            end = func_indices[idx + 1][0]
            body = '\n'.join(lines[start:end])
            doc = ''
            for j in range(start-1, max(start-4, -1), -1):
                comment_line = lines[j].strip()
                if comment_line.startswith('//') or comment_line.startswith('/*') or comment_line.startswith('*'):
                    doc = comment_line + '\n' + doc
                else:
                    break
            if mcp_pattern and re.search(mcp_pattern, body):
                functions.append({
                    'name': name,
                    'params': params,
                    'doc': doc.strip()
                })
    elif filetype == 'py':
        for i, line in enumerate(lines):
            if re.match(r'@mcp\.tool\s*\(', line.strip()):
                for j in range(i+1, min(i+6, len(lines))):
                    match = re.match(pattern, lines[j])
                    if match:
                        name = match.group(1)
                        params = match.group(2)
                        doc = ''
                        for k in range(j-1, max(j-4, -1), -1):
                            comment_line = lines[k].strip()
                            if comment_line.startswith('#') or comment_line.startswith('"""'):
                                doc = comment_line + '\n' + doc
                            else:
                                break
                        functions.append({
                            'name': name,
                            'params': params,
                            'doc': doc.strip()
                        })
                        break
            assign_match = re.match(r'\s*(\w+)\s*[=:]', line)
            if assign_match:
                var_name = assign_match.group(1).lower()
                if (
                    var_name == 'prompt' or var_name.endswith('_prompt') or var_name == 'prompts' or var_name.endswith('_prompts')
                ):
                    prompts.append({'name': assign_match.group(1)})
                if (
                    var_name == 'resource' or var_name.endswith('_resource') or var_name == 'resources' or var_name.endswith('_resources')
                ):
                    resources.append({'name': assign_match.group(1)})
    else:
        for i, line in enumerate(lines):
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
            assign_match = re.match(r'\s*(\w+)\s*[=:]', line)
            if assign_match:
                var_name = assign_match.group(1).lower()
                if (
                    var_name == 'prompt' or var_name.endswith('_prompt') or var_name == 'prompts' or var_name.endswith('_prompts')
                ):
                    prompts.append({'name': assign_match.group(1)})
                if (
                    var_name == 'resource' or var_name.endswith('_resource') or var_name == 'resources' or var_name.endswith('_resources')
                ):
                    resources.append({'name': assign_match.group(1)})
    result = {'tools': functions, 'prompts': prompts, 'resources': resources}
    print("analyze_code_unified", result)
    return result

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
    ignore_patterns = ["docker-compose", ".github/", ".gitlab/", ".github", ".gitlab", "third-party/"]
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
    print("!!!!!!!results", results)
    return results 