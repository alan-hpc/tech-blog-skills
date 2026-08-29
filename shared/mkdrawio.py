#!/usr/bin/env python3
"""一份规格 → 同时产出 .drawio（可编辑源）与 .png（供 Obsidian 嵌入）。

为什么不用 drawio CLI：本机 draw.io 21.5.0 的 Electron 主进程不接受 -x/-f 导出参数
（`bad option: -x`）。所以这里自己把同一份规格渲染成 SVG，再用 rsvg-convert 转 PNG。
两条产物几何一致，.drawio 打开后仍可正常编辑。

用法：python3 mkdrawio.py [figure_id]
"""
import html
import os
import subprocess
import sys

OUT = "/Users/min.yang/Documents/Obsidian Vault/GPU&NPU&TPU 架构解析/diagrams"
FONT = "PingFang SC, Hiragino Sans GB, Noto Sans CJK SC, sans-serif"
MONO = "SF Mono, Menlo, Consolas, monospace"

# 语义配色：浅底 + 深字 + 明确边框，深浅色主题下都能看清
PAL = {
    "box":  ("#ffffff", "#333333", "#111111"),
    "tmem": ("#fde7c9", "#b26b00", "#111111"),   # TMEM 一律橙
    "smem": ("#d9e8fb", "#1f5c9e", "#111111"),   # SMEM 一律蓝
    "core": ("#dbeddb", "#2d6b2d", "#111111"),   # 计算单元一律绿
    "reg":  ("#f0f0f0", "#666666", "#111111"),   # 寄存器/通用存储灰
    "dim":  ("#f7f7f7", "#cccccc", "#999999"),   # 灰掉的（不参与）
    "hot":  ("#fbe0dd", "#c0392b", "#111111"),   # 强调/危险
    "grp":  ("none",    "#aaaaaa", "#777777"),   # 分组虚线框
}
EDGE = {
    "":     ("#333333", 1.4, None,  "block"),
    "bi":   ("#b26b00", 2.0, None,  "both"),
    "hot":  ("#c0392b", 2.0, None,  "block"),
    "dash": ("#666666", 1.4, "6,4", "block"),
    "none": ("#aaaaaa", 1.2, "4,4", "none"),
}


# ────────────────────────────── .drawio ──────────────────────────────
def drawio_xml(nodes, edges, w, h):
    cells = []
    for nid, label, kind, x, y, ww, hh in nodes:
        fill, stroke, fc = PAL[kind]
        dash = ";dashed=1" if kind in ("dim", "grp") else ""
        va = ";verticalAlign=top;align=left;spacingLeft=8;spacingTop=4" if kind == "grp" else ""
        sty = (f"rounded=0;whiteSpace=wrap;html=1;fillColor={fill};"
               f"strokeColor={stroke};fontColor={fc};fontSize=13{dash}{va}")
        cells.append(
            f'<mxCell id="{nid}" value="{html.escape(label).replace(chr(10),"&lt;br&gt;")}" '
            f'style="{sty}" vertex="1" parent="1">'
            f'<mxGeometry x="{x}" y="{y}" width="{ww}" height="{hh}" as="geometry"/></mxCell>')
    for i, e in enumerate(edges):
        src, dst, label, kind = (list(e) + ["", ""])[:4]
        col, sw, dash, arrow = EDGE[kind]
        sty = (f"endArrow={'none' if arrow=='none' else 'block'};html=1;rounded=0;"
               f"strokeColor={col};strokeWidth={sw};fontSize=11;fontColor={col}"
               + (";dashed=1" if dash else "")
               + (";startArrow=block" if arrow == "both" else ""))
        cells.append(
            f'<mxCell id="e{i}" value="{html.escape(label)}" style="{sty}" '
            f'edge="1" parent="1" source="{src}" target="{dst}">'
            f'<mxGeometry relative="1" as="geometry"/></mxCell>')
    return ('<mxfile host="claude" type="device"><diagram id="d" name="Page-1">'
            f'<mxGraphModel dx="{w}" dy="{h}" grid="0" page="1" pageWidth="{w}" '
            f'pageHeight="{h}" background="#ffffff" math="0" shadow="0"><root>'
            f'<mxCell id="0"/><mxCell id="1" parent="0"/>{"".join(cells)}'
            '</root></mxGraphModel></diagram></mxfile>')


# ─────────────────────────────── SVG ────────────────────────────────
def anchor(a, b):
    """两个矩形之间的连线端点：取最接近的一对边中点。"""
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    acx, acy, bcx, bcy = ax + aw / 2, ay + ah / 2, bx + bw / 2, by + bh / 2
    dx, dy = bcx - acx, bcy - acy
    if abs(dx) * ah > abs(dy) * aw:                      # 水平为主
        p1 = (ax + aw, acy) if dx > 0 else (ax, acy)
        p2 = (bx, bcy) if dx > 0 else (bx + bw, bcy)
    else:                                                # 垂直为主
        p1 = (acx, ay + ah) if dy > 0 else (acx, ay)
        p2 = (bcx, by) if dy > 0 else (bcx, by + bh)
    return p1, p2


def svg_doc(nodes, edges, w, h):
    geo = {n[0]: (n[3], n[4], n[5], n[6]) for n in nodes}
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
         f'viewBox="0 0 {w} {h}">',
         '<defs>']
    for k, (col, sw, dash, arrow) in EDGE.items():
        o.append(f'<marker id="ar{k or "d"}" viewBox="0 0 10 10" refX="9" refY="5" '
                 f'markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
                 f'<path d="M0,0 L10,5 L0,10 z" fill="{col}"/></marker>')
    o.append('</defs>')
    o.append(f'<rect width="{w}" height="{h}" fill="#ffffff"/>')

    # 先画分组框（在底层）
    for n in nodes:
        if n[2] == "grp":
            _, label, _, x, y, ww, hh = n
            fill, stroke, fc = PAL["grp"]
            o.append(f'<rect x="{x}" y="{y}" width="{ww}" height="{hh}" fill="none" '
                     f'stroke="{stroke}" stroke-width="1.2" stroke-dasharray="6,4"/>')
            o.append(f'<text x="{x+9}" y="{y+18}" font-family="{FONT}" font-size="12" '
                     f'fill="{fc}">{html.escape(label)}</text>')

    # 连线（只画线；标签留到最后画，避免被方块盖住、也避免白底遮线）
    labels = []
    for e in edges:
        src, dst, label, kind = (list(e) + ["", ""])[:4]
        col, sw, dash, arrow = EDGE[kind]
        (x1, y1), (x2, y2) = anchor(geo[src], geo[dst])
        da = f' stroke-dasharray="{dash}"' if dash else ""
        me = "" if arrow == "none" else f' marker-end="url(#ar{kind or "d"})"'
        ms = f' marker-start="url(#ar{kind or "d"})"' if arrow == "both" else ""
        o.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{col}" '
                 f'stroke-width="{sw}"{da}{me}{ms}/>')
        if label:
            horiz = abs(x2 - x1) >= abs(y2 - y1)
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            # 标签让开连线本身：横线放线上方，竖线放线右侧
            if horiz:
                my -= 13
            else:
                mx += sum(6.5 if ord(c) > 0x2000 else 3.5 for c in label) + 12
            labels.append((mx, my, label, col))

    # 方块
    for nid, label, kind, x, y, ww, hh in nodes:
        if kind == "grp":
            continue
        fill, stroke, fc = PAL[kind]
        da = ' stroke-dasharray="5,4"' if kind == "dim" else ""
        o.append(f'<rect x="{x}" y="{y}" width="{ww}" height="{hh}" fill="{fill}" '
                 f'stroke="{stroke}" stroke-width="1.4"{da}/>')
        lines = label.split("\n")
        fs = 13 if len(lines) <= 2 else 12
        lh = fs + 4
        y0 = y + hh / 2 - (len(lines) - 1) * lh / 2 + fs * 0.36
        for i, ln in enumerate(lines):
            mono = ln.startswith("`") and ln.endswith("`")
            txt = ln.strip("`")
            o.append(f'<text x="{x+ww/2}" y="{y0+i*lh}" '
                     f'font-family="{MONO if mono else FONT}" font-size="{fs}" '
                     f'fill="{fc}" text-anchor="middle">{html.escape(txt)}</text>')

    # 连线标签最后画 —— 保证在方块之上，不会被覆盖或截断
    for mx, my, label, col in labels:
        tw = sum(13 if ord(c) > 0x2000 else 7 for c in label) + 10
        o.append(f'<rect x="{mx-tw/2}" y="{my-11}" width="{tw}" height="17" rx="3" '
                 f'fill="#ffffff" stroke="{col}" stroke-width="0.6" opacity="0.95"/>')
        o.append(f'<text x="{mx}" y="{my+2}" font-family="{FONT}" font-size="11.5" '
                 f'fill="{col}" text-anchor="middle">{html.escape(label)}</text>')
    o.append('</svg>')
    return "\n".join(o)


def emit(fid, spec):
    os.makedirs(OUT, exist_ok=True)
    nodes, edges, w, h = spec["nodes"], spec["edges"], spec["w"], spec["h"]
    src = os.path.join(OUT, fid + ".drawio")
    svg = os.path.join(OUT, fid + ".svg")
    png = os.path.join(OUT, fid + ".png")
    open(src, "w", encoding="utf-8").write(drawio_xml(nodes, edges, w, h))
    open(svg, "w", encoding="utf-8").write(svg_doc(nodes, edges, w, h))
    r = subprocess.run(["rsvg-convert", "-z", "2", "-b", "white", "-o", png, svg],
                       capture_output=True, text=True)
    os.remove(svg)                                # SVG 只是中间产物
    ok = os.path.exists(png) and os.path.getsize(png) > 0
    print(f"  {'✓' if ok else '✗'} {fid:<38} {os.path.getsize(png) if ok else 0:>8} B"
          + ("" if ok else "  " + (r.stderr or "")[:120]))
    return ok


if __name__ == "__main__":
    from figs import FIGS
    only = sys.argv[1] if len(sys.argv) > 1 else None
    n = sum(emit(k, v) for k, v in FIGS.items() if not only or k == only)
    print(f"生成 {n} 张（每张同时留有 .drawio 源文件）")
