# 配置驱动指纹 Mock（阶段 F：权限默认值 + 媒体表面）

接续 `status-010`，本轮处理 `navigator.permissions.query()` 默认状态、`mediaDevices`、`speechSynthesis`、WebRTC 等媒体/权限表面。

## 先测量

| 检测点 | content_shell 默认 | 真实 Chrome 新 profile | 结论 |
|---|---|---|---|
| `permissions.query(geolocation)` | **granted** | prompt | ❌ 预授权地理位置是强信号 |
| `query(notifications)` | **denied** | prompt | ❌ |
| `query(camera/microphone)` | **denied** | prompt | ❌ |
| `query(midi)` | **denied** | granted | ❌ |
| `query(persistent-storage)` | **denied** | prompt | ❌ |
| `query(clipboard-read)` | **denied** | prompt | ❌ |
| `query(push)` | NotSupportedError | NotSupportedError | ✅ 一致（缺 userVisibleOnly）|
| `mediaDevices.enumerateDevices()` | 3 项空标签(audioinput/videoinput/audiooutput) | 授权前同样空标签 | ✅ 与授权前隐私行为一致 |
| `RTCPeerConnection`/`getUserMedia`/`MediaRecorder` | function | function | ✅ |
| `enumerateDevices.toString()` | `[native code]` | `[native code]` | ✅ |
| `speechSynthesis.getVoices().length` | **0** | 桌面通常 >0 | ⚠️ 次要，见残留 |
| `Notification.permission` | **denied** | default | ⚠️ 独立路径，见残留 |

核心问题：content_shell 的权限默认值是"测试默认"（allowlist 里 granted，其余 denied），与真实 Chrome 新 profile（多为 prompt）差异明显。

## 设计

`ShellPermissionManager::GetPermissionStatus()` 运行在 **browser 进程**（可直接读 profile，无沙箱问题），原逻辑：allowlist 内 → GRANTED，否则 → DENIED。

- `content/shell/common/shell_fingerprint_profile.{h,cc}`：解析 `permissions.mode`。
- `content/shell/browser/shell_permission_manager.cc`：新增 `ChromeDefaultPermissionStatus(PermissionType)`，返回真实 Chrome 新 profile 的 query 默认值：
  - **ASK（"prompt"）**：GEOLOCATION(_APPROXIMATE)、NOTIFICATIONS、AUDIO_CAPTURE、VIDEO_CAPTURE、CAMERA_PAN_TILT_ZOOM、MIDI_SYSEX、PERSISTENT_STORAGE、CLIPBOARD_READ_WRITE、IDLE_DETECTION、PROTECTED_MEDIA_IDENTIFIER、STORAGE_ACCESS_GRANT、WINDOW_MANAGEMENT、LOCAL_FONTS、DISPLAY_CAPTURE、VR、AR、HAND_TRACKING …
  - **GRANTED**：MIDI（基础 MIDI）、SENSORS、BACKGROUND_SYNC、CLIPBOARD_SANITIZED_WRITE、PAYMENT_HANDLER。
  - 未覆盖的类型回落原 allowlist 逻辑。
  - 仅当 `profile.permissions_mode()=="chrome_defaults"` 时启用（配置驱动、opt-in）。
- `config/mac_chrome_profile.json`：新增 `"permissions": {"mode": "chrome_defaults"}`。

`push` 保持抛 NotSupportedError（与真实 Chrome 一致）。`mediaDevices` 无需改（授权前空标签本就是 Chrome 隐私行为）。

## 运行验证（profile）

| permission | 改前 | 改后 |
|---|---|---|
| geolocation | granted | **prompt** ✅ |
| notifications | denied | **prompt** ✅ |
| camera | denied | **prompt** ✅ |
| microphone | denied | **prompt** ✅ |
| midi | denied | **granted** ✅ |
| persistent-storage | denied | **prompt** ✅ |
| clipboard-read | denied | **prompt** ✅ |

7 项 query 状态全部对齐真实 Chrome 新 profile。

## 编译

`autoninja -C out/ContentShell content_shell` 成功（仅触及 content/shell browser + common，增量快）。

## 残留 / 后续

- **`Notification.permission` 仍为 "denied"（应为 "default"）**：它不走 `PermissionService`，而是 `NotificationManager::GetPermissionStatus()` → `blink.mojom.NotificationService.GetPermissionStatus()` 的独立 mojo 调用。content_shell 未绑定 platform notification service，mojo 连接返回 false → Blink 侧回落 DENIED（`notification_manager.cc:77-82`）。修复需在 content_shell 接入一个返回 ASK 的通知服务，属较大改动，单列后续。注意：反爬主要读 `permissions.query({name:'notifications'})`（已为 prompt），`Notification.permission` 为次要面。
- **`speechSynthesis.getVoices()` 为空**：真实桌面 Chrome 有系统语音列表，0 是 headless 特征。注入语音列表需 native 提供 TTS voice 列表，中等复杂度，单列后续（阶段 G/H）。
- 阶段 G：WebGL vendor/renderer、Canvas/Audio stable noise。
- `navigator.maxTouchPoints` 接入。

## 累计已 native mock 的检测面

UA / UA-CH / Accept-Language / languages / webdriver / platform / productSub / vendor / hardwareConcurrency / deviceMemory / timezone / plugins / mimeTypes / pdfViewerEnabled / window.chrome / screen 几何 / window 尺寸 / **permissions.query() 默认状态（geolocation/notifications/camera/microphone/midi/persistent-storage/clipboard 等）**。
