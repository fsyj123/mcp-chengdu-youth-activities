# MCP Server · 成都青年之家活动抓取器（Python）

一个基于 **Model Context Protocol (MCP)** 的服务端，抓取并解析
[成都青年之家](https://cdyouth.cdcyl.org.cn/jgc/) 的最新「精彩活动」列表，返回**结构化活动数组**。

- 语言：Python 3.9+
- 传输：**SSE（Server-Sent Events）**
- 框架：Starlette + Uvicorn
- SDK：`mcp`（官方 Python SDK）+ `FastMCP`
- 解析：httpx + BeautifulSoup4 + lxml

---

## ✨ 功能特性

- 🔍 **GET 抓取**：请求 `https://cdyouth.cdcyl.org.cn/jgc/`，直接解析首页 HTML。
- 📝 **结构化输出**：活动 ID、标题、标签、分类、时间、地址、状态、浏览量、封面图、详情链接等。
- 🧩 **MCP Tool**：`fetch_chengdu_youth_activities(limit?: int)`。
- 🔄 **SSE 传输**：提供 `/sse`（建立会话）与 `/messages`（客户端发消息）端点。
- ❤️ **健康检查**：`/healthz` 返回 200 `ok`，便于托管/监控。

---

## 📦 安装

### 方式 A：从源代码本地安装（推荐开发用）
```bash
# 创建虚拟环境（可用 uv/pipenv/venv，以下以 uv 为例）
uv venv
uv pip install -e .
