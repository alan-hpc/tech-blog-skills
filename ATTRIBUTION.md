# 设计参照

## academic-research-skills

架构上参照了 [academic-research-skills](https://github.com/Imbad0202/academic-research-skills)
（作者 Cheng-I Wu，授权 CC BY-NC 4.0）。参照的是**结构性想法**，具体为：

| 想法 | 在本仓库的对应 |
|---|---|
| 多技能 pipeline + 共享参考资料目录 | 四个 skill + `shared/` |
| 多席位角色分离评审 | `codesign-review` 的五席位 |
| 固定的魔鬼代言人席位，其 CRITICAL 必须被显式裁决 | `codesign-review` §2 席位 5 |
| 发现必须带证据锚，禁止泛泛而谈 | `codesign-review` §3 |
| 判定词固定为 满足/部分满足/不满足/未评估 | `codesign-review` §1 |
| benchmark 报告必须含样本量与非空 caveats | `codesign-measure` §1 测量契约 |
| 「方法做了但没披露」本身就是缺陷 | `codesign-measure` §1、`codesign-review` D2 |
| 引用要能支撑它所附着的那条断言 | `codesign-sources` §1 证据分级 |

**本仓库不包含 academic-research-skills 的任何文本、代码或数据文件。**
全部内容针对硬件 codesign 场景重新编写，领域、示例、判据、失败模式均不同：
前者面向学术论文投稿与同行评审，本仓库面向硬件微基准测试与技术博客。

如果你的场景是写学术论文，应该直接用 academic-research-skills，而不是这个仓库。

## 其它

`codesign-measure` §4 的陷阱目录、`codesign-sources` §3 的专利读法，
来自实际项目中踩过的坑，无外部来源。
