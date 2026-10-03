# 验证记录（2026-10-02）

- 后端：9 项自动测试覆盖范围/非有限数值、自动保存、启停恢复实际原 H、拒绝覆盖其他配置、回读失败、版本拒绝与辅助程序的私有可执行副本、关机保留配置和正常停止清理。
- 前端 TypeScript 与生产打包通过；CSS 以内联方式加载，适配 Framely 的离屏插件页面。
- 实际 CEF 离屏渲染测试通过：三个滑块、启用开关、中性黑白/暖色预设的桥接保存和展开使用说明（模拟后端）。
- 新模块：ARM64 模拟上传/返回与四线程 4×10000 次测试、1000 组数学变换和当前 compositor 哈希接受/指令上下文变异测试通过。
- 当前 Frame 只读复制的 compositor SHA256 为 d75d3a…123b3。40 字节上传上下文移到 0x166d48，调用点 0x166d6c；vtable=0x5a7b10，slot120 对应 0x2a1af8。黑白标记仍为 node+839，uniform 起始仍为 node+192；上传正常分支在 0x2a1b68 同步 memcpy。新增适配限定完整哈希，无自动地址扫描/猜测。
- 新 hue_control 在当前 Frame 通过公共 OpenVR Background 接口读取实际系统 H=0.674033761；读取测试没有写设置、配置 preload 或重启 SteamVR。

- 签名 0.1.0 包已通过 Framely 正式安装 API 安装到 Frame。真实受限后端 status 显示 connected=true、supported=true、enabled=false；readHue 返回 0.674033761，无需网络权限。安装前后 compositor PID 均为 2438，没有重启 SteamVR、启用 preload 或写入系统色调。

头显内的 H/S/V 视觉效果、停用恢复和正常开机恢复仍需实际观察；插件不会自行重启运行时。

## 0.1.1 修复验证

0.1.0 的前端误将完整 settings（包含 enabled、originalHue）存入调节草稿，滑块及中性黑白预设展开草稿后提交额外字段，后端正确拒绝。0.1.1 在状态接收和提交边界只选取 H/S/V，不放宽后端校验。

新的真实 CEF 回归使用包含 enabled/originalHue 的状态和严格参数校验，逐个调节三个滑块，再启用、使用预设、恢复原始效果并再次使用预设。修复版通过；原版在首个色调滑块提交时失败，可复现用户报错。9 项后端测试、TypeScript 和生产构建通过。

设备已在正常启动后加载原生模块：nativeActive=true、matchedMono>6000、restartRequired=false。当前修复仅变更前端，不需要再次重启 SteamVR；实际画面效果仍以头显测试为准。


## 0.1.2 无签名格式与 SDK 更新

- 使用当前 Framely SDK 构建，包含统一键盘、滚动条和悬停反馈；版本元数据、打包命令均已更新。
- 类型检查、9 项后端测试、原生 ABI/调色/模块边界测试与真实 CEF 页面交互测试通过。
- `.framely` 包仅包含 manifest.json 与声明的载荷，逐文件 SHA256 校验通过，不包含公钥或签名。
- 已通过 Framely 0.2.0-523a67b20bbb 安装到 Frame；收藏、启用状态、排序与保存的调色参数保留，安装前后 vrcompositor PID 不变。
