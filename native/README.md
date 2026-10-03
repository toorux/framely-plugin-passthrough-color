# 原生调色模块

`hue_control.cpp` 通过公共 OpenVR 设置接口读取和修改 `camera.monochromeTintHue`。`frame_sv_module.c` 与 ARM64 入口只对匹配完整 compositor 哈希、调用上下文和 renderer vtable 的黑白上传路径生效。

`frame_sv_uniform.c` 复制 528 字节 uniform，只修改偏移 304、464、480、496、512 处的五组 RGB，保留 alpha 与其他字节。每组颜色使用：

```text
y = 0.3r + 0.5g + 0.2b
c' = V × (y + S × (c − y))
```

S 表示现有归一化染色的强度；S=0 产生等值 RGB，V 表示亮度增益。独立读取线程约每 250ms 读取插件的控制 JSON，上传路径只读取原子缓存。无效控制文件回退到 S=1、V=1；RGB、默认值及不匹配路径保持原输出。

构建通过 `npm run build`，离线回归通过 `bash native/test.sh`。测试覆盖数学变换、ABI、并发、控制文件与运行时版本保护，不连接或重启 SteamVR。设备验证记录见 ../VALIDATION.md。
