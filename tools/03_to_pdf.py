#!/usr/bin/env python3
"""03_投递方案.md → A4 单页 PDF。

用法：
    python3 tools/03_to_pdf.py <03_投递方案.md> [输出.pdf]

依赖：Chrome（或用 CHROME 环境变量指定路径）。没有 Chrome 时只输出 HTML，不报错。
行为：若排出来超过 1 页，自动按 0.96/0.92/0.88/0.84/0.80 逐档缩小字号与间距，
      压到 1 页为止（不缩放布局盒，避免表格列宽变形）。
验证：跑完打印 Pages，必须为 1。
"""
import html
import os
import re
import subprocess
import sys
import tempfile

CHROME = os.environ.get(
    "CHROME", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
)


def build_css(k: float = 1.0) -> str:
    """k = 整体缩放系数，同时缩放字号/间距/页边距（不用 zoom，避免 fixed 表格变形）。"""
    return f"""
@page {{ size: A4; margin: {9*k:.2f}mm {7*k:.2f}mm; }}
* {{ box-sizing: border-box; }}
body {{ font: {10.2*k:.2f}px/1.5 -apple-system,"PingFang SC","Hiragino Sans GB",sans-serif;
       color:#2c3e50; margin:0; }}
h1 {{ font-size:{15*k:.2f}px; margin:0 0 {6*k:.2f}px; color:#1a252f; }}
h2 {{ font-size:{12*k:.2f}px; margin:{9*k:.2f}px 0 {3*k:.2f}px;
     padding-left:{6*k:.2f}px; border-left:{3*k:.2f}px solid #d97b29; color:#1a252f; }}
h3 {{ font-size:{10.5*k:.2f}px; margin:{6*k:.2f}px 0 {2*k:.2f}px; color:#34495e; }}
p  {{ margin:{3*k:.2f}px 0; }}
ul {{ margin:{3*k:.2f}px 0 {3*k:.2f}px {16*k:.2f}px; padding:0; }}
li {{ margin:{1*k:.2f}px 0; }}
.lead {{ background:#fdf6ee; border-left:{4*k:.2f}px solid #d97b29;
        padding:{7*k:.2f}px {9*k:.2f}px; margin:{5*k:.2f}px 0 {7*k:.2f}px; font-weight:600; }}
.quote {{ color:#7f8c8d; font-size:{9*k:.2f}px; margin:{2*k:.2f}px 0 {5*k:.2f}px; }}
table {{ width:100%; border-collapse:collapse; margin:{3*k:.2f}px 0 {6*k:.2f}px; }}
th,td {{ border:1px solid #e2e6ea; padding:{2.5*k:.2f}px {4*k:.2f}px;
        font-size:{9.2*k:.2f}px; vertical-align:top;
        word-break:break-word; overflow-wrap:anywhere; }}
th {{ background:#f6f7f8; text-align:left; font-weight:600; }}
table.two {{ table-layout:fixed; }}
table.two th, table.two td {{ width:50%; }}
table.four {{ table-layout:fixed; }}
table.four th:nth-child(1), table.four td:nth-child(1) {{ width:26%; }}
table.four th:nth-child(4), table.four td:nth-child(4) {{ width:26%; }}
table.idx {{ table-layout:fixed; }}
table.idx th:first-child, table.idx td:first-child {{ width:6%; }}
tr:nth-child(even) td {{ background:#fbfcfc; }}
footer {{ margin-top:{7*k:.2f}px; font-size:{8*k:.2f}px; color:#95a5a6;
         border-top:1px solid #eee; padding-top:{3*k:.2f}px; }}
strong {{ color:#1a252f; }}
code {{ background:#f4f4f4; padding:0 {2*k:.2f}px; border-radius:2px; font-size:{9*k:.2f}px; }}
"""


def inline(t: str) -> str:
    t = html.escape(t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"`(.+?)`", r"<code>\1</code>", t)
    return t


def convert(md: str, k: float = 1.0) -> str:
    out, lines, i = [], md.split("\n"), 0
    while i < len(lines):
        s = lines[i].strip()

        # 表格
        if s.startswith("|") and i + 1 < len(lines) and re.match(
            r"^\s*\|[\s:|-]+\|\s*$", lines[i + 1]
        ):
            header = [c.strip() for c in s.strip("|").split("|")]
            cls = "two" if len(header) == 2 else ("four" if len(header) == 4 else "")
            if header and header[0].strip() in ("#", "序号"):
                cls = (cls + " idx").strip()
            out.append(f'<table class="{cls}"><thead><tr>')
            out.extend(f"<th>{inline(c)}</th>" for c in header)
            out.append("</tr></thead><tbody>")
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                out.append("<tr>")
                out.extend(f"<td>{inline(c)}</td>" for c in cells)
                out.append("</tr>")
                i += 1
            out.append("</tbody></table>")
            continue

        # 引用块（> [!important] 当重点块）
        if s.startswith(">"):
            buf = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                buf.append(lines[i].strip().lstrip(">").strip())
                i += 1
            text = " ".join(x for x in buf if x)
            text = re.sub(r"^\[!\w+\]\s*", "", text)
            if not text:
                continue
            cls = "lead" if ("[!important]" in " ".join(buf) or len(text) < 160) else "quote"
            out.append(f'<div class="{cls}">{inline(text)}</div>')
            continue

        if s.startswith("# "):
            out.append(f"<h1>{inline(s[2:])}</h1>")
        elif s.startswith("## "):
            out.append(f"<h2>{inline(s[3:])}</h2>")
        elif s.startswith("### "):
            out.append(f"<h3>{inline(s[4:])}</h3>")
        elif s.startswith("- "):
            items = []
            while i < len(lines) and lines[i].strip().startswith("- "):
                items.append(lines[i].strip()[2:])
                i += 1
            out.append("<ul>" + "".join(f"<li>{inline(x)}</li>" for x in items) + "</ul>")
            continue
        elif s == "---":
            pass
        elif s:
            out.append(f"<p>{inline(s)}</p>")
        i += 1

    body = "\n".join(out)
    return (
        f'<!doctype html><html lang="zh"><meta charset="utf-8">'
        f"<style>{build_css(k)}</style><body>{body}</body></html>"
    )


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    src = sys.argv[1]
    dst = sys.argv[2] if len(sys.argv) > 2 else os.path.splitext(src)[0] + ".pdf"
    md = open(src, encoding="utf-8").read()

    tmpdir = tempfile.mkdtemp(prefix="jr-pdf-")
    html_out = os.path.splitext(src)[0] + ".html"

    if not os.path.exists(CHROME):
        open(html_out, "w", encoding="utf-8").write(convert(md))
        print(f"⚠️  没找到 Chrome（{CHROME}），只生成了 HTML：{html_out}")
        return 0

    def pages_of(path: str) -> int:
        try:
            info = subprocess.run(["pdfinfo", path], capture_output=True,
                                  text=True, check=True)
            for ln in info.stdout.splitlines():
                if ln.startswith("Pages:"):
                    return int(ln.split(":")[1].strip())
        except (FileNotFoundError, subprocess.CalledProcessError):
            pass
        return 1

    last_k, page_count = 1.0, 99
    for k in (1.0, 0.96, 0.92, 0.88, 0.84, 0.80):
        page = convert(md, k)
        html_path = os.path.join(tmpdir, "方案.html")
        open(html_path, "w", encoding="utf-8").write(page)
        subprocess.run(
            [
                CHROME, "--headless=new", "--disable-gpu", "--no-sandbox",
                "--no-pdf-header-footer",
                f"--user-data-dir={os.path.join(tmpdir, 'profile')}",
                f"--print-to-pdf={dst}", f"file://{html_path}",
            ],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        last_k, page_count = k, pages_of(dst)
        if page_count == 1:
            break

    open(html_out, "w", encoding="utf-8").write(convert(md, last_k))

    size = os.path.getsize(dst) if os.path.exists(dst) else 0
    flag = "✅" if page_count == 1 else "⚠️"
    print(f"{flag} {dst}  ({size} bytes)  k={last_k}")
    print(f"   Pages: {page_count}" + ("  ← 还是多页，需要删内容" if page_count > 1 else ""))
    print("   HTML: " + html_out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
