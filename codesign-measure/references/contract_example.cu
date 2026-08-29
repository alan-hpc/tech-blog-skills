// contract_example.cu —— 测量契约的最小可运行范例
//
// 演示契约的 8 项里，代码能负责的 6 项：
//   n / 中位数 / 离散度 / 分辨率提示 / 环境固定 / 计时口径
// 另外 2 项（反自欺核对、源码可得）见文末注释与 README。
//
// 编译（注意用 -gencode，不是 -arch，理由见 SKILL.md §4.6）：
//   nvcc -gencode arch=compute_XXXa,code=sm_XXXa -O3 contract_example.cu -o ce
// 反自欺核对（必做）：
//   nvcc -gencode arch=compute_XXXa,code=sm_XXXa -O3 -cubin contract_example.cu -o ce.cubin
//   cuobjdump -sass ce.cubin | grep -c '<被测指令助记符>'
//
//   ★ 数的是「静态指令条数」，不是执行次数。期望值 =
//        每轮循环体里该指令的条数 × 编译器的展开倍数
//   本例：每轮 4 条 load × #pragma unroll 4 = 16 条（与 REP=256 无关）。
//   实测确为 16。对不上 —— 尤其是远小于期望或为 0 —— 说明被优化掉了，数字无效。

#include <cstdio>
#include <cstdint>
#include <vector>
#include <algorithm>

#define CK(x) do{ cudaError_t e=(x); if(e){ \
    printf("ERR %d %s\n",__LINE__,cudaGetErrorString(e)); exit(1);} }while(0)

#define REP    256   // kernel 内重复次数：摊薄计时开销
#define TRIALS 31    // 独立采样次数：奇数便于取中位数

// ---------------------------------------------------------------------------
// 被测 kernel。
// ★ 关键：每轮用循环计数器 i 扰动输入，防止跨循环常量折叠（SKILL.md §4.1）。
//   绝不要用累加器扰动输入 —— 那会造出串行依赖（§4.2），
//   症状是「吞吐 ≈ 延迟」。
// ---------------------------------------------------------------------------
__global__ void k_measure(uint64_t* out, uint32_t seed)
{
    __shared__ uint32_t buf[1024];
    for (int i = threadIdx.x; i < 1024; i += blockDim.x) buf[i] = i ^ seed;
    __syncthreads();

    uint32_t a = seed, b = seed + 1, c = seed + 2, d = seed + 3;

    uint64_t t0 = clock64();          // 设备内 cycle 计数器：与 SM 频率无关
    #pragma unroll 4
    for (int i = 0; i < REP; ++i) {
        // 用 i 扰动索引，编译器无法把整个循环折叠成常量
        a += buf[(a + i) & 1023];
        b += buf[(b + i) & 1023];
        c += buf[(c + i) & 1023];
        d += buf[(d + i) & 1023];
    }
    uint64_t t1 = clock64();

    if (threadIdx.x == 0) {
        out[0] = (t1 - t0) / REP;     // 每次操作的平均 cycle
        out[1] = a + b + c + d;       // 消费结果，防止死代码消除
    }
}

// ---------------------------------------------------------------------------
// 统计：报中位数 + min/max + 极差占比。
// ★ 报中位数而非均值：kernel 启动偶发抖动会拖动均值。
// ---------------------------------------------------------------------------
static void report(const char* op, const char* detail, std::vector<double> v)
{
    std::sort(v.begin(), v.end());
    double med = v[v.size()/2], lo = v.front(), hi = v.back();
    double spread = med > 0 ? 100.0 * (hi - lo) / med : 0.0;
    printf("%s,%s,%zu,%.1f,%.1f,%.1f,%.1f", op, detail, v.size(), med, lo, hi, spread);
    // 分辨率提示：个位数 cycle 时 ±1 cycle 就是几十个百分点
    if (med < 10.0)
        printf("   <- 分辨率边缘：±1 cycle = ±%.0f%%，派生比值须写成区间", 100.0/med);
    printf("\n");
}

int main()
{
    CK(cudaSetDevice(0));

    // --- 环境固定：直接打进输出，避免事后回忆不起来 ---
    cudaDeviceProp pr; CK(cudaGetDeviceProperties(&pr, 0));
    int clk = 0;  cudaDeviceGetAttribute(&clk, cudaDevAttrClockRate, 0);
    int rt = 0, drv = 0; cudaRuntimeGetVersion(&rt); cudaDriverGetVersion(&drv);
    printf("# device=%s sm_%d%d SMs=%d clockRate=%.0fMHz(上限) "
           "cudart=%d driverAPI=%d REP=%d TRIALS=%d timer=clock64(cycle)\n",
           pr.name, pr.major, pr.minor, pr.multiProcessorCount,
           clk/1000.0, rt, drv, REP, TRIALS);
    printf("# 还需人工记录：实际 clocks.sm、所有设备的 util（独占性）、驱动版本\n");
    printf("op,detail,n,median,min,max,spread_pct\n");

    uint64_t* d = nullptr; CK(cudaMalloc(&d, 64));
    std::vector<double> v;
    for (int r = 0; r < TRIALS; ++r) {
        uint64_t h = 0;
        k_measure<<<1, 128>>>(d, (uint32_t)r);   // 每次换 seed，避免缓存态相同
        CK(cudaDeviceSynchronize());
        CK(cudaMemcpy(&h, d, sizeof h, cudaMemcpyDeviceToHost));
        v.push_back((double)h);
    }
    report("shared_load", "4x per iter", v);

    CK(cudaFree(d));
    return 0;
}
