#!/usr/bin/env python3
"""质量闸门 —— codesign 技术报告的机械检查。

机器能查的它全查；机器查不了的（论证是否成立、解释是否正确）交给
codesign-review 的五席位评审。

用法:
    python3 validate.py article.md
    python3 validate.py *.md
    python3 validate.py --strict article.md    # 结构检查也算失败

退出码 0 = 全过，1 = 有失败项。
"""
import argparse
import io
import os
import re
import sys
import unicodedata

# 图片查找目录（按顺序尝试）
FIG_DIRS = ["diagrams", "figures", "images", "assets", "."]

# 九段式骨架
STAGES = [
    (r"^##\s*一、\s*结论", "一、结论与定义"),
    (r"^##\s*二、\s*背景", "二、背景与问题"),
    (r"^##\s*三、\s*核心原理", "三、核心原理"),
    (r"^##\s*四、\s*实现细节", "四、实现细节"),
    (r"^##\s*五、\s*完整代码", "五、完整代码展示"),
    (r"^##\s*六、\s*底层代码", "六、底层代码展示"),
    (r"^##\s*七、\s*底层原理", "七、底层原理"),
    (r"^##\s*八、\s*实际测试", "八、实际测试数据"),
    (r"^##\s*九、\s*限制", "九、限制与总结"),
]

# 测量契约关键词（有数字就该有这些）
CONTRACT_HINTS = ["中位数", "median", "离散", "极差", "spread", "n =", "n=", "样本"]

# 证据分级措辞
GRADE_HINTS = ["实测", "据检索摘要", "推断", "据原文", "据 ", "标称"]


def find_fig(name, base):
    for d in FIG_DIRS:
        if os.path.exists(os.path.join(base, d, name)):
            return True
    return os.path.exists(os.path.join(base, name))


def check(path, strict=False):
    fails, warns = [], []
    base = os.path.dirname(os.path.abspath(path))
    s = io.open(path, encoding="utf-8").read()

    # --- 硬失败项 ---

    # 1. 代码块配平 —— 不配平后面整篇渲染错乱
    n_fence = s.count("```")
    if n_fence % 2:
        fails.append(f"代码块围栏不配平：{n_fence} 个 ``` （必须偶数）")

    # 2. wiki 链接目标存在
    #    注意：[[#标题]] 是同文件内的标题链接（Obsidian 语法），不指向别的文件，跳过。
    raw = re.findall(r"(?<!!)\[\[([^\]]+)\]\]", s)
    heads = set(re.findall(r"^#{1,6}\s+(.+?)\s*$", s, re.M))
    links, bad_head = [], []
    for l in raw:
        tgt = l.split("|")[0].strip()
        if tgt.startswith("#"):                      # 同文件标题链接
            h = tgt[1:].strip()
            if h and h not in heads:
                bad_head.append(h)
            continue
        links.append(tgt.split("#")[0].strip())
    broken = sorted({l for l in links if l and
                     not os.path.exists(os.path.join(base, l + ".md"))})
    if bad_head:
        fails.append("指向不存在的标题：" + ", ".join(sorted(set(bad_head))))
    if broken:
        fails.append("坏的 wiki 链接：" + ", ".join(broken))

    # 3. 图片存在
    embeds = [e.split("|")[0].strip() for e in re.findall(r"!\[\[([^\]]+)\]\]", s)]
    embeds += [m for m in re.findall(r"!\[[^\]]*\]\(([^)]+)\)", s)
               if not m.startswith(("http://", "https://", "data:"))]
    miss = sorted({e for e in embeds if not find_fig(e, base)})
    if miss:
        fails.append("缺失的图片：" + ", ".join(miss))

    # 4. 混入西里尔/希腊字母（生成中文时偶发，肉眼极难发现）
    stray = sorted({c for c in s if ord(c) > 0x400
                    and unicodedata.name(c, "").startswith(("CYRILLIC", "GREEK"))})
    if stray:
        fails.append("混入非中日韩字母：" + " ".join(stray))

    # 5. 有数字但没有测量契约的痕迹
    has_perf = re.search(r"\d+(\.\d+)?\s*(cycle|ns|us|µs|ms|GB/s|TB/s|TFLOPS|×|x\b)", s)
    if has_perf and not any(h in s for h in CONTRACT_HINTS):
        fails.append("出现性能数字，但全文没有 n / 中位数 / 离散度 —— 违反测量契约")

    # 6. 代码块里的超宽行 / ASCII 画图
    #    等宽对齐只在终端成立；Obsidian/网页会软换行，把框图折成一堆断线。
    lines = s.split("\n")
    inb, lang, start = False, "", 0
    wide, ascii_art = [], []
    # 真正的框图必然有「竖向连接符」；只有横线与拐角的多半是给代码加的下划线标注，
    # 例如  desc[UR10][R6.64]
    #            └─UR─┘ └─R─┘        ← 这不是框图，不该报
    BOX = set("│├┤┬┴┼┃╱╲╳▲▼")
    for i, ln in enumerate(lines, 1):
        if ln.startswith("```"):
            if not inb:
                inb, lang, start = True, (ln[3:].strip() or "(none)"), i
                blk = []
            else:
                inb = False
                w = max((sum(2 if ord(c) > 0x2000 else 1 for c in x) for x in blk),
                        default=0)
                boxy = sum(1 for x in blk if sum(1 for c in x if c in BOX) >= 3)
                # 普通代码 78–90 列只告警（PTX/编译命令本身就长）；
                # 超过 90 列几乎必然软换行，算失败。
                if w > 78:
                    wide.append((start, lang, w))
                if boxy >= 2:
                    ascii_art.append((start, lang, boxy))
            continue
        if inb:
            blk.append(ln)
    if ascii_art:
        (fails if strict else warns).append(
            "代码块里有 ASCII 画图（应改用 draw.io）：" +
            ", ".join(f"行{a}[{b}]{c}行框线" for a, b, c in ascii_art))
    hard = [x for x in wide if x[2] > 90]
    soft = [x for x in wide if x[2] <= 90]
    if hard:
        fails.append("代码块超过 90 显示列（必然软换行）：" +
                     ", ".join(f"行{a}[{b}]{c}列" for a, b, c in hard))
    if soft:
        warns.append("代码块 78–90 显示列（窄栏下可能换行）：" +
                     ", ".join(f"行{a}[{b}]{c}列" for a, b, c in soft))

    # --- 结构与纪律（strict 下算失败，否则告警） ---

    missing_stages = [name for pat, name in STAGES if not re.search(pat, s, re.M)]
    if missing_stages:
        (fails if strict else warns).append(
            "缺少九段式章节：" + "、".join(missing_stages))

    if not re.search(r"^###?\s*9\.[24]|没验证|未验证|什么会推翻|证伪", s, re.M):
        (fails if strict else warns).append(
            "找不到「没验证什么」或「什么会推翻结论」——§9 不完整")

    if not any(h in s for h in GRADE_HINTS):
        (fails if strict else warns).append(
            "全文没有证据分级措辞（实测 / 据 X / 推断 / 据检索摘要）")

    # 说明书正文引用：公开申请（A1）用段落号 [00xx]，授权专利（B2）用列号 col.N。
    # 文章提到专利却一条正文引用都没有 —— 多半只读了权利要求和附图。
    mentions_patent = re.search(r"\bUS\s?\d{7,11}|专利", s)
    # 三种引用形式：
    #   [00xx]        公开申请（A1）的段落号
    #   col.N         授权专利（B2）的列号
    #   说明书正文     从 Google Patents 全文读到的（HTML 里没有段落号与列号）
    cites = (set(re.findall(r"\[0\d{3}\]", s))
             | set(re.findall(r"col\.\s?\d+", s))
             | set(re.findall(r"说明书正文", s)))
    if mentions_patent and not cites:
        (fails if strict else warns).append(
            "提到专利但没有任何说明书正文引用（[00xx] 或 col.N）—— 很可能只读了权利要求与附图")

    # 「定律」这类不可证伪的措辞
    for word in ["定律", "必然", "一定是", "毫无疑问"]:
        if word in s:
            warns.append(f"出现不可证伪的措辞「{word}」——确认是否该降级为观察")

    ok = not fails
    print(f"[{'PASS' if ok else 'FAIL'}] {path}")
    print(f"       {os.path.getsize(path):,} 字节 | 围栏 {n_fence} | "
          f"链接 {len(set(links))} | 图 {len(set(embeds))} | "
          f"缺章节 {len(missing_stages)}")
    for f in fails:
        print(f"       ✗ {f}")
    for w in warns:
        print(f"       ! {w}")
    return ok


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+")
    ap.add_argument("--strict", action="store_true",
                    help="结构与纪律问题也算失败")
    a = ap.parse_args()
    return 0 if all([check(f, a.strict) for f in a.files]) else 1


if __name__ == "__main__":
    sys.exit(main())
