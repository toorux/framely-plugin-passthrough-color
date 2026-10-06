# 透视调色

**本插件由 AI 编写。**

切换 Steam Frame **关闭、彩色与黑白透视**，调节彩色画面的亮度、饱和度和冷暖，以及黑白画面的染色色调、染色饱和度和亮度增益，提供 React 快捷页面、滑块、预设、自动保存与一键恢复。不会让黑白摄像头产生真实彩色图像。

使用 Framely 0.4 SDK，插件清单的 apiVersion 为 1。后端声明 `runAs: steamos`，访问当前 Steam 会话的设置和用户 systemd 配置；无需 root，不请求网络、窗口或通知权限。`autostart: true` 用于恢复已保存的调色参数。

## 如何调整

1. 安装 `.framely` 包，在“已安装”打开“透视调色”，可收藏到“常用”。
2. 顶部按钮读取系统实际透视模式，并约每 2.5 秒同步外部切换。关闭透视时不显示调节项；彩色相机不可用时禁用彩色按钮。黑白和彩色参数分别保存。打开对应模式的 **启用调色 / 启用彩色调节**。插件保存启用前的系统色调，添加自己的用户级启动配置，不自动重启 SteamVR。
3. **首次启用**需要在下一次 SteamVR 启动后加载原生模块。可以稍后正常重启设备；这次启动之前色调可调整，饱和度和亮度尚不生效。出现“调色模块已启用”后再检查透视画面。
4. 拖动滑块，约 250ms 合并保存；原生 S/V 读取周期约 250ms，以后调整无需再次重启。

| 参数 | 界面范围 | 含义 |
|---|---|---|
| 色调 | 0–360° | 系统 `camera.monochromeTintHue`，选择染色颜色 |
| 染色饱和度 | 0–100% | 0% 中性黑白；100% 保留系统染色强度 |
| 亮度 | 25–150% | 100% 保持原增益；高值可能使亮部细节裁剪 |

彩色模式提供亮度 25–150%、饱和度 0–200%、冷暖 −100–100；默认分别为 100%、100%、0。冷暖通过 RGB 增益调整白平衡，不是经过标定的 Kelvin 色温。更新前已加载的模块需要在下一次 SteamVR 启动后换为新版，插件不会自动重启运行时。

“中性黑白”设为 S=0、V=1；此时色调不再产生染色。“柔和暖色 / 冷色”使用 30% 染色饱和度。“恢复原始效果”恢复首次启用前的 H 及 S=1、V=1；没有捕获原 H 时使用系统文档默认 0.67。

**停用调色**会恢复原 H、S/V 原输出，并移除插件自己的启动配置。当前进程里的模块保持中性旁路，在 SteamVR 正常关闭后卸载。卸载插件前建议先停用。插件正常停止也会恢复原输出并移除配置；系统正在关机时保留已启用配置，以便下一次开机加载，然后由常驻后端恢复参数。

## 存储与兼容

- 参数：Framely 为 steamos 身份提供的 `FRAMELY_DATA_DIR/settings.json`。
- 实时控制/状态：`/run/user/<uid>/framely-passthrough-color/`，权限 0700。
- 启动配置：`~/.config/systemd/user/steamvr.service.d/80-framely-passthrough-color.conf`。
- 模块副本：`~/.local/share/framely/passthrough-color/libframely_passthrough_color.so`。

不修改 SteamVR 的磁盘二进制、shader 或其他插件的 preload。模式按钮仅切换实际可见状态和相机源，保留其余相机配置。已有其他 compositor preload 时拒绝覆盖；不匹配的运行时保持原输出。H 与 S/V 使用不同链路，不保证同一帧应用。

当前原生模块限定 ARM64 compositor 完整 SHA256：

- `ab33d32b15f55d356d6c4509b635fac6dca9614e6485226e75b62aaaa3aa639e`：原 demo 验证版本。
- `d75d3a0d3a86f8750e8f77fd43575605465c8fa2bef973a7597c4a1c8cb123b3`：当前 Frame，新增适配已离线核对；新模块的端到端画面效果需要实机首次加载确认。

模块启动时再次校验完整哈希、40 字节调用上下文与 renderer vtable，分别匹配黑白与彩色路径。彩色饱和度仅对两个完整 SHA256 匹配的 RGB fragment shader 在内存中追加运算，不修改磁盘 shader；未匹配时禁用饱和度。在上传线程之外读取 JSON；上传时只修改五组 RGB，保持 alpha 和其他字节。数学实现见 [原生模块说明](native/README.md)，测试与设备验证见 [验证记录](VALIDATION.md)。

## 构建、打包、安装

Linux ARM64、C/C++ 编译器、Python 3、Node.js。OpenVR 头文件、ARM64 加载库与许可在 vendor/openvr；SDK 在 vendor/framely-sdk。

```bash
npm ci
npm run build
npm run typecheck
npm test
bash native/test.sh
# 可选：使用真实 CEF 测试参数提交与交互
FRAMELY_CEF_ROOT=/path/to/cef bash tests/cef-smoke.sh
# 可选：测试匹配的只读 compositor 副本
FRAME_TEST_COMPOSITOR=/path/to/vrcompositor bash native/test.sh
npm run pack
framely verify dist/tooru.passthrough-color-0.1.4.framely
framely install dist/tooru.passthrough-color-0.1.4.framely --approve
```

下载地址按仓库、插件 ID 和版本自动生成，打包时写入包内 manifest；数据库通过 submodule 固定源码提交，自动读取清单并将下载包 SHA256 与 Release 附件哈希比对，不需要密钥或签名。

图标只使用清单中的 `icon` 配置，仓库和包内均包含同一路径的 PNG。数据库自动生成固定提交的商店图片地址，并校验仓库图片与包内图标一致。

## 发布

推送与 `manifest.json` 版本一致的标签，Actions 自动构建 ARM64 插件、校验并发布 GitHub Release，随后将该版本的固定源码提交登记到 `DATABASE_REPOSITORY` 指定的数据库仓库。正式版更新 `main`，预发布版（如 `0.1.4-preview.1`）更新 `testing`。向上游原仓库的 PR 手动提交。

```bash
git tag v0.1.4
git push origin v0.1.4
```

发布新版本只需更新版本号，不需要填写或修改下载地址。插件版本以 `manifest.json` 为准；`package.json` 和 `package-lock.json` 的 npm 版本可按需同步。已发布版本不覆盖附件。

首次使用数据库登记流程，在本仓库 Settings → Secrets and variables → Actions 配置：

- Variables：添加 `DATABASE_REPOSITORY`，值为目标仓库的 `owner/repository`，例如 `toorux/framely-plugin-database`。
- Secrets：添加 `DATABASE_TOKEN`，使用仅授予上述目标仓库 **Contents: Read and write** 权限的 fine-grained token。

向上游提交 PR 时使用仓库所有者账号或经验证有写权限的维护者账号。插件 ID 使用 `tooru.passthrough-color`，对应 submodule 路径为 `plugins/tooru.passthrough-color`；同一前缀必须属于同一个 GitHub 所有者，每个所有者最多占用五个前缀。上游会在自动合并前下载包并校验 Release SHA256、清单与载荷，同时验证仓库归属。提交上游 PR 时若存在冲突，再手动同步上游并解决。

已有 Release 可在 Actions → Register plugin in database → Run workflow 中填写标签单独登记，无需重新发布附件。

插件包在 [Releases](https://github.com/toorux/framely-plugin-passthrough-color/releases) 下载，附件包含 `.framely` 与 `SHA256SUMS`。

## 故障处理

- “需下次 SteamVR 启动”：已配置，但新进程尚未加载模块。不要把值保存成功当作画面生效。
- “此版本尚未适配”：等待适配，不修改哈希或关闭保护强行启用。
- “已有其他 preload”：停用冲突工具后再启用，不合并未知模块。
- 失去会话连接：插件不拉起 SteamVR，等原生会话恢复后再操作。
- 原生模块 active 但 matchedMono 为 0：打开黑白透视后再观察计数与视觉效果。

紧急恢复只处理自己的配置：将运行控制设回 S=1、V=1（或在 UI 停用），移除上述插件 drop-in，执行 `systemctl --user daemon-reload`，在方便时正常重启 SteamVR/设备。已记录的原 H 在插件数据 `originalHue` 中，可用 `hue_control --set <originalHue>` 恢复。避免关闭或删除其他原生 Steam 配置。

## 生命周期

0.1.3 需要 Framely 0.3。声明正常启动/停止及独立异常清理、卸载清理；钩子使用插件原本的用户身份，默认最多重试 3 次。异常清理不启动或重启 SteamVR，保留用户设置。

当前版本需要 Framely 0.4。SDK 已同步依赖状态查询；本插件没有其他必需插件依赖。
