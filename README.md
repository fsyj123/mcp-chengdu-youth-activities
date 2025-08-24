# MCP Server · 成都青年之家活动抓取器

一个基于 [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) 的服务端（Server），
用于抓取并解析 [成都青年之家](https://cdyouth.cdcyl.org.cn/jgc/) 的最新活动信息。

本项目提供一个 MCP Tool：`fetch_chengdu_youth_activities`  
通过 HTTP SSE Transport 暴露，调用时自动请求页面、解析 HTML，并返回结构化的活动列表。

---

## ✨ 功能特性

- 🔍 **抓取活动信息**：从 `https://cdyouth.cdcyl.org.cn/jgc/` 获取最新活动。
- 📝 **自动解析**：活动标题、标签、时间、地点、状态、浏览量、图片等。
- 📦 **MCP Tool 接口**：可直接在兼容 MCP 的客户端（如 Anthropic MCP Inspector）中使用。
- 🔄 **SSE Transport**：基于 Server-Sent Events 实现（兼容旧版 MCP 客户端）。
- 🧩 **结构化输出**：返回 JSON 数组，同时包含可读文本。

---

## 📦 安装与运行

### 1. 克隆仓库
```bash
git clone https://github.com/<yourname>/mcp-chengdu-youth-activities.git
cd mcp-chengdu-youth-activities
