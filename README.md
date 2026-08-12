# FeatherScoop 🪶

**飞书文档下载器 · Feishu / Lark Document Downloader**

<div align="center">

[![GitHub Stars](https://img.shields.io/github/stars/xiao-chengguo/FeatherScoop?style=social)](https://github.com/xiao-chengguo/FeatherScoop/stargazers)
[![GitHub Forks](https://img.shields.io/github/forks/xiao-chengguo/FeatherScoop?style=social)](https://github.com/xiao-chengguo/FeatherScoop/network/members)
[![License](https://img.shields.io/badge/License-MIT-blue)](LICENSE)
[![简体中文](https://img.shields.io/badge/🇨🇳_简体中文-Current-green)](README.md)
[![English](https://img.shields.io/badge/🇺🇸_English-Version-blue)](README.en.md)

**简体中文** · [English](README.en.md)

</div>

> 🪶 **只要你能在线预览，就能拿到原始文件** —— 即使分享者关闭了"下载"按钮。

**FeatherScoop 是一款飞书（Feishu / Lark）只读分享文档的批量下载工具**：飞书知识库备份、飞书附件批量下载（PDF / 表格 / 文档）、飞书 wiki 文档同步、企业资料归档、课程资料导出…… 全部附件一键落盘，自动按目录分组、增量同步、生成索引，免登录配置、零依赖。

[✨ 核心特性](#-核心特性) · [🚀 快速开始](#-快速开始) · [🧠 工作原理](#-工作原理) · [🔍 适用场景](#-适用场景) · [⚠️ 免责声明](#️-免责声明) · [📄 许可](#-许可)

---

## ✨ 核心特性

| 特性 | 说明 |
|------|------|
| 🪶 **免登录配置** | CDP 复用 Chrome 登录态，飞书文档下载无需输密码、无需复制 Cookie |
| 📥 **突破下载限制** | 下载按钮被禁（`download/all` → 403）？预览流 `preview` 返回**完整原始文件** |
| 📂 **自动分组归档** | 附件按页面目录自动归档（`【资料】` 前缀 → 访谈资料目录） |
| 🔄 **增量同步** | 已下载且大小一致的文件自动跳过，适合"持续更新中"的飞书文档 |
| 📇 **自动索引** | 每次下载后自动生成 README 索引，飞书知识库一键归档 |
| 📦 **零依赖** | Node 22+ 内置 `fetch` + `WebSocket`，附带 Python 兜底版 |

## 🚀 快速开始

### 前置条件

- Google Chrome（至少登录过一次飞书 / Lark）
- Node.js 22+（**无需任何 npm 包**）

### 四步下载

```bash
# 1. 启动带 CDP 调试端口的 Chrome（复用你的飞书登录态）
chrome.exe --remote-debugging-port=9222 --user-data-dir="%USERPROFILE%\chrome-debug-profile" --remote-allow-origins=*

# 2. 在该 Chrome 登录飞书，导航到目标文档（wiki / docx 均可）

# 3. 提取附件清单（飞书文档 block 数据）
node scripts/cdp_frames.js eval "JSON.stringify((function(){const bm=DATA.clientVars.data.block_map;const files=[];for(const k of Object.keys(bm)){const b=bm[k];const d=b.data||{};if(d.type==='file'){files.push({token:d.file.token,name:d.file.name,size:d.file.size})}}return files})())" 1 > block_files.json

# 4. 提取 Cookie 并批量下载
node scripts/cdp_eval.js cookies "feishu.cn" > cookies.txt
node scripts/download_files.js block_files.json "你的输出目录"
```

文档更新后，**重跑第 3–4 步**即可增量补齐（已下载的自动跳过）。

## 🧠 工作原理

1. **登录态复用** — 飞书文档需登录。复制 Chrome profile 到调试浏览器，打开 wiki 页即为已登录状态。
2. **数据来源** — 文档完整 block 数据在 iframe 的 `window.DATA.clientVars.data.block_map`（SSR 注入）。
3. **关键突破** — `download/all/{token}` 被禁（403）时，`preview/{token}?preview_type=16&mount_point=docx_file` 返回**完整原始文件**。

## 🔍 适用场景

- 🏢 **飞书知识库（wiki）整体备份 / 迁移**
- 📄 **飞书文档附件（PDF / 表格 / 文档）批量下载**
- 🔒 分享者关闭下载权限的**只读资料归档**
- 🎓 飞书课程、内部培训资料本地留存
- 🔁 "持续更新中"的飞书文档增量同步

## 📦 脚本清单

| 脚本 | 作用 |
|------|------|
| `scripts/cdp_eval.js` | 极简 CDP 客户端：开页 / 执行 JS / 提取 Cookie / fetch |
| `scripts/cdp_frames.js` | 在文档 iframe 中执行 JS（提取 block 数据） |
| `scripts/cdp_listen.js` | CDP Network 域监听，发现真实 API 请求 |
| `scripts/download_files.js` | **主下载器 v2**：下载 + 自动分组 + 增量跳过 + README 索引 |
| `scripts/feishu_downloader.py` | Python 兜底版（Cookie + API，docx 渲染 Markdown） |

## 🐛 已知问题

- 租户域名 `/space/api` 对无效会话返回 **404**（不是 401）——重新登录即可
- 大文件（65MB+）下载没问题，但别用 CDP eval 传 base64（消息超限）
- `cookies.txt` 含你的登录会话——注意保密，用完即删

## ⚠️ 免责声明

请仅用于**你有权访问**、且个人/合法用途的内容。尊重分享者的意图与飞书服务条款。FeatherScoop 是研究/工具项目，使用者自行承担一切责任。

## 📄 许可

[MIT](./LICENSE) — 个人与商用免费，注明出处即可。

---

💬 **遇到问题？** 欢迎提交 [Issue](https://github.com/xiao-chengguo/FeatherScoop/issues) | ⭐ 觉得好用请点 Star，支持持续更新

*FeatherScoop —— 看得见的，就能拿得到。*
