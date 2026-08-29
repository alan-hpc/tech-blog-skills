---
name: codesign-measure
description: >
  Run and report hardware measurements to a contract that survives review: every
  number carries n, median, dispersion, and a resolution limit; every measured
  instruction is verified present in the disassembly; the environment is pinned;
  and known anti-fooling checks are executed before any number is quoted. Covers
  GPU/CPU/accelerator microbenchmarks (CUDA, PTX/SASS, cycle counters).
  Use when the user says "实测", "跑个 benchmark", "测一下延迟/吞吐",
  "这个数字靠谱吗", "补上离散度", "measure", "microbenchmark", or when an
  article contains performance numbers that lack n / dispersion / provenance.
tools: Bash, Read, Write, Edit
user-invokable: true
argument-hint: "[benchmark source or article path]"
---

# 测量契约 · 让每个数字都扛得住复现

**立场**：一个没有 n、没有离散度、没有反自欺核对的性能数字，
**不是「初步结果」，是无效数据**。它不能进文章，也不能进结论。

---

## 1 · 测量契约（每个数字都必须满足）

发布任何一个数字之前，下面 8 项缺一不可：

| # | 字段 | 为什么必须 | 不满足时 |
|---|---|---|---|
| 1 | **n**（独立采样次数） | 单点值无法区分真值与噪声 | 无效，不得引用 |
| 2 | **中位数**（而非均值） | 均值被离群值拖动；kernel 启动偶发抖动很常见 | 必须说明用的是哪个统计量 |
| 3 | **离散度**（min/max 或 p5/p95，及极差占比） | 读者据此判断能信到第几位 | 无效 |
| 4 | **分辨率上限** | 3.0 cycle 的测量，±1 cycle 就是 ±33% | 会导致过度精确的派生比值 |
| 5 | **反自欺核对**（见 §3） | 编译器可能已把被测代码删掉 | 数字可能纯属虚构 |
| 6 | **环境固定**（见 §2） | cycle 数与频率、驱动、独占性相关 | 不可复现 |
| 7 | **计时口径** | cycle 计数器与墙钟时间是两回事 | 跨尺度对比会错 |
| 8 | **源码可得** | 读者要能重跑 | 只能当作传闻 |

### 记录格式

每次测量产出一行 JSON header + 每项一行，落盘存档：

```jsonl
{"run":"s53_v2","date":"YYYY-MM-DD","device":"<型号> <架构> <SM数>","device_index":0,
 "exclusive":true,"all_devices_util_pct":0,"driver":"<版本>","runtime":"<版本>",
 "clock_attr_mhz":2032,"clock_observed_mhz":2025,
 "compile":"<完整编译命令>","timer":"clock64 (cycle, frequency-independent)",
 "trials":31,"rep_per_kernel":256,"stat":"median",
 "sass_check":{"STTM":260,"LDTM":16}}
{"id":"...","op":"...","n":31,"median":3.0,"min":3.0,"max":4.0,"spread_pct":33.3,
 "note":"±1 cycle 分辨率极限，不得宣称精确到 3.0"}
```

`sass_check` 与 `exclusive` 是**最容易被省略、也最致命**的两项。

---

## 2 · 环境固定

测量前后各采一次，写进 header：

```bash
# 设备、时钟、占用、驱动 —— 用你的厂商工具，示例为 NVIDIA
nvidia-smi --query-gpu=index,name,clocks.sm,utilization.gpu,driver_version \
           --format=csv,noheader
```

**必须回答的三个问题：**

1. **机器是独占的吗？** 共享机器上别人的任务会污染 cycle 级测量。
   把**所有**设备的 util 记下来，不只是你用的那块。
2. **时钟是多少？** `clockRate` 属性报的是**上限**，实际运行时钟常常更低。
   两个都记：`clock_attr` 与 `clock_observed`。
3. **计的是 cycle 还是时间？** 用设备内 cycle 计数器（如 `clock64`）时，
   结果**与频率无关**，跨频率可比但不能直接换算成时间；用墙钟则相反。
   **跨尺度对比前必须确认两边口径一致。**

> **不能省的一句话**：如果测量在共享机器上完成，**在文章里写出来**，
> 并说明你做了什么来控制它（换空闲设备复测、交叉验证等）。
> 隐瞒共享状态是诚信问题，不是技术问题。

---

## 3 · 反自欺核对（每次编译后执行）

**核心手段：数汇编里的指令条数，与循环次数对账。**

```bash
# 以 CUDA 为例；其它平台换成对应的反汇编工具
nvcc <你的完整编译参数> -cubin foo.cu -o foo.cubin
cuobjdump -sass foo.cubin | grep -c '<被测指令助记符>'
```

**数的是静态指令条数，不是执行次数。** 期望值：

```
期望条数 = 每轮循环体里该指令的条数 × 编译器展开倍数
```

与 `REP` 无关 —— `REP` 是动态执行次数，展开倍数才决定静态条数。
例：每轮 4 条 load、`#pragma unroll 4` → 期望 16 条。
**对不上，尤其是远小于期望或为 0，这个数字就是假的。**

**必须核对的场景：**

| 场景 | 症状 | 核对方法 |
|---|---|---|
| 常量折叠 | 结果异常地好 | 指令数远小于预期 |
| 死代码消除 | 结果异常地好 | 指令数为 0 |
| 读未初始化的内存 | 读延迟异常地低 | 加载指令数为 0 |
| 隐藏的串行依赖 | **吞吐 ≈ 延迟** | 这本身就是判据，见 §4.2 |

---

## 4 · 已知陷阱目录

这些都是实际踩过、有明确症状与判据的。

### 4.1 跨循环常量折叠 → 假加速

**症状**：某精度测出比另一精度快 7.9×。
**真相**：操作数是编译期常量，`op(A,B,C) = C + K`，整个循环退化成加法链，
汇编里只剩 2 条目标指令。
**修**：每轮迭代用**循环计数器**扰动输入，然后数指令。

### 4.2 修错方向：把输出喂回输入

**症状**：改完之后，测出的吞吐 ≈ 测出的延迟。
**真相**：把累加器异或回操作数，重新造出了串行依赖。
**判据**：**吞吐 ≈ 延迟就是有依赖**，不是「测得准了」。
**修**：用循环计数器扰动，**永远不要用输出扰动**。

### 4.3 读没写过的内存

**症状**：读延迟低得离谱，汇编里加载指令数为 0。
**修**：测读之前先写一遍填满。

### 4.4 一次性资源放进循环 → 设备永久挂死

某些资源申请/释放协议**每个线程块只允许一次**。放进循环会导致
**无报错、无超时的永久挂死**，只能强杀进程。
**规矩**：资源申请一律放在 kernel 开头，**绝不放循环**。

### 4.5 误导性错误码

释放类 API 的错误信息可能把方向说反
（例：报「资源未完全释放」，实际是**多释放了几次**）。
**遇到资源类错误码时，先确认执行该操作的线程数是否符合协议**，
再怀疑是否漏了释放。

### 4.6 编译目标：`-arch` 与 `-gencode`

生成可执行文件时，`-arch=sm_XXXa` 可能额外嵌入**不带架构后缀的 PTX**，
导致架构专属指令在运行期失败。
**用**：`-gencode arch=compute_XXXa,code=sm_XXXa`

### 4.7 静默失效的编译选项

某些资源控制选项在缺少配套属性时会被**静默忽略**（只有警告）。
**核对方法**：改选项前后各反汇编一次，确认汇编真的变了。

### 4.8 功耗/能耗测量的采样陷阱

被测 kernel 太短 → 采样窗口全落在空闲区间 → 采到的是 idle 值。
**修**：把工作量放大到采样周期的数十倍，并从**被测进程之外**采样。

### 4.9 共享机器

其它设备上跑着第三方任务时，cycle 级测量会被污染。
**做法**：挑空闲设备测；**再换一组空闲设备复测做交叉验证**；
两次差异写进文章。

### 4.10 分辨率边缘的数字

当测量值只有个位数 cycle 时，±1 cycle 就是几十个百分点。
**规矩**：报告分辨率上限，并把所有派生比值写成**区间**而非点值。

---

## 5 · 输出到文章的形态

文章里必须有一个「测量口径」表，且**在第一个数字出现之前**：

```markdown
### 测量口径（所有 cycle 数据适用）

| 项 | 值 |
|---|---|
| 机器 | <型号> · <架构> · <SM 数> · 设备 N，测量时全部设备 0% util（独占） |
| 时钟 | 属性报 <A> MHz；测量瞬时 <B> MHz |
| 软件 | 驱动 <x> · runtime <y> |
| 编译 | <完整命令> |
| 计时 | 设备内 cycle 计数器，**与频率无关** |
| 采样 | 每项 n = <N> 次独立启动，报中位数；kernel 内再对 REP 次取均值 |
| 防自欺 | 编译后核对汇编条数：<助记符>=<数> ... |

| 项 | 中位数 | min | max | 极差 |
|---|---:|---:|---:|---:|
| ... | | | | |
```

**离散度异常的项要单独解释**，不能只列数字。

---

## 6 · 与其它技能的关系

- 上游 [`codesign-sources`](../codesign-sources/SKILL.md)：厂商给的标称值作为对照基线，
  但**标称值不是测量值**，证据等级不同。
- 下游 [`codesign-article`](../codesign-article/SKILL.md)：测量口径表进文章第三段。
- 评审 [`codesign-review`](../codesign-review/SKILL.md)：D2 维度逐条检查本契约。
