# FeatherScoop 🪶

**飞书 / Lark 只读分享文档附件下载器——即使分享者关闭了"下载"按钮，只要你能在线预览，就能拿到原始文件。**

FeatherScoop 可以批量保存飞书 wiki/文档中嵌入的全部附件（PDF 等）。通过 CDP 复用你的浏览器登录态，读取文档 block 数据，走**预览流**拿到原始文件——无需 Token、无需 API Key、无需手动复制 Cookie。

> ⚖️ **免责声明**：请仅用于你有权访问、且个人/合法用途的内容。尊重分享者的意图与平台服务条款。本项目仅供学习与研究，使用者自行承担一切责任。

---

## ✨ 功能特性

| 功能 | 说明 |
|---|---|
| 🪶 免登录配置 | CDP 复用 Chrome 登录态，不输密码、不复制 Cookie |
| 📥 突破下载限制 | `download/all` 返回 403 时，预览流返回**完整原始文件** |
| 📂 自动分组 | 文件名以 `【资料】` 开头 → `访谈嘉宾资料/`，其余 → `其他资料/`（可自定义） |
| 🔄 增量同步 | 已下载且大小一致的文件自动跳过，适合"持续更新"的文档 |
| 📇 自动索引 | 每次下载后自动生成带链接的 README.md 索引 |
| 📦 零依赖 | Node 22+ 内置 fetch + WebSocket，附带 Python 兜底版 |

## 🧠 工作原理（核心看点）

1. **登录态复用** — 飞书文档需登录。`browser-cdp` 把你的 Chrome profile（含 Cookie）复制到调试 Chrome（端口 9222），打开 wiki 页即为已登录状态。
2. **数据来源** — 文档完整内容在 `window.DATA.clientVars.data.block_map`（SSR 注入）。每个 file 块含 `{token, name, size}`。
3. **关键突破** — `download/all/{token}` → **403**（分享者关闭了下载权限）；但 `preview/{token}?preview_type=16&mount_point=docx_file` → **200 返回完整原始文件**。能预览 = 能拿到原文件。

## 🚀 快速开始

### 前置条件

- Google Chrome（至少登录过一次飞书）
- Node.js 22+（无需任何 npm 包）

### 五步下载

```bash
# 1. 启动带 CDP 调试端口的 Chrome（复用你的登录态）
#    Windows: 先关闭正在运行的 Chrome，然后：
#    "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="%USERPROFILE%\chrome-debug-profile" --remote-allow-origins=*
#    macOS:
#    /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222 --user-data-dir="$HOME/chrome-debug-profile" --remote-allow-origins=*
#    （复制登录态：把 Chrome 默认 profile 的 Cookies 文件拷到 chrome-debug-profile 即可免登录）

# 2. 打开文档页（确认已登录、内容正常渲染）
node scripts/cdp_eval.js open "https://<你的租户>.feishu.cn/wiki/<wiki_token>"
sleep 8
node scripts/cdp_eval.js eval "JSON.stringify({title:document.title,url:location.href})"

# 3. 从文档 iframe 提取附件清单（token/name/size）
node scripts/cdp_frames.js eval "JSON.stringify((function(){const bm=DATA.clientVars.data.block_map;const files=[];for(const k of Object.keys(bm)){const b=bm[k];const d=b.data||{};if(d.type==='file'){files.push({token:d.file.token,name:d.file.name,size:d.file.size})}}return files})())" 1 > block_files.json

# 4. 提取登录 Cookie（含 HttpOnly session）
node scripts/cdp_eval.js cookies "feishu.cn" > cookies.txt

# 5. 一键下载（自动分组 + 增量跳过 + 生成索引）
node scripts/download_files.js block_files.json "输出目录"
```

文档更新后，**重跑第 3–5 步**即可增量补齐（已下载的自动跳过）。

## 📦 脚本清单

| 脚本 | 作用 |
|---|---|
| `scripts/cdp_eval.js` | 极简 CDP 客户端：开页 / 执行 JS / 提取 Cookie / fetch |
| `scripts/cdp_frames.js` | 在指定 frame（文档 iframe 是独立 OOPIF target）执行 JS |
| `scripts/cdp_listen.js` | CDP Network 域监听，发现真实 API 请求 |
| `scripts/download_files.js` | **主下载器 v2**：下载 + 自动分组 + 增量跳过 + README 索引 |
| `scripts/feishu_downloader.py` | Python 兜底版（Cookie + API，docx 渲染 Markdown） |

## 🧩 自定义

- **分组规则** — 改 `download_files.js` 里的 `categoryOf()`（默认：`【资料】` 前缀 → `访谈嘉宾资料/`）
- **强制重下** — 加 `--force` 参数
- **其他租户** — 预览流域名 `internal-api-drive-stream.feishu.cn` 所有飞书租户通用，只需换 wiki URL

## 🐛 已知坑

- 租户域名 `/space/api` 对无效会话返回 **404**（不是 401）——别误判为路径错
- 页面刷新会重置 JS hook——抓真实 API 用 `cdp_listen.js`（CDP Network 域），别在页面内 hook
- 预览 iframe 是 OOPIF，有独立 CDP target（`type=iframe`）——`cdp_frames.js` 已封装处理
- Git Bash 的 `/c/...` 路径要转成 `C:/...` 给 Windows Node/Python 用
- `cookies.txt` 含你的登录会话——注意保密，用完即删

## 📄 许可

[MIT](./LICENSE) — 个人与商用免费，注明出处即可。

---

*FeatherScoop —— 看得见的，就能拿得到。*
