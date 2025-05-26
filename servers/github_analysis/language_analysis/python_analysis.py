import re

def extract_functions(source: str) -> list[dict]:
    pattern = r'def\s+(\w+)\s*\(([^)]*)\)'
    lines = source.splitlines()
    functions = []
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
                    param_list = [p.strip() for p in params.split(',') if p.strip()]
                    functions.append({
                        'name': name,
                        'params': param_list,
                        'description': doc.strip()
                    })
                    break
    return functions 