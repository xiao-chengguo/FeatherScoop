#!/usr/bin/env node
// download_files.js - 飞书文档附件批量下载器（v2: 下载+按目录分组+增量跳过+自动索引）
// 用法: node download_files.js <block_files.json> <输出目录> [--force]
//   - 按页面目录规则分组: 文件名以"【资料】"开头 -> 访谈嘉宾资料/ ; 其余 -> 其他资料/
//   - 增量模式: 已存在且大小一致的文件自动跳过（支持文档"持续更新"场景）
//   - 下载完成自动生成 README.md 索引

const fs = require("fs");
const path = require("path");

const CONCURRENCY = 4;
const UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36";

function safeName(name) {
  let n = String(name || "").replace(/[\\/:*?"<>|\r\n\t]/g, "_").trim();
  n = n.replace(/[. ]+$/g, "");
  return n || "untitled";
}

/** 按飞书页面目录规则分组: 【资料】开头 -> 访谈嘉宾资料, 否则 -> 其他资料 */
function categoryOf(name) {
  return name.startsWith("【资料】") ? "访谈嘉宾资料" : "其他资料";
}

async function downloadOne(f, cookie, outDir, force) {
  const dir = path.join(outDir, categoryOf(f.name));
  fs.mkdirSync(dir, { recursive: true });
  const ext = path.extname(f.name) || ".pdf";
  const name = safeName(path.basename(f.name, ext)) + ext;
  const target = path.join(dir, name);

  // 增量跳过: 文件已存在且大小一致
  if (!force && fs.existsSync(target)) {
    const st = fs.statSync(target);
    if (st.size === f.size) return { name, dir, status: "skip", size: st.size };
  }

  const url = `https://internal-api-drive-stream.feishu.cn/space/api/box/stream/download/preview/${f.token}?preview_type=16&mount_point=docx_file`;
  const r = await fetch(url, {
    headers: {
      Cookie: cookie,
      "User-Agent": UA,
      Referer: "https://internal-api-drive-stream.feishu.cn/",
      Origin: "https://internal-api-drive-stream.feishu.cn",
    },
  });
  if (r.status !== 200) throw new Error(`HTTP ${r.status}`);
  const buf = Buffer.from(await r.arrayBuffer());
  fs.writeFileSync(target, buf);
  return { name, dir, status: buf.length === f.size ? "ok" : "size-mismatch", size: buf.length, expect: f.size };
}

async function main() {
  const [input, outDir, flag] = process.argv.slice(2);
  if (!input || !outDir) {
    console.error("用法: node download_files.js <block_files.json> <输出目录> [--force]");
    process.exit(1);
  }
  const force = flag === "--force";
  let files = JSON.parse(fs.readFileSync(input, "utf8"));
  if (!Array.isArray(files) && files.files) {
    // 兼容 {files:[...]} 结构
    files = files.files;
  }
  const cookie = fs.readFileSync(path.join(path.dirname(input), "cookies.txt"), "utf8").trim();
  fs.mkdirSync(outDir, { recursive: true });

  console.log(`📁 输出目录: ${outDir}`);
  console.log(`📄 共 ${files.length} 个文件, 并发 ${CONCURRENCY}${force ? " (强制重下)" : " (增量跳过已存在)"}\n`);

  let ok = 0, skip = 0, fail = 0, done = 0;
  const queue = [...files];
  async function worker() {
    while (queue.length) {
      const f = queue.shift();
      try {
        const r = await downloadOne(f, cookie, outDir, force);
        const mark = r.status === "ok" ? "✅" : r.status === "skip" ? "⏭️" : "⚠️";
        if (r.status === "ok") ok++;
        else if (r.status === "skip") skip++;
        else fail++;
        console.log(`${mark} [${++done}/${files.length}] [${r.dir}] ${r.name} (${(r.size / 1024 / 1024).toFixed(2)}MB)`);
      } catch (e) {
        fail++;
        console.log(`❌ [${++done}/${files.length}] ${f.name}: ${e.message}`);
      }
    }
  }
  await Promise.all(Array.from({ length: CONCURRENCY }, worker));

  // 生成 README 索引
  const cats = {};
  for (const f of files) {
    const cat = categoryOf(f.name);
    if (!cats[cat]) cats[cat] = [];
    const ext = path.extname(f.name) || ".pdf";
    cats[cat].push(safeName(path.basename(f.name, ext)) + ext);
  }
  let md = `# 飞书文档附件合集\n\n`;
  md += `> 📄 共 ${files.length} 个文件\n> ⏰ 整理时间: ${new Date().toLocaleString("zh-CN")}\n\n---\n\n`;
  for (const [cat, list] of Object.entries(cats)) {
    md += `## 📁 ${cat}（共 ${list.length} 个）\n\n`;
    list.sort().forEach((n) => { md += `- [📄 ${n}](./${cat}/${encodeURI(n)})\n`; });
    md += "\n";
  }
  fs.writeFileSync(path.join(outDir, "README.md"), md, "utf8");

  console.log(`\n📊 完成: ✅${ok} ⏭️${skip} ⚠️/❌${fail}`);
}

main().catch((e) => { console.error("FATAL:", e); process.exit(1); });
