from typing import Any, List, Dict, Optional
import asyncio
import json
import os
import re
import base64
import tempfile
import pandas as pd
from datetime import datetime
from playwright.async_api import async_playwright
from playwright_stealth import Stealth
from fastmcp import FastMCP
import requests

# 初始化 FastMCP 服务器
mcp = FastMCP("xiaohongshu_scraper")

# 全局变量
_DIR = os.path.dirname(os.path.abspath(__file__))
BROWSER_DATA_DIR = os.path.join(_DIR, "browser_data")
DATA_DIR = os.path.join(_DIR, "data")
XHS_STATE_FILE = os.path.join(_DIR, "xhs_state.json")
XHS_MCP_DB = os.path.expanduser("~/.xhs-mcp/data.db")
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")

# 确保目录存在
os.makedirs(BROWSER_DATA_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

# 用于存储浏览器上下文
browser_instance = None
browser_obj = None
browser_context = None
main_page = None
is_logged_in = False

# 反风控辅助函数
import random as _random

async def _rand_sleep(base: float, jitter: float = 0.4):
    """带随机抖动的等待"""
    delta = base * jitter
    await asyncio.sleep(max(0.1, base + _random.uniform(-delta, delta)))

async def _human_type(page, text: str, wpm: int = 180):
    """逐字输入，模拟人类打字节奏"""
    base_delay = 60.0 / (wpm * 5)
    for char in text:
        await page.keyboard.type(char)
        if char in ('。', '，', '！', '？', '、', '\n', '.', ',', '!', '?'):
            await asyncio.sleep(_random.uniform(0.15, 0.45))
        else:
            await asyncio.sleep(_random.uniform(base_delay * 0.5, base_delay * 2.0))

async def ensure_browser():
    """确保浏览器已启动"""
    global browser_instance, browser_obj, browser_context, main_page, is_logged_in

    if browser_context is None:
        browser_instance = await async_playwright().start()
        browser_obj = await browser_instance.chromium.launch(
            headless=False,
            channel="chrome",
            args=['--no-sandbox', '--disable-setuid-sandbox'],
        )

        state = None
        if os.path.exists(XHS_STATE_FILE):
            try:
                with open(XHS_STATE_FILE) as f:
                    state = json.load(f)
            except Exception:
                state = None

        browser_context = await browser_obj.new_context(
            storage_state=state,
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            viewport=None,
        )
        if state:
            is_logged_in = True

        await browser_context.add_init_script("""
            window.__shadowRoots = new WeakMap();
            const _orig = Element.prototype.attachShadow;
            Element.prototype.attachShadow = function(init) {
                const shadow = _orig.call(this, init);
                window.__shadowRoots.set(this, shadow);
                return shadow;
            };
        """)

        if browser_context.pages:
            main_page = browser_context.pages[0]
        else:
            main_page = await browser_context.new_page()

        await Stealth().apply_stealth_async(main_page)
        main_page.set_default_timeout(60000)

    return is_logged_in

@mcp.tool()
async def login() -> str:
    """登录小红书账号"""
    global is_logged_in

    await ensure_browser()

    if not main_page:
        return "浏览器初始化失败，请重试"

    await main_page.goto("https://www.xiaohongshu.com", timeout=60000)
    await _rand_sleep(3)

    login_elements = await main_page.query_selector_all('text="登录"')
    if not login_elements:
        is_logged_in = True
        return "已登录小红书账号"

    max_wait_time = 180
    wait_interval = 5
    waited_time = 0

    while waited_time < max_wait_time:
        still_login = await main_page.query_selector_all('text="登录"')
        if not still_login:
            is_logged_in = True
            await _rand_sleep(2)
            try:
                state = await browser_context.storage_state()
                with open(XHS_STATE_FILE, 'w') as f:
                    json.dump(state, f)
            except Exception:
                pass
            return "登录成功！cookie 已保存"
        await asyncio.sleep(wait_interval)
        waited_time += wait_interval

    return "登录等待超时"

@mcp.tool()
async def search_notes(keywords: str, limit: int = 20, verbose: bool = False) -> str:
    """根据关键词搜索笔记"""
    login_status = await ensure_browser()
    if not login_status:
        return "请先登录小红书账号"

    if not main_page:
        return "浏览器初始化失败，请重试"

    target_count = min(limit, 100)
    search_url = f"https://www.xiaohongshu.com/search_result?keyword={keywords}&source=web_explore_feed"

    try:
        await main_page.goto(search_url, timeout=60000)
        await main_page.wait_for_function(
            "() => window.__INITIAL_STATE__ !== undefined",
            timeout=30000
        )
        await _rand_sleep(2)

        raw = await main_page.evaluate("""
            () => {
                const state = window.__INITIAL_STATE__;
                if (!state?.search?.feeds) return '[]';
                const feeds = state.search.feeds;
                const feedsData = feeds.value !== undefined ? feeds.value : feeds._value;
                return feedsData ? JSON.stringify(feedsData) : '[]';
            }
        """)

        feeds = json.loads(raw) if raw else []
        items = []
        for item in feeds[:target_count]:
            note_card = item.get('noteCard') or item.get('note_card') or {}
            user = note_card.get('user') or {}
            interact = note_card.get('interactInfo') or note_card.get('interact_info') or {}
            items.append({
                'id': item.get('id'),
                'xsecToken': item.get('xsec_token') or '',
                'title': note_card.get('displayTitle') or note_card.get('title') or '',
                'author': user.get('nickname') or '',
                'likes': interact.get('likedCount') or '0',
            })

        if not items:
            return f"未找到与\"{keywords}\"相关的笔记"

        result = f"搜索「{keywords}」，共找到 {len(items)} 条笔记：\n\n"
        for i, item in enumerate(items, 1):
            url = f"https://www.xiaohongshu.com/explore/{item['id']}"
            if verbose:
                url += f"?xsec_token={item['xsecToken']}"
            result += f"{i}. 【{item['title']}】 {item['author']} ❤️{item['likes']}\n   {url}\n\n"
        return result

    except Exception as e:
        return f"搜索笔记时出错: {str(e)}"

@mcp.tool()
async def get_note_content(url: str, include_images: bool = True) -> str:
    """获取笔记正文内容"""
    login_status = await ensure_browser()
    if not login_status:
        return "请先登录小红书账号"

    if not main_page:
        return "浏览器初始化失败，请重试"

    try:
        await main_page.goto(url, timeout=60000)
        await asyncio.sleep(5)

        content_text = await main_page.evaluate("""
            () => {
                const noteContent = document.querySelector('.note-content');
                if (noteContent) {
                    const noteText = noteContent.querySelector('.note-text');
                    if (noteText && noteText.textContent.trim()) {
                        return noteText.textContent.trim();
                    }
                }
                return "未能获取内容";
            }
        """)

        result = f"链接: {url}\n\n内容:\n{content_text}"
        return result

    except Exception as e:
        return f"获取笔记内容时出错: {str(e)}"

if __name__ == "__main__":
    print("启动小红书MCP服务器...")
    mcp.run(transport='stdio')