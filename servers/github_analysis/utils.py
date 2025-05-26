import os
import re
from typing import List
from urllib.parse import quote

GITHUB_API_URL = "https://api.github.com/repos/{owner}/{repo}/contents/"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")

def extract_owner_repo(url: str) -> tuple[str, str]:
    match = re.match(r"https://github.com/([^/]+)/([^/]+)", url)
    if not match:
        raise ValueError("Invalid GitHub repo URL")
    print(match.group(1), match.group(2))
    return match.group(1), match.group(2)

def list_repo_files(owner: str, repo: str) -> List[str]:
    import requests
    api_url = GITHUB_API_URL.format(owner=owner, repo=repo)
    headers = {"Accept": "application/vnd.github.v3+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"
    resp = requests.get(api_url, headers=headers)
    if resp.status_code != 200:
        return []
    files = resp.json()
    return [f['name'] for f in files if f['type'] == 'file']

def should_ignore_test_file(name: str, path: str, ext: str) -> bool:
    lower_name = name.lower()
    lower_path = path.lower()
    test_keywords = [
        'test', 'tests', 'spec', 'e2e', 'integration', 'unittest', 'describe'
    ]
    for kw in test_keywords:
        if kw in lower_name or kw in lower_path:
            print(f"[should_ignore_test_file] Skipping {path} due to keyword '{kw}' in name or path.")
            return True
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
    if ext in {'js', 'ts'}:
        for pat in ['.spec.' + ext, '.e2e.' + ext, '.test.' + ext]:
            if lower_name.endswith(pat):
                print(f"[should_ignore_test_file] Skipping {path} due to JS/TS pattern '{pat}'.")
                return True
    if ext == 'py':
        for pat in ['_test.py', '_spec.py', '_e2e.py']:
            if lower_name.endswith(pat):
                print(f"[should_ignore_test_file] Skipping {path} due to Python pattern '{pat}'.")
                return True
        if lower_name.startswith('test_'):
            print(f"[should_ignore_test_file] Skipping {path} due to Python prefix 'test_'.")
            return True
    if ext == 'java':
        for pat in ['test.java', 'tests.java', 'spec.java', 'e2e.java']:
            if lower_name.endswith(pat):
                print(f"[should_ignore_test_file] Skipping {path} due to Java pattern '{pat}'.")
                return True
    if ext == 'go':
        for pat in ['_test.go', '_e2e.go']:
            if lower_name.endswith(pat):
                print(f"[should_ignore_test_file] Skipping {path} due to Go pattern '{pat}'.")
                return True
    if ext == 'rb':
        for pat in ['_spec.rb', '_test.rb', '_e2e.rb']:
            if lower_name.endswith(pat):
                print(f"[should_ignore_test_file] Skipping {path} due to Ruby pattern '{pat}'.")
                return True
    if ext == 'php':
        for pat in ['test.php', 'spec.php', 'e2e.php']:
            if lower_name.endswith(pat):
                print(f"[should_ignore_test_file] Skipping {path} due to PHP pattern '{pat}'.")
                return True
    if ext in {'c', 'cpp', 'cs'}:
        for pat in ['test.' + ext, 'spec.' + ext, 'e2e.' + ext]:
            if lower_name.endswith(pat):
                print(f"[should_ignore_test_file] Skipping {path} due to C/C++/C# pattern '{pat}'.")
                return True
    return False 