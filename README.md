# tech-blog-skills

**面向软硬件协同设计（codesign）技术报告的 Claude Code 技能包。**

目标不是「写得快」，是**写得能被检验**：每一个数字可复现，每一条断言可溯源，
每一处推断被标成推断，每一个未验证的说法被明确列出。
标准对齐博士论文的技术章节，输出形态是技术博客。

---

## 为什么需要单独一套

通用写作技能追求流畅与产出速度。硬件解析类文章的失败模式完全不同：

| 常见失败 | 后果 | 本技能包的对策 |
|---|---|---|
| 编译器把被测代码优化掉了 | 测出「FP8 比 FP16 快 7.9×」这种假加速 | `codesign-measure` 强制 SASS 指令计数核对 |
| 只报单点值，不报离散度 | 读者以为 3.0 cycle 是精确值，实际 ±1 cycle = ±33% | 测量契约要求 n / 中位数 / 极差 / 分辨率上限 |
| 引用二手博客当一手事实 | 错误随转载扩散 | 五级证据分级，等级必须显式标注 |
| 读了权利要求就说「读过专利」 | 漏掉说明书正文里真正的设计动机 | `codesign-sources` 的专利读法协议 |
| 把 N 次观察写成「定律」 | 无法证伪的断言 | `codesign-review` 要求给出证伪条件 |
| 软→硬链条中间断开 | 读者跟不到硬件那一层 | 链条完整性是评审的独立维度 |

---

## 四个技能

```
                 ┌─────────────────────┐
                 │  codesign-sources   │  资料层：博客 / 专利 / 论文 / 规范
                 │  抓取 + 证据分级     │  产出：带等级标注的素材库
                 └──────────┬──────────┘
                            ↓
                 ┌─────────────────────┐
                 │  codesign-measure   │  实测层：测量契约 + 反自欺
                 │  跑数 + 离散度       │  产出：可复现的测量记录
                 └──────────┬──────────┘
                            ↓
                 ┌─────────────────────┐
                 │  codesign-article   │  写作层：九段式骨架
                 │  组织 + 术语纪律     │  产出：文章草稿
                 └──────────┬──────────┘
                            ↓
                 ┌─────────────────────┐
                 │  codesign-review    │  评审层：五席位 + 魔鬼代言人
                 │  证据锚定的发现      │  产出：分级发现 + 修复清单
                 └─────────────────────┘
                            ↓ 未通过则回到对应层
```

| 技能 | 何时用 | 核心产出 |
|---|---|---|
| [`codesign-sources`](codesign-sources/SKILL.md) | 动笔之前 | 素材库 + 每条素材的证据等级 |
| [`codesign-measure`](codesign-measure/SKILL.md) | 有任何性能/行为数字时 | 满足测量契约的记录 |
| [`codesign-article`](codesign-article/SKILL.md) | 组织成文 | 九段式文章 |
| [`codesign-review`](codesign-review/SKILL.md) | 发布之前 | 分级发现清单 |

四个可独立使用。最小可用组合是 `codesign-measure` + `codesign-review`
（给已有文章补测量纪律与评审）。

---

## 安装

```bash
git clone https://github.com/alan-hpc/tech-blog-skills
ln -s "$PWD/tech-blog-skills/codesign-article"  ~/.claude/skills/codesign-article
ln -s "$PWD/tech-blog-skills/codesign-review"   ~/.claude/skills/codesign-review
ln -s "$PWD/tech-blog-skills/codesign-measure"  ~/.claude/skills/codesign-measure
ln -s "$PWD/tech-blog-skills/codesign-sources"  ~/.claude/skills/codesign-sources
```

然后在 Claude Code 里 `/codesign-review 你的文章.md`。

**环境配置**：复制 `shared/env.example.toml` 为 `shared/env.toml`，
填入你自己的远程机器与容器信息。**该文件已在 `.gitignore` 中，不会被提交。**

---

## 质量闸门

```bash
python3 shared/validate.py "你的文章.md"
```

检查代码块配平、链接可达、图片存在、证据等级标注、测量契约字段、
以及「限制与边界」章节是否存在。**这是发布前的硬门槛。**

---

## 设计参照与致谢

架构上参照了 [academic-research-skills](https://github.com/Imbad0202/academic-research-skills)
（作者 Cheng-I Wu，CC BY-NC 4.0）的几个想法：多席位角色分离评审、
固定的魔鬼代言人席位、发现必须带证据锚、以及「方法做了但没披露 = 缺陷」的立场。

**本仓库不包含该项目的任何文本或代码**，全部内容为面向硬件 codesign 场景重新编写。
详见 [ATTRIBUTION.md](ATTRIBUTION.md)。

## 许可

MIT。见 [LICENSE](LICENSE)。
