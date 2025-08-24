from __future__ import annotations

import os
import re
from typing import Optional, List
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup, Tag, NavigableString
from pydantic import BaseModel, HttpUrl, Field
from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import PlainTextResponse
from starlette.routing import Mount, Route
import uvicorn

from mcp.server.fastmcp import FastMCP

# ===== 常量 =====
BASE = "https://cdyouth.cdcyl.org.cn"
TARGET_URL = f"{BASE}/jgc/"
UA = "mcp-cd-youth/1.0.2 (+https://cdyouth.cdcyl.org.cn)"

# ===== 数据模型（结构化输出）=====
class Activity(BaseModel):
    id: Optional[str] = Field(None, description="活动 ID（从详情 URL 提取）")
    title: str = Field(..., description="活动标题")
    tags: Optional[str] = Field(None, description="标题前缀标签，如『幸福美好生活】【免费特供』等")
    area: Optional[str] = Field(None, description="板块/分类，如 锦官Joy / 锦官Talk")
    venue: Optional[str] = Field(None, description="场地 + 地址文本")
    dateTimeText: Optional[str] = Field(None, description="日期时间文本，如 08-29 [周五] 19:00 / 08-25 14:00")
    status: Optional[str] = Field(None, description="报名状态，如 报名中 / 已抢光")
    hits: Optional[int] = Field(None, description="浏览量（若有）")
    # image: Optional[HttpUrl] = Field(None, description="封面图绝对 URL")
    # url: HttpUrl = Field(..., description="详情页绝对 URL")
    # zhijiaId: Optional[str] = Field(None, description="h3 上的 zhijiaid 属性（若有）")


# ===== 工具函数 =====
def abs_url(u: Optional[str]) -> Optional[str]:
    """把相对/协议相对 URL 转成绝对 URL。"""
    if not u:
        return None
    if u.startswith("//"):
        return "https:" + u
    return urljoin(BASE, u)

def only_digits(s: Optional[str]) -> str:
    return re.sub(r"[^\d]", "", s or "")

def clean_text(s: Optional[str]) -> Optional[str]:
    if not s:
        return None
    return " ".join(s.split()).strip() or None

def get_attr(el: Optional[Tag], name: str) -> Optional[str]:
    return el.get(name) if el else None

def text_excluding_tags(root: Tag, exclude_names: tuple[str, ...]) -> str:
    """返回 root 中的纯文本，但排除来自指定标签的文本。"""
    parts: List[str] = []
    for node in root.descendants:
        if isinstance(node, NavigableString):
            parent = node.parent
            if parent and parent.name in exclude_names:
                continue
            parts.append(str(node))
    return "".join(parts)


# ===== 抓取与解析 =====
def fetch_html() -> str:
    try:
        with httpx.Client(
            timeout=20.0,
            follow_redirects=True,
            verify=False,
            headers={
                "User-Agent": UA,
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "zh-CN,zh;q=0.9",
                "Cache-Control": "no-cache",
                "Referer": TARGET_URL,
            },
        ) as client:
            r = client.get(TARGET_URL)
            r.raise_for_status()
            return r.text
    except httpx.RequestError as e:
        # 网络/连接问题
        raise RuntimeError(f"Request error: {e}") from e
    except httpx.HTTPStatusError as e:
        # 非 2xx
        raise RuntimeError(f"HTTP {e.response.status_code}: {e.response.reason_phrase}") from e


def parse_activities(html: str) -> List[Activity]:
    soup = BeautifulSoup(html, "lxml")
    items: List[Activity] = []

    for li in soup.select("#main_list_result > li"):
        # 详情链接（优先标题 <a>，否则图片 <a>）
        a_title = li.select_one(".txt2 h2 a")
        img_a = li.select_one(".img a")
        href = get_attr(a_title, "href") or get_attr(img_a, "href")
        full_url = abs_url(href)
        if not full_url:
            # 没有详情链接就跳过
            continue

        # 活动 ID
        m = re.search(r"/activity/(\d+)", full_url)
        act_id = m.group(1) if m else None

        # --- 标签（先取，避免后续计算标题时误删导致取不到） ---
        span_el = a_title.select_one("span") if a_title else None
        tags_text = clean_text(span_el.get_text()) if span_el else None
        # 注意：示例中 <span> 内还包含 <em>，直接 get_text() 就能拿到“幸福美好生活【免费特供】”

        # --- 标题文本（不破坏 DOM，排除 <span> 内容） ---
        title_text: Optional[str] = None
        if a_title:
            # 仅取 a 标签下的“直接文本节点”，从而跳过 <span>
            direct_texts = []
            for child in a_title.children:
                if isinstance(child, NavigableString):
                    direct_texts.append(str(child))
            title_text = clean_text("".join(direct_texts)) or clean_text(
                text_excluding_tags(a_title, ("span",))
            )
        title_text = title_text or "(未命名活动)"

        # 板块/分类（小黄条）
        area_el = li.select_one(".area")
        area_text = clean_text(area_el.get_text()) if area_el else None

        # 场地 + zhijiaId
        h3 = li.select_one(".txt2 h3")
        venue_text = clean_text(h3.get_text()) if h3 else None
        zhijia_id = get_attr(h3, "zhijiaid")

        # --- 状态（先取，再计算日期文本） ---
        a_status = li.select_one(".txt2 h4 a")
        status_text = clean_text(a_status.get_text()) if a_status else None

        # 时间文本（排除 a、em 的文本，但不修改 DOM）
        h4 = li.select_one(".txt2 h4")
        date_text = None
        if h4:
            date_text = clean_text(text_excluding_tags(h4, ("a", "em")))

        # 浏览量
        hits_block = li.select_one(".hits")
        hits_num_str = only_digits(hits_block.get_text()) if hits_block else ""
        hits_val = int(hits_num_str) if hits_num_str else None

        # 封面图
        img = li.select_one(".img_con img")
        img_src = abs_url(get_attr(img, "src"))

        items.append(
            Activity(
                id=act_id,
                title=title_text,
                tags=tags_text,
                area=area_text,
                venue=venue_text,
                dateTimeText=date_text,
                status=status_text,
                hits=hits_val,
                # image=img_src,
                # url=full_url,
                # zhijiaId=zhijia_id,
            )
        )

    return items


# ===== MCP Server（FastMCP）=====
mcp = FastMCP(
    name="chengdu-youth-activities",
    instructions="Fetch and parse latest activities from Chengdu Youth Center index page."
)

@mcp.tool()
def fetch_chengdu_youth_activities(limit: Optional[int] = None) -> List[Activity]:
    """
    抓取并解析“精彩活动”列表为结构化活动数组。
    参数:
      - limit: 可选，返回前 N 条（1..100）
    """
    if limit is not None and (limit <= 0 or limit > 100):
        raise ValueError("limit must be in 1..100")
    html = fetch_html()
    all_items = parse_activities(html)
    return all_items[:limit] if limit else all_items


# ===== SSE 服务器挂载 + 健康检查 =====
def build_app():
    app = Starlette(routes=[
        # mcp.sse_app() 默认提供 /sse 与 /messages 两个端点
        Mount("/", app=mcp.sse_app()),
        Route("/healthz", lambda request: PlainTextResponse("ok"), methods=["GET"]),
    ])
    # 浏览器端调试时可开 CORS（生产环境请收紧）
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
        expose_headers=["Mcp-Session-Id"],
    )
    return app

def main():
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "3000"))
    uvicorn.run(build_app(), host=host, port=port, log_level="info")

if __name__ == "__main__":
    main()
