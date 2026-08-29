#!/usr/bin/env python3
"""从 Google Patents 抓专利说明书正文，存成纯文本。

为什么需要它：
  1. 语料里有 11/183 份 PDF 是**截断的下载**（无 %%EOF、无 xref），根本打不开；
  2. 即使 PDF 完好，NVIDIA 的公开专利常常是**扫描图像版**，`pdftotext` 输出 0 行，
     只能逐页读图，代价极高。
  Google Patents 的 HTML 里有全文，是**文本**，两个问题一次解决。

用法:
    python3 fetch_patent_text.py US12499052                 # 单篇
    python3 fetch_patent_text.py --check-corpus <dir>       # 体检：找出损坏的 PDF
    python3 fetch_patent_text.py --repair <dir>             # 给损坏的 PDF 补正文

产物：与 PDF 同目录的 <专利号>.txt，首行是来源与抓取日期。
"""
import argparse
import glob
import html
import io
import os
import re
import subprocess
import sys
import time

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"


def pdf_broken(path):
    """截断的下载：没有 %%EOF 或没有 xref 表。"""
    try:
        d = open(path, "rb").read()
    except OSError:
        return "读不了"
    if not d.startswith(b"%PDF"):
        return "非 PDF 头"
    why = []
    if b"%%EOF" not in d[-4096:]:
        why.append("无 EOF(截断)")
    if d.count(b"xref") == 0:
        why.append("无 xref")
    return ",".join(why)


def patent_no(path):
    """从文件名取专利号：US12499052__Title.pdf -> US12499052"""
    m = re.match(r"(US\d+[AB]?\d*)", os.path.basename(path))
    return m.group(1) if m else None


def fetch(no, tries=3):
    """抓正文。公开申请用 A1，授权专利用 B2；两个都试。"""
    for suffix in ("B2", "A1", "B1", ""):
        url = f"https://patents.google.com/patent/{no}{suffix}/en"
        for _ in range(tries):
            r = subprocess.run(["curl", "-sL", "--max-time", "45", "-A", UA, url],
                               capture_output=True)
            h = r.stdout.decode("utf-8", "replace")
            if len(h) < 20000:
                time.sleep(2)
                continue
            m = re.search(r'<section[^>]*itemprop="description".*?</section>', h, re.S)
            if not m:
                break                      # 页面在，但没有正文 → 换后缀
            t = re.sub(r"<(script|style).*?</\1>", " ", m.group(0), flags=re.S)
            t = html.unescape(re.sub(r"<[^>]+>", "\n", t))
            lines = [l.strip() for l in t.split("\n") if l.strip()]
            if len(lines) > 50:
                return url, "\n".join(lines)
        time.sleep(1)
    return None, None


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("patents", nargs="*")
    ap.add_argument("--check-corpus", metavar="DIR")
    ap.add_argument("--repair", metavar="DIR")
    a = ap.parse_args()

    if a.check_corpus or a.repair:
        root = a.check_corpus or a.repair
        pdfs = sorted(glob.glob(os.path.join(root, "*", "*.pdf")))
        bad = [(p, pdf_broken(p)) for p in pdfs]
        bad = [(p, w) for p, w in bad if w]
        print(f"体检：完好 {len(pdfs)-len(bad)} / 损坏 {len(bad)} / 共 {len(pdfs)}")
        for p, w in bad:
            print(f"  ✗ {w:22s} {os.path.relpath(p, root)}")
        if not a.repair:
            return 0 if not bad else 1
        print("\n开始补正文……")
        okn = 0
        for p, _ in bad:
            no = patent_no(p)
            if not no:
                print(f"  ? 认不出专利号：{os.path.basename(p)}")
                continue
            out = os.path.join(os.path.dirname(p), no + ".txt")
            if os.path.exists(out):
                print(f"  · 已有 {no}.txt，跳过")
                okn += 1
                continue
            url, txt = fetch(no)
            if not txt:
                print(f"  ✗ {no} 抓取失败")
                continue
            io.open(out, "w", encoding="utf-8").write(
                f"# 来源：{url}\n# 抓取日期：{time.strftime('%Y-%m-%d')}\n"
                f"# 原因：同目录 PDF 是截断的下载，无法打开\n\n{txt}\n")
            print(f"  ✓ {no}  {len(txt):>7,} 字符  → {os.path.basename(out)}")
            okn += 1
            time.sleep(1.5)
        print(f"\n补齐 {okn}/{len(bad)}")
        return 0

    for no in a.patents:
        url, txt = fetch(no)
        if txt:
            io.open(no + ".txt", "w", encoding="utf-8").write(
                f"# 来源：{url}\n# 抓取日期：{time.strftime('%Y-%m-%d')}\n\n{txt}\n")
            print(f"✓ {no}  {len(txt):,} 字符")
        else:
            print(f"✗ {no} 抓取失败")
    return 0


if __name__ == "__main__":
    sys.exit(main())
