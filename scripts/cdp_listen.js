#!/usr/bin/env node
// cdp_listen.js - 监听 CDP Network 请求
// 用法: node cdp_listen.js <秒数> [url过滤]
const http = require("http");
const CDP = "http://127.0.0.1:9222";

function httpReq(url) {
  return new Promise((resolve, reject) => {
    http.get(url, (res) => {
      let d = "";
      res.on("data", (c) => (d += c));
      res.on("end", () => resolve(d));
    }).on("error", reject);
  });
}

async function main() {
  const seconds = parseInt(process.argv[2] || "10", 10);
  const filter = process.argv[3] || "";
  const list = JSON.parse(await httpReq(`${CDP}/json/list`));
  const tab = list.find((t) => t.type === "page") || list[0];
  const ws = new WebSocket(tab.webSocketDebuggerUrl);
  let count = 0;
  ws.onopen = () => {
    ws.send(JSON.stringify({ id: 1, method: "Network.enable", params: {} }));
    setTimeout(() => {
      console.error(`\n--- 监听结束, 共 ${count} 个请求 ---`);
      try { ws.close(); } catch {}
      process.exit(0);
    }, seconds * 1000);
  };
  ws.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.method === "Network.requestWillBeSent") {
      const r = msg.params.request;
      const url = r.url || "";
      if (url.includes("/space/api/") || url.includes("/api/") || url.includes(filter)) {
        count++;
        console.log(`${r.method} ${url}`);
      }
    }
  };
}
main().catch((e) => { console.error("ERR:", e.message); process.exit(1); });
