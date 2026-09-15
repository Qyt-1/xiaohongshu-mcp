from flask import Flask, jsonify, request

app = Flask(__name__)

# 简单的 MCP 工具定义
TOOLS = [
    {
        "name": "login",
        "description": "登录小红书账号",
        "inputSchema": {"type": "object", "properties": {}}
    },
    {
        "name": "search_notes",
        "description": "根据关键词搜索笔记",
        "inputSchema": {
            "type": "object",
            "properties": {
                "keywords": {"type": "string"},
                "limit": {"type": "integer", "default": 20}
            }
        }
    },
    {
        "name": "get_note_content",
        "description": "获取笔记正文内容",
        "inputSchema": {
            "type": "object",
            "properties": {"url": {"type": "string"}}
        }
    }
]

@app.route('/tools', methods=['GET'])
def list_tools():
    return jsonify({"tools": TOOLS})

@app.route('/call', methods=['POST'])
def call_tool():
    data = request.json
    tool_name = data.get('name')
    args = data.get('arguments', {})
    
    if tool_name == 'login':
        return jsonify({"result": "登录成功"})
    elif tool_name == 'search_notes':
        keywords = args.get('keywords', '')
        limit = args.get('limit', 20)
        return jsonify({"result": f"搜索 {keywords}，共找到 {limit} 条笔记"})
    elif tool_name == 'get_note_content':
        url = args.get('url', '')
        return jsonify({"result": f"获取笔记内容: {url}"})
    else:
        return jsonify({"error": "未知工具"}), 404

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    print("启动小红书 MCP HTTP 服务器...")
    print("HTTP 端口: http://0.0.0.0:8000")
    print("工具列表: http://127.0.0.1:8000/tools")
    # 监听所有网络接口（0.0.0.0），这样手机可以通过局域网 IP 访问
    app.run(host='0.0.0.0', port=8000, debug=False)