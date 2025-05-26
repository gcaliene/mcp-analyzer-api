from servers.github_analysis.utils import should_ignore_test_file, GITHUB_API_URL, GITHUB_TOKEN
import requests
import re
from urllib.parse import quote
from servers.github_analysis.language_analysis import (
    extract_python, extract_go, extract_js, extract_ts, extract_java, extract_cs, extract_rb, extract_php, extract_cpp, extract_c
)

IGNORE_DIRS = {'third-party'}

EXTRACTORS = {
    'py': extract_python,
    'go': extract_go,
    'js': extract_js,
    'ts': extract_ts,
    'java': extract_java,
    'cs': extract_cs,
    'rb': extract_rb,
    'php': extract_php,
    'cpp': extract_cpp,
    'c': extract_c,
}

def analyze_code_unified(source: str, filetype: str) -> dict:
    extractor = EXTRACTORS.get(filetype)
    functions = extractor(source) if extractor else []
    prompts = []
    resources = []
    lines = source.splitlines()
    for line in lines:
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
        if any(ignore in f['name'].lower() or ignore in f['path'].lower() for ignore in IGNORE_DIRS):
            print(f"[analyze_files_advanced] Skipping due to ignore dir: {f['path']}")
            continue
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