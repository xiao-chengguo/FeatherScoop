#!/usr/bin/env node
// cdp_frames.js - 查看 frame 树, 并在指定 frame 执行 JS
// 用法:
//   node cdp_frames.js tree                # 打印 frame 树
//   node cdp_frames.js eval <expr> [idx]   # 在 frame 树第 idx 个 frame 执行
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

function cdpCall(wsUrl, method, params) {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(wsUrl);
    const id = Math.floor(Math.random() * 1e9);
    const timer = setTimeout(() => { try { ws.close(); } catch {} reject(new Error("timeout")); }, 30000);
    ws.onopen = () => ws.send(JSON.stringify({ id, method, params: params || {} }));
    ws.onmessage = (ev) => {
      const msg = JSON.parse(ev.data);
      if (msg.id === id) {
        clearTimeout(timer);
        try { ws.close(); } catch {}
        if (msg.error) reject(new Error(JSON.stringify(msg.error)));
        else resolve(msg.result);
      }
    };
    ws.onerror = () => { clearTimeout(timer); reject(new Error("WS error")); };
  });
}

function flatten(tree, out = []) {
  out.push(tree.frame);
  (tree.childFrames || []).forEach((c) => flatten(c, out));
  return out;
}

async function main() {
  const cmd = process.argv[2];
  const list = JSON.parse(await httpReq(`${CDP}/json/list`));
  const tab = list.find((t) => t.type === "page" && !t.url.includes("omnibox")) || list[0];
  const wsUrl = tab.webSocketDebuggerUrl;
  if (cmd === "tree") {
    const r = await cdpCall(wsUrl, "Page.getFrameTree", {});
    const frames = flatten(r.frameTree);
    frames.forEach((f, i) => console.log(`${i} ${f.id} ${(f.url || "").slice(0, 100)}`));
  } else if (cmd === "eval") {
    const expr = process.argv[3];
    const idx = parseInt(process.argv[4] || "0", 10);
    const r = await cdpCall(wsUrl, "Page.getFrameTree", {});
    const frames = flatten(r.frameTree);
    const frame = frames[idx];
    if (!frame) throw new Error(`无 frame ${idx}`);
    const res = await cdpCall(wsUrl, "Runtime.evaluate", {
      expression: expr,
      contextId: frame.contextId,
      returnByValue: true,
      awaitPromise: true,
    });
    console.log(typeof res.result?.value === "string" ? res.result.value : JSON.stringify(res.result?.value ?? res));
  }
}
main().catch((e) => { console.error("ERR:", e.message); process.exit(1); });
