from fastmcp import FastMCP

mcp = FastMCP("xiaohongshu_scraper")

@mcp.tool()
async def login() -> str:
    """登录小红书账号"""
    return "登录成功"

@mcp.tool()
async def search_notes(keywords: str, limit: int = 20) -> str:
    """根据关键词搜索笔记"""
    return f"搜索 {keywords}，共找到 {limit} 条笔记"

@mcp.tool()
async def get_note_content(url: str) -> str:
    """获取笔记正文内容"""
    return f"获取笔记内容: {url}"

if __name__ == "__main__":
    print("启动小红书 MCP 服务器 (SSE 模式)...")
    print("SSE 端点： http://127.0.0.1:8000")
    mcp.run(transport='sse')