# 原生调色模块

`hue_control.cpp` 通过公共 OpenVR 设置接口读取和修改 `camera.monochromeTintHue`。`frame_sv_module.c` 与 ARM64 入口只对匹配完整 compositor 哈希、调用上下文和 renderer vtable 的黑白上传路径生效。

`frame_sv_uniform.c` 复制 528 字节 uniform，只修改偏移 304、464、480、496、512 处的五组 RGB，保留 alpha 与其他字节。每组颜色使用：

```text
y = 0.3r + 0.5g + 0.2b
c' = V × (y + S × (c − y))
```

S 表示现有归一化染色的强度；S=0 产生等值 RGB，V 表示亮度增益。独立读取线程约每 250ms 读取插件的控制 JSON，上传路径只读取原子缓存。无效控制文件回退到 S=1、V=1；RGB、默认值及不匹配路径保持原输出。

构建通过 `npm run build`，离线回归通过 `bash native/test.sh`。测试覆盖数学变换、ABI、并发、控制文件与运行时版本保护，不连接或重启 SteamVR。设备验证记录见 ../VALIDATION.md。

## 彩色与模式切换

彩色 uniform 使用独立控制文件与单个 64 位原子快照。亮度和冷暖只改变五组 tint RGB，保留画面透明度。正冷暖值衰减蓝色，负值衰减红色；绿通道随偏移轻微衰减，默认严格中性。

彩色逐像素饱和度在 Vulkan shader 创建时加入线性 RGB 运算 `grey*(1-S)+RGB*S`，亮度权重为 0.2126、0.7152、0.0722。在原 shader gamma 解码后、tint 相乘前执行。仅接受以下 SHA256：

- 普通 RGB fragment：`07d34d631e4609d4289c402c1fe9d37bbc662f7201bad098d3ad0918c4c9bc97`
- 锐化 RGB fragment：`5ef0a90f1cd68f692e426dcb26369dae44dc1b96b71ca633247cc95b0e97e06f`
- 核对的普通 vertex：`69baab1403c153fcdf06a87ae05a25a6678c9bc1dbeebfa3b295145182ac09f3`
- 核对的锐化 vertex：`5a22b4540c45361f7a88302158094c010fc216645a5997517623cbca64b57bdc`

原 RGB fragment 不使用 member25[0].w（字节 476），两套 vertex 不读取 member25，该槽位传递 S。只有匹配 shader 成功创建后才发布饱和度就绪状态；未知 shader 原样传递。离线测试可指定 `FRAME_COLOR_SHADER_DIR` 和 `SPIRV_VAL`，使用设备只读副本验证两种输出、单字节指纹拒绝、Vulkan 查询包装和创建失败旁路，不在仓库保存 Valve shader。

模式辅助程序调用 `IVRCameraPassthroughInternal_001`，后端先校验 vrclient SHA256 `05bece568cdfad1ecdd052a6f1aa0994ebddb6026db73c38b97eb031ea7e0c36`，辅助程序再次校验 slots7–10 偏移。读取真实可见状态与来源；写入保留其余四个配置字段并回读，失败恢复原配置及可见状态。彩色相机由只读设备查询确认。

2026-10-06：设备 `--mode-get` 经 SSH 回读 `off`、`colorAvailable:true`。新彩色 shader 已通过离线 SPIR-V 校验；新模块尚未在真实 compositor 中加载，GPU 画面效果仍需后续验证。
