import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { SSEServerTransport } from "@modelcontextprotocol/sdk/server/sse.js";
import express from "express";
import cors from "cors";
import { z } from "zod";
import { load } from "cheerio";

// =============== 业务逻辑：抓取 + 解析活动列表 ===============
const BASE = "https://cdyouth.cdcyl.org.cn";
const TARGET_URL = `${BASE}/jgc/`;

type Activity = {
  title: string;
  tags?: string | null;
  area?: string | null;
  venue?: string | null;
  dateTimeText?: string | null;
  status?: string | null;
  hits?: number | null;
};

const InputSchema = z.object({
  limit: z.number().int().positive().max(100).optional()
});

function absUrl(u?: string | null): string | null {
  if (!u) return null;
  if (u.startsWith("http://") || u.startsWith("https://")) return u;
  if (u.startsWith("//")) return `https:${u}`;
  return new URL(u, BASE).href;
}

function cleanText(s?: string | null): string | null {
  if (!s) return null;
  return s.replace(/\s+/g, " ").trim() || null;
}

async function fetchHtml(): Promise<string> {
  const ac = new AbortController();
  const t = setTimeout(() => ac.abort(), 20000);
  try {
    const res = await fetch(TARGET_URL, {
      method: "GET",
      signal: ac.signal,
      headers: {
        "User-Agent": "mcp-chengdu-youth-activities/1.1 (+https://cdyouth.cdcyl.org.cn)",
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Cache-Control": "no-cache",
        "Referer": TARGET_URL
      }
    });
    if (!res.ok) throw new Error(`HTTP ${res.status} ${res.statusText}`);
    return await res.text();
  } finally {
    clearTimeout(t);
  }
}

function parseActivities(html: string): Activity[] {
  const $ = load(html);
  const items: Activity[] = [];

  $("#main_list_result > li").each((_, li) => {
    const $li = $(li);

    const href = $li.find(".txt2 h2 a").attr("href") || $li.find(".img a").attr("href") || "";
    const url = absUrl(href)!;
    const id = url.match(/\/activity\/(\d+)/)?.[1];

    const $titleA = $li.find(".txt2 h2 a").clone();
    $titleA.find("span").remove();
    const title = cleanText($titleA.text()) || "(未命名活动)";

    const tags = cleanText($li.find(".txt2 h2 a span").text()) || null;
    const area = cleanText($li.find(".area").text());

    const $h3 = $li.find(".txt2 h3");
    const venue = cleanText($h3.text());
    const zhijiaId = $h3.attr("zhijiaid") || null;

    const $h4 = $li.find(".txt2 h4").clone();
    $h4.find("a, em").remove();
    const dateTimeText = cleanText($h4.text());
    const status = cleanText($li.find(".txt2 h4 a").text());

    const hitsTxt = $li.find(".hits").text().replace(/[^\d]/g, "");
    const hits = hitsTxt ? parseInt(hitsTxt, 10) : null;

    const image = absUrl($li.find(".img_con img").attr("src"));

    items.push({
      title, tags, area, venue, dateTimeText, status, hits
    });
  });

  return items;
}

async function getActivities(limit?: number): Promise<Activity[]> {
  const html = await fetchHtml();
  const all = parseActivities(html);
  return typeof limit === "number" ? all.slice(0, limit) : all;
}

// =============== MCP Server 注册工具 ===============
const server = new McpServer({
  name: "chengdu-youth-activities",
  version: "1.1.0"
});

server.registerTool(
  "fetch_chengdu_youth_activities",
  {
    title: "获取成都青年之家最新活动",
    description: "GET https://cdyouth.cdcyl.org.cn/jgc/ 并解析“精彩活动”列表为活动数组。",
    inputSchema: { limit: z.number().int().positive().max(100).optional() }
  },
  async ({ limit }: z.infer<typeof InputSchema>) => {
    const activities = await getActivities(limit);
    const jsonText = JSON.stringify(activities, null, 2);
    return {
      structuredContent: activities
    };
  }
);

// =============== SSE Transport + Express ===============
const app = express();

// 若要允许浏览器侧 MCP 客户端（如 Inspector）直连，可按需放开 CORS
app.use(cors({
  origin: "*",
  allowedHeaders: ["Content-Type", "mcp-session-id"],
  exposedHeaders: ["Mcp-Session-Id"]
}));
app.use(express.json({ limit: "1mb" }));

// 保存每个 SSE 会话对应的 transport
const transports: Record<string, SSEServerTransport> = {};

// SSE 端点：建立服务端推送连接（server -> client）
app.get("/sse", async (req, res) => {
  // 创建一个 SSE 传输；“/messages” 是客户端发消息用的 POST 端点
  const transport = new SSEServerTransport("/messages", res);
  transports[transport.sessionId] = transport;

  // 连接 MCP Server
  await server.connect(transport);

  // 连接关闭时清理
  res.on("close", () => {
    transport.close();
    delete transports[transport.sessionId];
  });
});

// 消息端点：客户端 -> 服务器（JSON-RPC）
app.post("/messages", async (req, res) => {
  const sessionId = (req.query.sessionId as string) || "";
  const transport = transports[sessionId];
  if (!transport) {
    res.status(400).send("No transport found for sessionId");
    return;
  }
  // 交给传输层处理 JSON-RPC 请求体
  await transport.handlePostMessage(req as any, res as any, req.body);
});

// 健康检查
app.get("/healthz", (_req, res) => res.status(200).send("ok"));

const PORT = Number(process.env.PORT || 3000);
app.listen(PORT, () => {
  console.error(`MCP SSE server listening on http://localhost:${PORT}`);
});
