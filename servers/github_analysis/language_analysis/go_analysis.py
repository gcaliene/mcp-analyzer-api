import re

def extract_functions(source: str) -> list[dict]:
    pattern = r'func\s+(\w+)\s*\(([^)]*)\)'
    mcp_pattern = r'mcp\.NewTool\('
    lines = source.splitlines()
    functions = []
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
        if re.search(mcp_pattern, body):
            param_list = [p.strip() for p in params.split(',') if p.strip()]
            functions.append({
                'name': name,
                'params': param_list,
                'description': doc.strip()
            })
        if 'mcp.NewTool' in body:
            tool_name_match = re.search(r'mcp.NewTool\(["\']([\w_]+)["\']', body)
            tool_name = tool_name_match.group(1) if tool_name_match else name
            desc_match = re.search(r'mcp.WithDescription\([^)]*["\'](.+?)["\']', body)
            tool_desc = desc_match.group(1) if desc_match else ''
            param_pattern = re.compile(r'mcp.With(?:String|Number|Bool|Int|Float)\(["\']([\w_]+)["\'][^)]*mcp.Description\(["\'](.+?)["\']', re.DOTALL)
            parameters = []
            for p_match in param_pattern.finditer(body):
                pname, pdesc = p_match.group(1), p_match.group(2)
                parameters.append({"name": pname, "description": pdesc})
            functions.append({
                'name': tool_name,
                'parameters': parameters,
                'description': tool_desc
            })
    return functions 