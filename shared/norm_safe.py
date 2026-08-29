#!/usr/bin/env python3
"""术语归一化 —— 代码块与 wiki 链接安全版。

背景（血的教训）：一次 `re.sub(r" {2,}", " ", s)` 全文替换，
把 24 个代码块里 12 个的 ASCII 对齐图毁掉了，且无 git、无备份。
第二版加了代码块保护，又把 `[[13 · 功耗 供电与散热]]` 归一成
`功耗供电与散热`，链接全断。

所以这个脚本做两件事：
  1. ``` 代码块内的内容原样保留（对齐、空格、制表一律不动）
  2. [[wiki-link]] 与 ![[embed]] 先抽出占位，处理完再放回

用法:
    python3 norm_safe.py article.md            # 预览 diff，不写盘
    python3 norm_safe.py article.md --write    # 写盘（会先备份 .bak）

术语表在 TERMS 里改。
"""
import io
import os
import re
import shutil
import sys

# (正则, 替换) —— 只在代码块外、wiki 链接外生效
TERMS = [
    (r"\bTensor\s+Memory\b", "Tensor Memory"),
    (r"\btensor\s+core\b", "tensor core"),
    (r"\bshared\s+memory\b", "shared memory"),
    (r"\bwarp\s*group\b", "warpgroup"),
    # 中英文之间补一个空格（常见排版要求），但不动代码块
    (r"([一-鿿])([A-Za-z0-9])", r"\1 \2"),
    (r"([A-Za-z0-9])([一-鿿])", r"\1 \2"),
]

SENTINEL = "\x00WL{}\x00"


def norm(text, terms=TERMS):
    # --- 1) 抽出 wiki 链接与图片嵌入
    keep = []

    def stash(m):
        keep.append(m.group(0))
        return SENTINEL.format(len(keep) - 1)

    text = re.sub(r"!?\[\[[^\]]*\]\]", stash, text)

    # --- 2) 按 ``` 切段，只处理代码块之外
    parts = re.split(r"(```)", text)
    out, in_block = [], False
    for seg in parts:
        if seg == "```":
            in_block = not in_block
            out.append(seg)
            continue
        if in_block:
            out.append(seg)            # 原样保留
            continue
        for pat, rep in terms:
            seg = re.sub(pat, rep, seg)
        out.append(seg)
    res = "".join(out)

    # --- 3) 放回
    return re.sub(r"\x00WL(\d+)\x00", lambda m: keep[int(m.group(1))], res)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    path = sys.argv[1]
    write = "--write" in sys.argv
    src = io.open(path, encoding="utf-8").read()
    dst = norm(src)

    if src == dst:
        print("无变化")
        return 0

    # 安全检查：代码块数量与总行数不应改变
    if src.count("```") != dst.count("```"):
        print("*** 拒绝写入：代码块围栏数量变了 ***")
        return 1
    if src.count("[[") != dst.count("[["):
        print("*** 拒绝写入：wiki 链接数量变了 ***")
        return 1

    import difflib
    diff = list(difflib.unified_diff(src.split("\n"), dst.split("\n"),
                                     "before", "after", lineterm="", n=1))
    print("\n".join(diff[:120]))
    print(f"\n... 共 {len([d for d in diff if d.startswith('+') and not d.startswith('+++')])} 行变更")

    if write:
        shutil.copy(path, path + ".bak")
        io.open(path, "w", encoding="utf-8").write(dst)
        print(f"已写入，备份在 {os.path.basename(path)}.bak")
    else:
        print("（预览模式，未写盘。加 --write 才写）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
