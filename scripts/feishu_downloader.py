# -*- coding: utf-8 -*-
"""
飞书 Wiki 文档下载器（Cookie 版）
================================
通过飞书网页 API + 登录 Cookie 下载只读分享的 wiki 文档到本地。

用法:
    python feishu_downloader.py --url <wiki_url> --cookie "session=xxx; trust_browser=xxx" [--out <目录>]

说明:
    cookie 从浏览器复制: 打开飞书文档并登录 -> F12 -> Console 输入 document.cookie 复制,
    或 Application/存储 -> Cookies -> 复制关键项 (session 必填, trust_browser 最好带上)。
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import uuid
from html.parser import HTMLParser

try:
    import requests
except ImportError:
    print("缺少 requests 库, 请先执行: pip install requests")
    sys.exit(1)

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

# ---- block_type 数值 -> 名称 (新版 docx) ----
BLOCK_TEXT = 1
BLOCK_H1, BLOCK_H2, BLOCK_H3 = 2, 3, 4
BLOCK_H4, BLOCK_H5, BLOCK_H6 = 5, 6, 7
BLOCK_H7, BLOCK_H8, BLOCK_H9 = 8, 9, 10
BLOCK_BULLET, BLOCK_ORDERED, BLOCK_CODE = 11, 12, 13
BLOCK_QUOTE, BLOCK_CALLOUT = 14, 15
BLOCK_DIVIDER = 17
BLOCK_IMAGE = 18
BLOCK_FILE = 19
BLOCK_TABLE = 22
BLOCK_TASK = 24
BLOCK_SHEET = 26
BLOCK_BITABLE = 27
BLOCK_LINK_PREVIEW = 28


class FeishuDownloader:
    def __init__(self, host: str, cookie: str, out_dir: str, verbose: bool = False):
        self.host = host.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": UA,
            "Referer": f"{self.host}/",
            "Cookie": cookie,
        })
        self.out_dir = out_dir
        self.verbose = verbose
        os.makedirs(out_dir, exist_ok=True)
        self._img_dir = os.path.join(out_dir, "_images")
        os.makedirs(self._img_dir, exist_ok=True)
        self._downloaded_files = {}

    # ---------- 基础请求 ----------
    def _post(self, path: str, body=None, params=None):
        url = f"{self.host}{path}"
        r = self.session.post(url, json=body, params=params, timeout=30)
        return self._parse(r, url)

    def _get(self, path: str, params=None):
        url = f"{self.host}{path}"
        r = self.session.get(url, params=params, timeout=30)
        return self._parse(r, url)

    def _parse(self, r, url):
        if self.verbose:
            print(f"  [api] {r.status_code} {url}")
        if r.status_code == 401:
            raise RuntimeError("Cookie 无效或已过期, 请重新复制 Cookie")
        if r.status_code == 403:
            raise RuntimeError("无权限访问 (403), 确认账号能打开该文档")
        try:
            j = r.json()
        except Exception:
            raise RuntimeError(f"接口返回非 JSON: HTTP {r.status_code} @ {url}")
        if j.get("code") not in (0, None):
            raise RuntimeError(f"飞书接口错误 code={j.get('code')} msg={j.get('msg')} @ {url}")
        return j.get("data") or {}

    # ---------- wiki 解析 ----------
    def resolve_wiki(self, wiki_token: str):
        """wiki_token -> 节点信息(obj_token / obj_type / 标题)"""
        data = self._post("/space/api/wiki/v2/token_info/",
                          body={"wiki_token": wiki_token, "need_parse_attr": True})
        node = data.get("node") or {}
        obj_token = node.get("obj_token")
        obj_type = node.get("obj_type")
        title = node.get("title") or obj_token
        return obj_token, obj_type, title

    def wiki_children(self, wiki_token: str):
        """获取 wiki 节点的直接子节点列表"""
        children = []
        page_token = ""
        while True:
            params = {"wiki_token": wiki_token, "page_size": 50}
            if page_token:
                params["page_token"] = page_token
            data = self._get("/space/api/wiki/v2/node_children/", params=params)
            items = data.get("items") or []
            for it in items:
                children.append({
                    "wiki_token": it.get("wiki_token"),
                    "obj_token": it.get("obj_token"),
                    "obj_type": it.get("obj_type"),
                    "title": it.get("title"),
                })
            if not data.get("has_more"):
                break
            page_token = data.get("page_token") or ""
            if not page_token:
                break
        return children

    # ---------- docx: 读取 block ----------
    def get_docx_blocks(self, obj_token: str):
        data = self._post(f"/space/api/obj/{obj_token}/", body={
            "need_parse_block": True,
            "need_extra_info": False,
            "need_doc_gen_info": True,
            "token": obj_token,
        })
        blocks = data.get("block") or []
        return blocks

    # ---------- docx block -> markdown ----------
    def blocks_to_markdown(self, blocks, obj_token):
        md_lines = []
        for b in blocks:
            md_lines.append(self._block_to_md(b, blocks))
        # 去掉连续空行
        out = re.sub(r"\n{3,}", "\n\n", "\n".join(md_lines))
        return out.strip()

    def _block_to_md(self, b, all_blocks, indent=0):
        bt = b.get("block_type")
        md = ""
        if bt == BLOCK_TEXT:
            md = self._text_elements_to_md(b.get("text", {})) + "\n"
        elif BLOCK_H1 <= bt <= BLOCK_H9:
            level = bt - BLOCK_H1 + 1
            md = "#" * level + " " + self._text_elements_to_md(b.get("text", {})) + "\n"
        elif bt == BLOCK_BULLET:
            md = "  " * indent + "- " + self._text_elements_to_md(b.get("text", {})) + "\n"
        elif bt == BLOCK_ORDERED:
            md = "  " * indent + "1. " + self._text_elements_to_md(b.get("text", {})) + "\n"
        elif bt == BLOCK_TASK:
            done = (b.get("task") or {}).get("done")
            box = "[x]" if done else "[ ]"
            md = "  " * indent + f"- {box} " + self._text_elements_to_md(b.get("text", {})) + "\n"
        elif bt == BLOCK_QUOTE:
            md = "> " + self._text_elements_to_md(b.get("text", {})).replace("\n", "\n> ") + "\n"
        elif bt == BLOCK_CALLOUT:
            md = "> 💡 " + self._text_elements_to_md(b.get("text", {})).replace("\n", "\n> ") + "\n"
        elif bt == BLOCK_CODE:
            code = (b.get("code") or {})
            lang = code.get("language") or ""
            content = code.get("text") or ""
            md = f"```{lang}\n{content}\n```\n"
        elif bt == BLOCK_DIVIDER:
            md = "---\n"
        elif bt == BLOCK_IMAGE:
            img = b.get("image") or {}
            token = img.get("token")
            if token:
                local = self._download_image(token)
                if local:
                    md = f"![image]({local})\n"
                else:
                    md = ""
        elif bt == BLOCK_FILE:
            f_ = b.get("file") or {}
            name = f_.get("name") or "文件"
            token = f_.get("token")
            url = f_.get("url") or ""
            if token:
                url = f"{self.host}/space/api/box/stream/download/all/{token}/"
            md = f"[📎 {name}]({url})\n"
        elif bt == BLOCK_LINK_PREVIEW:
            lp = b.get("link_preview") or {}
            url = lp.get("url") or ""
            title = lp.get("title") or url
            md = f"[🔗 {title}]({url})\n"
        elif bt == BLOCK_TABLE:
            md = self._table_to_md(b, all_blocks)
        elif bt == BLOCK_SHEET:
            sheet = b.get("sheet") or {}
            token = sheet.get("token")
            md = f"\n[📊 内嵌表格 {token}]\n"
        elif bt == BLOCK_BITABLE:
            bitable = b.get("bitable") or {}
            token = bitable.get("token")
            md = f"\n[📋 内嵌多维表格 {token}]\n"
        else:
            # 未知类型: 尝试取文本
            t = self._text_elements_to_md(b.get("text", {}))
            if t:
                md = t + "\n"
        return md

    def _text_elements_to_md(self, text_block):
        elements = text_block.get("elements") or []
        parts = []
        for e in elements:
            run = e.get("text_run") or {}
            content = run.get("content") or ""
            style = run.get("text_element_style") or {}
            content = content.replace("\n", "\n")
            if style.get("bold"):
                content = f"**{content}**"
            if style.get("italic"):
                content = f"*{content}*"
            if style.get("underline"):
                content = f"<u>{content}</u>"
            if style.get("strike_through"):
                content = f"~~{content}~~"
            if style.get("inline_code"):
                content = f"`{content}`"
            link = style.get("link") or {}
            if link.get("url"):
                content = f"[{content}]({link['url']})"
            parts.append(content)
        return "".join(parts)

    def _table_to_md(self, b, all_blocks):
        table = b.get("table") or {}
        cells = table.get("cells") or []
        if not cells:
            return ""
        rows = []
        for row in cells:
            row_md = []
            for cell in row:
                cell_text = ""
                for cbid in cell:
                    cb = self._find_block(all_blocks, cbid)
                    if cb:
                        cell_text += self._block_to_md(cb, all_blocks)
                cell_text = cell_text.replace("\n", " ").strip()
                row_md.append(cell_text.replace("|", "\\|"))
            rows.append(row_md)
        n_cols = max(len(r) for r in rows) if rows else 0
        out = []
        for i, row in enumerate(rows):
            row = row + [""] * (n_cols - len(row))
            out.append("| " + " | ".join(row) + " |")
            if i == 0:
                out.append("| " + " | ".join(["---"] * n_cols) + " |")
        return "\n".join(out) + "\n"

    def _find_block(self, blocks, block_id):
        for b in blocks:
            if b.get("block_id") == block_id:
                return b
        return None

    def _download_image(self, token):
        if token in self._downloaded_files:
            return self._downloaded_files[token]
        url = f"{self.host}/space/api/box/stream/download/image/{token}/"
        try:
            r = self.session.get(url, timeout=30)
            if r.status_code == 200 and len(r.content) > 100:
                ext = self._guess_ext(r.headers.get("Content-Type", ""))
                fn = os.path.join(self._img_dir, f"{token}{ext}")
                with open(fn, "wb") as f:
                    f.write(r.content)
                rel = os.path.relpath(fn, self.out_dir).replace("\\", "/")
                self._downloaded_files[token] = rel
                return rel
        except Exception as e:
            if self.verbose:
                print(f"  [warn] 图片下载失败 {token}: {e}")
        self._downloaded_files[token] = None
        return None

    @staticmethod
    def _guess_ext(content_type):
        m = re.search(r"image/(\w+)", content_type or "")
        if not m:
            return ".png"
        ext = m.group(1).lower()
        return {".jpeg": ".jpg", "svg+xml": ".svg"}.get(ext, f".{ext}")

    # ---------- 导出任务 (sheet/bitable/兜底) ----------
    def export_task(self, obj_token, obj_type, file_extension, title):
        """创建导出任务并轮询下载, 返回本地文件路径"""
        data = self._post("/space/api/export_task/", body={
            "obj_type": obj_type,
            "obj_token": obj_token,
            "file_extension": file_extension,
            "sub_id": "",
            "need_more": True,
        })
        ticket = (data.get("ticket") or {}).get("ticket") or data.get("ticket")
        if not ticket:
            raise RuntimeError(f"导出任务创建失败: {data}")
        # 轮询
        for _ in range(30):
            time.sleep(1.5)
            info = self._get("/space/api/export_task/info/", params={"ticket": ticket})
            status = info.get("status") or info.get("job_status")
            result = info.get("result") or {}
            file_token = result.get("file_token")
            if file_token:
                # 下载
                dl = self._get("/space/api/export_task/download/", params={"ticket": ticket})
                if dl:
                    return self._save_download(dl, title, file_extension)
            if status in ("fail", "error", 3):
                raise RuntimeError(f"导出失败: {info}")
            if status in ("done", "success", 2):
                break
        raise RuntimeError("导出任务超时")

    def _save_download(self, data, title, ext):
        # data 可能是文件内容(bytes)或 json
        if isinstance(data, bytes):
            content = data
        elif isinstance(data, dict):
            # 有的接口直接返回 file_token 需要再下
            file_token = data.get("file_token")
            if not file_token:
                raise RuntimeError(f"下载响应异常: {data}")
            url = f"{self.host}/space/api/box/stream/download/all/{file_token}/"
            r = self.session.get(url, timeout=60)
            if r.status_code != 200:
                raise RuntimeError(f"文件下载失败: HTTP {r.status_code}")
            content = r.content
        else:
            raise RuntimeError(f"下载响应异常: {data}")
        fn = os.path.join(self.out_dir, f"{self._safe_name(title)}.{ext}")
        with open(fn, "wb") as f:
            f.write(content)
        return fn

    @staticmethod
    def _safe_name(name):
        name = re.sub(r'[\\/:*?"<>|\r\n\t]', "_", name).strip()
        return name[:80] or "untitled"

    # ---------- 旧版 doc 直下 ----------
    def download_doc_stream(self, obj_token, title):
        url = f"{self.host}/space/api/box/stream/download/all/{obj_token}/"
        r = self.session.get(url, timeout=60)
        if r.status_code == 200 and len(r.content) > 100:
            fn = os.path.join(self.out_dir, f"{self._safe_name(title)}.docx")
            with open(fn, "wb") as f:
                f.write(r.content)
            return fn
        return None

    # ---------- 主流程 ----------
    def download_wiki(self, wiki_token, title=None, depth=0):
        obj_token, obj_type, node_title = self.resolve_wiki(wiki_token)
        title = title or node_title
        indent = "  " * depth
        print(f"{indent}📄 [{obj_type}] {title} ({obj_token})")
        if obj_type == "docx":
            blocks = self.get_docx_blocks(obj_token)
            md = self.blocks_to_markdown(blocks, obj_token)
            fn = os.path.join(self.out_dir, f"{self._safe_name(title)}.md")
            with open(fn, "w", encoding="utf-8") as f:
                f.write(f"# {title}\n\n{md}")
            print(f"{indent}  ✅ -> {fn} ({len(md)} 字符)")
        elif obj_type == "doc":
            fn = self.download_doc_stream(obj_token, title)
            if fn:
                print(f"{indent}  ✅ -> {fn}")
            else:
                print(f"{indent}  ⚠️ 旧版 doc 直下失败, 尝试导出...")
                try:
                    fn = self.export_task(obj_token, "doc", "docx", title)
                    print(f"{indent}  ✅ -> {fn}")
                except Exception as e:
                    print(f"{indent}  ❌ {e}")
        elif obj_type in ("sheet", "bitable"):
            try:
                fn = self.export_task(obj_token, obj_type, "xlsx", title)
                print(f"{indent}  ✅ -> {fn}")
            except Exception as e:
                print(f"{indent}  ❌ {e}")
        else:
            print(f"{indent}  ⏭️ 暂不支持的文档类型: {obj_type}")
        # 递归子节点
        try:
            children = self.wiki_children(wiki_token)
            for ch in children:
                self.download_wiki(ch["wiki_token"], title=ch.get("title"), depth=depth + 1)
        except Exception as e:
            print(f"{indent}  ⏭️ 获取子节点失败: {e}")


def parse_wiki_token(url):
    m = re.search(r"/wiki/([A-Za-z0-9]+)", url)
    if m:
        return m.group(1)
    m = re.search(r"wiki_token=([A-Za-z0-9]+)", url)
    if m:
        return m.group(1)
    raise ValueError("无法从 URL 解析 wiki token")


def main():
    ap = argparse.ArgumentParser(description="飞书 Wiki 文档下载器 (Cookie 版)")
    ap.add_argument("--url", required=True, help="飞书 wiki 文档链接")
    ap.add_argument("--cookie", required=True, help='飞书登录 Cookie, 如 "session=xxx; trust_browser=xxx"')
    ap.add_argument("--out", default="./feishu_output", help="输出目录 (默认 ./feishu_output)")
    ap.add_argument("--verbose", action="store_true", help="打印调试信息")
    args = ap.parse_args()

    wiki_token = parse_wiki_token(args.url)
    host = re.match(r"(https?://[^/]+)", args.url).group(1)

    dl = FeishuDownloader(host, args.cookie, args.out, verbose=args.verbose)
    try:
        dl.download_wiki(wiki_token)
        print(f"\n✅ 全部完成, 文件保存在: {os.path.abspath(args.out)}")
    except Exception as e:
        print(f"\n❌ 失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
