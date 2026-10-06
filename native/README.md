# 原生调色模块

`hue_control.cpp` 通过公共 OpenVR 设置接口读取和修改 `camera.monochromeTintHue`。`frame_sv_module.c` 与 ARM64 入口只对匹配调用上下文、上传函数结构和 renderer vtable 的黑白上传路径生效。

`frame_sv_uniform.c` 复制 528 字节 uniform，只修改偏移 304、464、480、496、512 处的五组 RGB，保留 alpha 与其他字节。每组颜色使用：

```text
y = 0.3r + 0.5g + 0.2b
c' = V × (y + S × (c − y))
```

S 表示现有归一化染色的强度；S=0 产生等值 RGB，V 表示亮度增益。独立读取线程约每 250ms 读取插件的控制 JSON，上传路径只读取原子缓存。无效控制文件回退到 S=1、V=1；RGB、默认值及不匹配路径保持原输出。

构建通过 `npm run build`，离线回归通过 `bash native/test.sh`。测试覆盖数学变换、ABI、并发、控制文件与运行时版本保护，不连接或重启 SteamVR。设备验证记录见 ../VALIDATION.md。

## 彩色与模式切换

彩色 uniform 使用独立控制文件与单个 64 位原子快照。亮度和冷暖只改变五组 tint RGB，保留画面透明度。正冷暖值衰减蓝色，负值衰减红色；绿通道随偏移轻微衰减，默认严格中性。

彩色逐像素饱和度在 Vulkan shader 创建时加入线性 RGB 运算 `grey*(1-S)+RGB*S`，亮度权重为 0.2126、0.7152、0.0722。在原 shader gamma 解码后、tint 相乘前执行。已核对的 shader 样本 SHA256 如下，仅作验证记录；实际按规范化后的 SPIR-V 结构识别：

- 普通 RGB fragment：`07d34d631e4609d4289c402c1fe9d37bbc662f7201bad098d3ad0918c4c9bc97`
- 锐化 RGB fragment：`5ef0a90f1cd68f692e426dcb26369dae44dc1b96b71ca633247cc95b0e97e06f`
- 核对的普通 vertex：`69baab1403c153fcdf06a87ae05a25a6678c9bc1dbeebfa3b295145182ac09f3`
- 核对的锐化 vertex：`5a22b4540c45361f7a88302158094c010fc216645a5997517623cbca64b57bdc`

原 RGB fragment 不使用 member25[0].w（字节 476），两套 vertex 不读取 member25，该槽位传递 S。只有匹配 shader 成功创建后才发布饱和度就绪状态；未知 shader 原样传递。离线测试可指定 `FRAME_COLOR_SHADER_DIR` 和 `SPIRV_VAL`，使用设备只读副本验证两种输出、无关元数据与 ID 重编号兼容、实际指令修改拒绝、Vulkan 查询包装和创建失败旁路，不在仓库保存 Valve shader。

模式辅助程序调用 `IVRCameraPassthroughInternal_001`，辅助程序检查 slots7–10 所指方法的指令结构与可执行内存边界，保留寄存器、字段偏移和局部分支的校验，忽略外部调用目标地址，不再要求固定 vrclient 哈希或方法地址。读取真实可见状态与来源；写入保留其余四个配置字段并回读，失败恢复原配置及可见状态。彩色相机由只读设备查询确认。

2026-10-06：设备 `--mode-get` 经 SSH 回读 `off`、`colorAvailable:true`。新彩色 shader 已通过离线 SPIR-V 校验；新模块尚未在真实 compositor 中加载，GPU 画面效果仍需后续验证。

## 更新兼容性

后端与原生构造器共用 `frame_compat.c` 的有界 ARM64 ELF 探测。要求唯一的 40 字节上传上下文、附近的黑白标志字段访问、唯一的上传函数结构，以及该函数对应的 vtable 相对重定位。通过后动态解析 context/site/upload/vtable 地址，构造器在实际内存再次验证调用点和 vtable；无关文件字节、build ID 和代码地址移动不会禁用模块。真正的布局变化或多义匹配仍拒绝该渲染功能。

相机模式、公共 OpenVR 黑白色相、原生 RGB 增益和 shader 饱和度分别检测。模式失败不影响色相设置；原生结构失败不影响模式与色相。shader 比较排除编译器标记、调试元数据和 ID 编号，保持实际指令、布局、绑定与常量比较；不匹配只关闭彩色饱和度。该策略兼容结构保持一致的更新，不宣称任意 ABI 改动都可自动适配。
