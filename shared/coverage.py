#!/usr/bin/env python3
"""改写不丢信息 —— 逐项比对旧版与新版。

重排文章结构时最容易发生的事故是「搬着搬着漏了一段」，而且**看不出来**：
新版读着通顺、字数还更多，但某张表、某个数字、某条出处不见了。

本工具把两版都拆成可比对的事实项，报出「旧版有、新版没有」的部分。

用法:
    python3 coverage.py old.md new.md
    python3 coverage.py old.md new.md --json      # 机器可读
    python3 coverage.py old.md new.md --allow 允许丢失.txt

退出码 0 = 无丢失，1 = 有丢失项。
"""
import argparse
import io
import json
import re
import sys
from collections import Counter

# ── 提取器：每个返回 {事实项: 出现次数} ────────────────────────────


def numbers(s):
    """带单位的数字 —— 最不能丢的一类。"""
    pat = (r"(\d+(?:\.\d+)?)\s*"
           r"(cycle|cycles|ns|us|µs|ms|s\b|B/clk|GB/s|TB/s|TFLOPS|FLOPS|"
           r"KB|MB|GB|W\b|MHz|GHz|bit|byte|列|行|次|倍|×|%)")
    return Counter(f"{m[0]}{m[1]}" for m in re.findall(pat, s))


def citations(s):
    """说明书正文引用：公开申请用段落号 [00xx]，授权专利用列号 col.N。"""
    return Counter(re.findall(r"\[0\d{3}\]", s)
                   + [c.replace(" ", "") for c in re.findall(r"col\.\s?\d+", s)]
                   + re.findall(r"说明书正文", s))


def patents(s):
    """专利号 US2026xxxxxxx / US12699602 等。"""
    return Counter(re.findall(r"US\s?\d{7,11}(?:A1)?", s))


def figures(s):
    """图片嵌入。"""
    return Counter(e.split("|")[0].strip()
                   for e in re.findall(r"!\[\[([^\]]+)\]\]", s))


def wikilinks(s):
    """跨文章链接（不含同文件标题链接）。"""
    out = []
    for l in re.findall(r"(?<!!)\[\[([^\]]+)\]\]", s):
        t = l.split("|")[0].strip()
        if not t.startswith("#"):
            out.append(t.split("#")[0].strip())
    return Counter(out)


def identifiers(s):
    """指令 / 助记符 / API 名 —— 技术文章的骨架。"""
    pat = r"`([A-Za-z_][A-Za-z0-9_.:%<>]{2,})`"
    bad = {"true", "false", "null", "int", "the", "and"}
    return Counter(m for m in re.findall(pat, s) if m.lower() not in bad)


def table_rows(s):
    """表格行的首列 —— 表被整张漏掉时最明显。"""
    out = []
    for ln in s.split("\n"):
        t = ln.strip()
        if t.startswith("|") and t.endswith("|") and not re.match(r"^\|[\s:|-]+\|$", t):
            first = t.strip("|").split("|")[0].strip()
            first = re.sub(r"[*`\[\]]", "", first)
            if first and not re.match(r"^-+$", first):
                out.append(first)
    return Counter(out)


def sources(s):
    """出处措辞：据 XXX / 知乎《》/ arXiv 编号等。"""
    out = re.findall(r"《([^》]{2,40})》", s)
    out += re.findall(r"arXiv\s?[\d.]{6,12}", s)
    out += re.findall(r"据\s*([A-Za-z一-鿿][^，。、\s]{1,20})", s)
    return Counter(out)


EXTRACTORS = {
    "带单位的数字": numbers,
    "专利正文引用": citations,
    "专利号": patents,
    "图片": figures,
    "跨文章链接": wikilinks,
    "指令/标识符": identifiers,
    "表格行": table_rows,
    "出处": sources,
}


def compare(old, new, allow=frozenset(), strict_counts=False):
    """丢失 = 该事实在新版里彻底不存在了（次数归零）。

    次数减少通常是合并重复表述的正常结果，单独记为「变少」而非丢失；
    要连次数一起卡，加 --strict-counts。
    """
    report, lost_total = {}, 0
    for name, fn in EXTRACTORS.items():
        a, b = fn(old), fn(new)
        lost, fewer = [], []
        for k, cnt in a.items():
            if k in allow:
                continue
            if b[k] == 0:
                lost.append((k, cnt, 0))
            elif b[k] < cnt:
                fewer.append((k, cnt, b[k]))
        if strict_counts:
            lost += fewer
            fewer = []
        report[name] = {"旧": len(a), "新": len(b), "丢失": lost, "变少": fewer}
        lost_total += len(lost)
    return report, lost_total


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("old")
    ap.add_argument("new")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--allow", help="每行一项，明示允许丢失的内容")
    ap.add_argument("--max-show", type=int, default=12)
    ap.add_argument("--strict-counts", action="store_true",
                    help="次数减少也算丢失（默认只卡彻底消失）")
    a = ap.parse_args()

    old = io.open(a.old, encoding="utf-8").read()
    new = io.open(a.new, encoding="utf-8").read()
    allow = set()
    if a.allow:
        for ln in io.open(a.allow, encoding="utf-8"):
            ln = ln.split("#")[0].strip()        # 支持行尾注释
            if ln:
                allow.add(ln)

    rep, total = compare(old, new, allow, a.strict_counts)

    if a.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
        return 0 if total == 0 else 1

    print(f"{'[PASS] 无信息丢失' if total == 0 else f'[FAIL] 丢失 {total} 项'}"
          f"　{a.old.split('/')[-1]} → {a.new.split('/')[-1]}")
    print(f"       {len(old):,} → {len(new):,} 字符")
    for name, d in rep.items():
        mark = "✓" if not d["丢失"] else "✗"
        print(f"  {mark} {name:<12} 旧 {d['旧']:>4} → 新 {d['新']:>4}"
              + (f"　丢失 {len(d['丢失'])}" if d["丢失"] else ""))
        for k, was, now in d["丢失"][:a.max_show]:
            note = f"（{was}→{now} 次）" if now else ""
            print(f"        · {k}{note}")
        if len(d["丢失"]) > a.max_show:
            print(f"        … 另有 {len(d['丢失']) - a.max_show} 项")
        if d["变少"]:
            print(f"      （{len(d['变少'])} 项次数变少，多为合并重复表述，未计入丢失）")
    if total:
        print("\n  每一项都要么补回新版，要么写进 --allow 文件并说明为什么可以丢。")
    return 0 if total == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
