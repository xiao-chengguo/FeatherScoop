# FeatherScoop 🪶

**Download files from Feishu / Lark read-only shared documents — even when the download button is disabled.**

FeatherScoop lets you save every attachment (PDF, docs, etc.) embedded in a Feishu (Lark) wiki/document that you can *view* but not *download*. It reuses your browser login session via CDP, reads the document's block data, and fetches the original files through the **preview stream** — no tokens, no API keys, no manual cookie copying.

> ⚖️ **Disclaimer**: Use this tool only for documents you are authorized to access, for personal/legal purposes. Respect the sharer's intent and the platform's terms of service. FeatherScoop is a research/utility project — you are responsible for how you use it.

---

## ✨ Features

| Feature | Detail |
|---|---|
| 🪶 Zero-config login | Reuses your Chrome login session via CDP — no passwords, no cookies to copy |
| 📥 Downloads disabled files | Preview stream returns the *original* file even when `download/all` returns 403 |
| 📂 Auto folder grouping | Files starting with `【资料】` → `访谈嘉宾资料/`, others → `其他资料/` (configurable) |
| 🔄 Incremental sync | Skips already-downloaded files (size match) — perfect for "constantly updating" docs |
| 📇 Auto index | Generates a `README.md` index with links after every run |
| 📦 Zero npm deps | Node 22+ built-in `fetch` + `WebSocket`, Python fallback included |

## 🧠 How it works (the interesting part)

1. **Login reuse** — Feishu docs require login. `browser-cdp` copies your Chrome profile (cookies included) into a debug Chrome on port 9222, so opening the wiki page is already authenticated.
2. **Block data** — The document's full content lives in `window.DATA.clientVars.data.block_map` (SSR-injected). Each `file` block has `{token, name, size}`.
3. **The key trick** — `download/all/{token}` → **403** (download permission disabled by the sharer). But `preview/{token}?preview_type=16&mount_point=docx_file` → **200 with the complete original file**. If you're allowed to preview it, you can retrieve the original.

## 🚀 Quick Start

### Prerequisites

- Google Chrome (logged into Feishu at least once)
- Node.js 22+ (no npm packages needed)

### Run

```bash
# 1. Start Chrome with a CDP debugging port (reusing your login)
#    Windows: close running Chrome first, then:
#    "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="%USERPROFILE%\chrome-debug-profile" --remote-allow-origins=*
#    macOS:
#    /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222 --user-data-dir="$HOME/chrome-debug-profile" --remote-allow-origins=*
#    (Tip: copy your default profile's Cookies file into chrome-debug-profile to skip login)

# 2. Open the wiki page & confirm it renders (logged in)
node scripts/cdp_eval.js open "https://<your-tenant>.feishu.cn/wiki/<wiki_token>"
sleep 8
node scripts/cdp_eval.js eval "JSON.stringify({title:document.title,url:location.href})"

# 3. Extract attachment manifest (tokens/names/sizes) from the document iframe
node scripts/cdp_frames.js eval "JSON.stringify((function(){const bm=DATA.clientVars.data.block_map;const files=[];for(const k of Object.keys(bm)){const b=bm[k];const d=b.data||{};if(d.type==='file'){files.push({token:d.file.token,name:d.file.name,size:d.file.size})}}return files})())" 1 > block_files.json

# 4. Capture your session cookie (incl. HttpOnly)
node scripts/cdp_eval.js cookies "feishu.cn" > cookies.txt

# 5. Download everything (auto-grouped + incremental + index)
node scripts/download_files.js block_files.json "path/to/output/folder"
```

Document updated later? Just re-run steps 3–5 — already-downloaded files are skipped.

## 📦 Scripts

| Script | Purpose |
|---|---|
| `scripts/cdp_eval.js` | Minimal CDP client: open page / eval JS / dump cookies / fetch |
| `scripts/cdp_frames.js` | Execute JS inside a specific frame (the document iframe is a separate OOPIF target) |
| `scripts/cdp_listen.js` | Listen to CDP Network events to discover real API endpoints |
| `scripts/download_files.js` | **Main downloader v2**: download + auto-group + incremental skip + README index |
| `scripts/feishu_downloader.py` | Python fallback (cookies + API, renders docx to Markdown) |

## 🧩 Customization

- **Grouping rule** — edit `categoryOf()` in `download_files.js` (default: names starting with `【资料】` → `访谈嘉宾资料/`).
- **Force re-download** — add `--force`.
- **Other tenants** — the preview-stream domain `internal-api-drive-stream.feishu.cn` is shared by all Feishu tenants; only the wiki URL changes.

## 🐛 Known pitfalls

- Tenant-domain `/space/api` returns **404** for invalid sessions (not 401) — don't misread it as a wrong path.
- Page reloads wipe JS hooks — use `cdp_listen.js` (CDP Network domain) instead of in-page hooks.
- The preview iframe is an OOPIF with its own CDP target (`type=iframe`) — `cdp_frames.js` handles this.
- Git-Bash `/c/...` paths must become `C:/...` for Windows Node/Python.
- `cookies.txt` contains your login session — keep it private, delete after use.

## 📄 License

[MIT](./LICENSE) — free for personal & commercial use, attribution appreciated.

---

*Built with FeatherScoop — scoop what you can see.*
