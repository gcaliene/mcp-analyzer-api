import re

def extract_functions(source: str) -> list[dict]:
    pattern = r'def\s+(\w+)\s*\(([^)]*)\)'
    mcp_pattern = r'@mcp\.tool\s*\('
    lines = source.splitlines()
    functions = []
    for i, line in enumerate(lines):
        match = re.match(pattern, line)
        if match:
            name = match.group(1)
            params = match.group(2)
            doc = ''
            for j in range(i-1, max(i-4, -1), -1):
                comment_line = lines[j].strip()
                if comment_line.startswith('#') or comment_line.startswith('=begin'):
                    doc = comment_line + '\n' + doc
                else:
                    break
            if re.search(mcp_pattern, line):
                param_list = [p.strip() for p in params.split(',') if p.strip()]
                functions.append({
                    'name': name,
                    'params': param_list,
                    'description': doc.strip()
                })
    return functions 