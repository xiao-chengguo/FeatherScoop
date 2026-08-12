#!/usr/bin/env node
// cdp_eval.js - 极简 CDP 客户端: 打开页面 / 执行 JS / 拿 cookie
// 用法:
//   node cdp_eval.js open <url>
//   node cdp_eval.js eval <js-code> [tabId]
//   node cdp_eval.js list
//   node cdp_eval.js cookies [host]         # 通过 Network.getAllCookies 拿指定域的 cookie(含 HttpOnly)
//   node cdp_eval.js fetch <method> <path> [body-json] [tabId]  # 在页面上下文 fetch(同源带cookie)

const http = require("http");

const CDP = "http://127.0.0.1:9222";

function httpReq(url, method = "GET", body = null) {
  return new Promise((resolve, reject) => {
    const u = new URL(url);
    const req = http.request(
      { hostname: u.hostname, port: u.port, path: u.pathname + u.search, method, headers: body ? { "Content-Type": "application/json" } : {} },
      (res) => {
        let d = "";
        res.on("data", (c) => (d += c));
        res.on("end", () => resolve({ status: res.statusCode, body: d }));
      }
    );
    req.on("error", reject);
    if (body) req.write(JSON.stringify(body));
    req.end();
  });
}

async function listTabs() {
  const r = await httpReq(`${CDP}/json/list`);
  return JSON.parse(r.body);
}

async function newTab(url) {
  const r = await httpReq(`${CDP}/json/new?${encodeURIComponent(url)}`, "PUT");
  return JSON.parse(r.body);
}

function cdpCall(wsUrl, method, params) {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(wsUrl);
    const id = Math.floor(Math.random() * 1e9);
    const timer = setTimeout(() => { try { ws.close(); } catch {} reject(new Error("CDP timeout")); }, 30000);
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
    ws.onerror = (e) => { clearTimeout(timer); reject(new Error("WS error")); };
  });
}

async function evalInTab(tabId, expression) {
  const tabs = await listTabs();
  const tab = tabs.find((t) => t.id === tabId) || tabs.find((t) => t.type === "page") || tabs[0];
  if (!tab) throw new Error("无可用 tab");
  const res = await cdpCall(tab.webSocketDebuggerUrl, "Runtime.evaluate", {
    expression,
    returnByValue: true,
    awaitPromise: true,
    userGesture: true,
  });
  if (res.exceptionDetails) {
    return { error: res.exceptionDetails.exception?.description || res.exceptionDetails.text };
  }
  return res.result?.value;
}

async function getCookies(host) {
  const tabs = await listTabs();
  const tab = tabs.find((t) => t.type === "page") || tabs[0];
  const res = await cdpCall(tab.webSocketDebuggerUrl, "Network.getAllCookies", {});
  const cookies = (res.cookies || []).filter((c) => !host || c.domain.includes(host));
  return cookies.map((c) => `${c.name}=${c.value}`);
}

async function main() {
  const [cmd, ...rest] = process.argv.slice(2);
  if (cmd === "open") {
    const t = await newTab(rest[0]);
    console.log(`TAB_ID=${t.id}`);
  } else if (cmd === "list") {
    const tabs = await listTabs();
    for (const t of tabs) console.log(`${t.type} ${t.id} ${t.url}`);
  } else if (cmd === "eval") {
    const expr = rest[0];
    const tabId = rest[1];
    const out = await evalInTab(tabId, expr);
    console.log(typeof out === "string" ? out : JSON.stringify(out));
  } else if (cmd === "cookies") {
    const out = await getCookies(rest[0]);
    console.log(out.join("; "));
  } else if (cmd === "fetch") {
    const [method, path, bodyJson, tabId] = rest;
    const expr = `(async()=>{const r=await fetch(${JSON.stringify(path)},{method:${JSON.stringify(method)},headers:{'Content-Type':'application/json'},body:${bodyJson ? JSON.stringify(bodyJson) : "undefined"},credentials:'include'});const t=await r.text();let j;try{j=JSON.parse(t)}catch(e){j=t.slice(0,2000)}return JSON.stringify({status:r.status,data:j});})()`;
    const out = await evalInTab(tabId, expr);
    console.log(typeof out === "string" ? out : JSON.stringify(out));
  } else {
    console.log("未知命令: " + cmd);
  }
}

main().catch((e) => { console.error("ERR:", e.message); process.exit(1); });
