# v3 变更记录 001：指纹画像 mock 首次落地到源码

对应提交：

```text
commit f7408907311b9b6dcd8e358d1259911471734c8c
Author: JoeYuan <zy.yuan@aftership.com>
Date:   Mon Jul 20 15:04:35 2026 +0800

    feat: e0488508e6-v3: 支持破解点 mock
```

`git log --oneline`：

```text
f740890731 feat: e0488508e6-v3: 支持破解点 mock
e8ca59d734 feat: e0488508e6-v2: 裁剪
5246b97bc4 feat: e0488508e6-v1
e0488508e6 Roll Enterprise Companion chromium_win_x86 ...
```

规模：33 个文件，`+1842 / -3`。这是单次提交，一次性把 `docs/e0488508e6-v2/status-005` ~ `status-016` 里规划/记录的 fingerprint profile mock 基础设施真正写进了 `chromium-workspace/src`（v2 的 `e8ca59d734` 提交本身只做了裁剪，没有包含这批代码）。本文只记录这一次提交实际改了什么。

## 一、核心新增：`ShellFingerprintProfile`

新文件：

```text
content/shell/common/shell_fingerprint_profile.h
content/shell/common/shell_fingerprint_profile.cc
```

进程级单例，通过 `--fingerprint-profile=<path.json>` 加载一份 JSON 画像，懒加载、失败则 `empty()`，所有 getter 在未设置时都退回宿主/content_shell 默认值。加载入口：

```cpp
static const ShellFingerprintProfile& Get();      // 进程内单例，惰性加载
static void SetForTesting(ShellFingerprintProfile);
static std::optional<ShellFingerprintProfile> ParseFromJson(const std::string&);
static std::optional<ShellFingerprintProfile> LoadFromFile(const std::string&);
```

解析的 JSON 字段（与仓库里已有的 `config/mac_chrome_profile.json` 对应，这份文件本身没改，之前一直是"写了但没人读"）：

```text
name
browser.userAgent / browser.userAgentData.{brands,fullVersionList,mobile,platform,platformVersion,architecture,bitness,model,uaFullVersion}
navigator.{languages,platform,productSub,vendor,hardwareConcurrency,deviceMemory,maxTouchPoints,webdriver}
timezone
plugins.mode
chrome_object.mode
permissions.mode
speech.mode
screen.{width,height,availWidth,availHeight,availLeft,availTop,colorDepth}
window.{innerWidth,innerHeight}
webgl.{unmaskedVendor,unmaskedRenderer}（回退到 vendor/renderer）
canvas.{mode,seed} / audio.{mode,seed}（mode 目前只认 "stable_noise"，用 seed 做 base::Hash 生成稳定 token）
network.acceptLanguage（缺省时从 navigator.languages 反推，反之亦然，保证两种表示互相一致）
```

`time.mode` / `network.tls` / `network.http2` 三个字段在 `mac_chrome_profile.json` 里已经存在，但这次没有解析代码，仍是纯占位（`docs/e0488508e6-v2/TODO-akamai-gaps.md` 第 5、8 条提到过）。

## 二、进程间转发机制

Renderer 是沙箱进程，不能直接读画像 JSON 文件，所以 browser 进程解析画像后，通过一批新增的 `fp-*` command-line switch 转发给 renderer 子进程。转发点在：

```text
content/shell/browser/shell_content_browser_client.cc
  ShellContentBrowserClient::AppendExtraCommandLineSwitches()
```

新增的开关集中定义在 `third_party/blink/public/common/switches.h` + `.cc`（部分在 `content/shell/common/shell_switches.h`）：

```text
fingerprint-profile              画像 JSON 路径（browser 进程独占读取）
fp-navigator-platform / fp-navigator-product-sub / fp-navigator-vendor
fp-hardware-concurrency / fp-device-memory / fp-max-touch-points
fp-plugins-mode                  chrome_pdf | empty
fp-navigator-webdriver           true | false
fp-speech-voices-mode            mac_defaults
fp-window-chrome                 chrome（content/shell/common/shell_switches.h 里定义）
fp-screen-width / fp-screen-height / fp-screen-avail-{width,height,left,top} / fp-screen-color-depth
fp-webgl-vendor / fp-webgl-renderer
fp-canvas-noise-token / fp-audio-noise-token   （十进制 uint64，由 seed 经 base::Hash 派生）
fp-api-trace / fp-api-trace-file  诊断用，见第七节
```

## 三、按能力点的具体改动

### User-Agent / Accept-Language / navigator.languages

`shell_content_browser_client.cc`：`GetShellLanguage()`、`GetUserAgent()` 优先读画像；`GetShellUserAgentMetadata()` 在画像声明了 `userAgentData` 时整体替换 Sec-CH-UA brand 列表、platform、architecture、mobile 等字段。`content/shell/browser/shell.cc` 里把画像的 `navigator.languages` 写进 `RendererPreferences.accept_languages`（逗号分隔、不带 q-value）并 `SyncRendererPrefs()`，让 `navigator.languages` 和 Accept-Language 头保持一致但不冲突（q-value 只在网络层加）。

### navigator 标量字段

`third_party/blink/renderer/core/frame/navigator.cc`（`productSub`/`vendor`/`platform`/`webdriver`）、`navigator_concurrent_hardware.cc`（`hardwareConcurrency`）、`navigator_device_memory.cc`（`deviceMemory`）、`events/navigator_events.cc`（`maxTouchPoints`）：每个 getter 先查对应 `fp-*` switch，非空则返回覆盖值，否则走原逻辑。`navigator.webdriver` 之前完全没有覆盖机制，只是隐式依赖 `AutomationControlledEnabled()` 恰好为 `false`，现在跟其它字段一样显式读 `fp-navigator-webdriver`。

### 时区 / 初始窗口尺寸

`content/shell/app/shell_main_delegate.cc::BasicStartupComplete()`：在 ICU 初始化之前把画像 `timezone` 写入 `TZ` 环境变量（影响 `Intl.DateTimeFormat`/`Date`，且是进程级、纯原生，没有 JS patch）；画像声明了 `window.innerWidth/innerHeight` 且命令行没有显式传 `--content-shell-host-window-size` 时，用它拼出该开关的值，直接改宿主窗口尺寸而不是 hook `window.innerWidth` 的 getter。

### navigator.plugins / navigator.mimeTypes / navigator.pdfViewerEnabled

`third_party/blink/renderer/modules/plugins/dom_plugin_array.cc::IsPdfViewerAvailable()`：`fp-plugins-mode=chrome_pdf` 强制返回 `true`（走 Chrome 内置 PDF viewer 那一套固定 plugin/mimetype 集合），`=empty` 强制 `false`，不设置则保留原来读 `PluginData` 的逻辑。

### window.chrome mock

`content/shell/renderer/shell_render_frame_observer.cc::DidClearWindowObject()`：`fp-window-chrome=chrome` 时调用新增的 `InstallWindowChrome()`，用真实 `v8::Function::New` 构造 `chrome.app`（`isInstalled`/`InstallState`/`RunningState`/`getDetails` 等）、`chrome.csi()`、`chrome.loadTimes()`、`chrome.runtime`（`connect`/`sendMessage`/`id=undefined`/`OnInstalledReason`/`PlatformOs`），全部是原生 V8 函数而非 JS 脚本注入，`Function.prototype.toString` 会显示为 `[native code]`。会先检查 `window.chrome` 是否已存在，避免覆盖。**`chrome.webstore` 这次没做**（见第七节）。

### navigator.permissions / Notification.permission

`content/shell/browser/shell_permission_manager.cc` 新增 `ChromeDefaultPermissionStatus()`：`fp-permissions-mode`（画像里是 `permissions.mode`）等于 `chrome_defaults` 时，把 geolocation/notifications/camera/mic 等一批权限的 `query()` 结果从 content_shell 的测试期默认值改成真实 Chrome 新 profile 的默认值（多数是 `prompt`，midi/sensors/background-sync 等是 `granted`）。

配套新增 `content/shell/browser/shell_platform_notification_service.{h,cc}`（`ShellBrowserContext::GetPlatformNotificationService()` 原来固定返回 `nullptr`，导致 `Notification.permission` 之类的查询直接短路成 `DENIED`）——这是个空实现（不真正弹通知），存在的意义只是让权限查询能走到上面的 `chrome_defaults` 分支而不是提前被 `nullptr` 短路掉。

### speechSynthesis.getVoices()

`third_party/blink/renderer/modules/speech/speech_synthesis.{h,cc}`：新增 `MaybeApplyFingerprintMockVoices()`，`fp-speech-voices-mode=mac_defaults` 且真实 voice 列表为空时，塞入 8 个写死的 macOS 系统语音（Samantha/Alex/Fred/Victoria/Karen/Daniel/Moira/Tessa），只做一次。这部分逻辑此前已经在 `docs/e0488508e6-v2/status-016-webdriver-speech-mock.md` 里描述过，这次是同一份代码首次进入 `chromium-workspace/src`。

### screen.* 几何

`third_party/blink/renderer/core/frame/screen.cc::GetRect()`：`width`/`height`/`availWidth/Height/Left/Top`/`colorDepth` 逐个在物理像素换算之前叠加对应 `fp-screen-*` 覆盖值，缺省保留宿主值。

### WebGL 供应商/渲染器

`third_party/blink/renderer/modules/webgl/webgl_rendering_context_base.cc::getParameter()`：`UNMASKED_VENDOR_WEBGL`/`UNMASKED_RENDERER_WEBGL` 两个 case 里，`fp-webgl-vendor`/`fp-webgl-renderer` 非空则返回画像里的字符串（例如 `"Google Inc. (Apple)"` / `"ANGLE (Apple, ANGLE Metal Renderer: Apple M2, ...)"`），否则走原来的 `ContextGL()->GetString(...)`。

### Canvas / WebAudio 稳定噪声

新文件：

```text
third_party/blink/renderer/core/canvas_interventions/fingerprint_stable_noise.{h,cc}
third_party/blink/renderer/modules/webaudio/fingerprint_audio_stable_noise.{h,cc}
```

两者都是"画像给一个 uint64 token（由 `canvas.seed`/`audio.seed` 经 `base::Hash` 派生），token 存在时对像素/采样点做确定性扰动"。挂载点：`html_canvas_element.cc::ToDataURLInternal()`（`toDataURL`/`toBlob` 路径，读回像素、加噪、重新编码）、`base_rendering_context_2d.cc::getImageDataInternal()`（`getImageData`）、`webaudio/offline_audio_context.cc::FireCompletionEvent()`（`OfflineAudioContext` 渲染完成后对 `AudioBuffer` 逐 channel 加极小扰动，`samples[i] += delta * 1e-7f`，且值为 0 的采样点跳过，避免把静音段染出噪声）。同一个 seed → 同一个 token → 同一份噪声，跨次运行可复现；不同宿主机器的真实 canvas/audio 底层差异被这层噪声掩盖掉。

### API 用量诊断埋点（`--fp-api-trace`）

`third_party/blink/common/switches.cc` 新增 `FingerprintApiTraceLog(const char* name)`：`--fp-api-trace` 存在时每次调用打一行 `LOG(INFO) << "[FP_API_TRACE] " name`；同时给了 `--fp-api-trace-file`，存在则以 `fopen(..., "a")` 追加写文件（POSIX `O_APPEND` 短写近似原子，浏览器/渲染器/GPU 多进程可以安全交错写同一个文件）。这次把埋点铺到了几乎所有上面提到的 getter：`navigator.*`、`screen.*`、`window.chrome.*`、WebGL `getParameter`、canvas `toDataURL`/`getImageData`、`speechSynthesis.getVoices`、`navigator.permissions.query`/`Notification.permission`、`navigator.plugins`/`mimeTypes`/`pdfViewerEnabled`、`OfflineAudioContext` 完成事件。纯诊断用途，未设置开关时是一次 `HasSwitch()` 判断，不影响任何返回值。

## 四、涉及文件清单（按目录分组）

```text
content/shell/BUILD.gn                                          注册新增 .cc/.h
content/shell/app/shell_main_delegate.cc                        TZ 环境变量 + 初始窗口尺寸
content/shell/browser/shell.cc                                  navigator.languages -> accept_languages
content/shell/browser/shell_browser_context.{cc,h}              接入 ShellPlatformNotificationService
content/shell/browser/shell_content_browser_client.cc           UA/UA-CH/Accept-Language + fp-* switch 转发
content/shell/browser/shell_permission_manager.cc               chrome_defaults 权限默认值
content/shell/browser/shell_platform_notification_service.{cc,h} 新增（空实现）
content/shell/common/shell_fingerprint_profile.{cc,h}           新增（画像核心）
content/shell/common/shell_switches.h                           fingerprint-profile / fp-window-chrome 开关声明
content/shell/renderer/shell_render_frame_observer.cc           window.chrome 原生 mock

third_party/blink/common/switches.cc                            fp-* 开关定义 + FingerprintApiTraceLog
third_party/blink/public/common/switches.h                      对应声明

third_party/blink/renderer/core/canvas_interventions/build.gni  注册 fingerprint_stable_noise
third_party/blink/renderer/core/canvas_interventions/fingerprint_stable_noise.{cc,h}  新增
third_party/blink/renderer/core/events/navigator_events.cc      maxTouchPoints
third_party/blink/renderer/core/frame/navigator.cc              productSub/vendor/platform/webdriver
third_party/blink/renderer/core/frame/navigator_concurrent_hardware.cc  hardwareConcurrency
third_party/blink/renderer/core/frame/navigator_device_memory.cc       deviceMemory
third_party/blink/renderer/core/frame/screen.cc                 screen.* 几何覆盖
third_party/blink/renderer/core/html/canvas/html_canvas_element.cc     toDataURL 加噪
third_party/blink/renderer/modules/canvas/canvas2d/base_rendering_context_2d.cc  getImageData 加噪
third_party/blink/renderer/modules/plugins/dom_plugin_array.cc  plugins/mimeTypes/pdfViewerEnabled
third_party/blink/renderer/modules/speech/speech_synthesis.{cc,h}      语音列表 mock
third_party/blink/renderer/modules/webaudio/BUILD.gn            注册 fingerprint_audio_stable_noise
third_party/blink/renderer/modules/webaudio/fingerprint_audio_stable_noise.{cc,h}  新增
third_party/blink/renderer/modules/webaudio/offline_audio_context.cc   音频加噪挂载点
third_party/blink/renderer/modules/webgl/webgl_rendering_context_base.cc  UNMASKED_VENDOR/RENDERER
```

## 五、编译与手动验证建议

在 `chromium-workspace/src` 里：

```bash
cd /Users/zy.yuan/Develop/browser-runtime-projects/chromium-workspace/src
autoninja -C out/ContentShell content_shell
```

启动时挂上画像：

```bash
"out/ContentShell/Content Shell.app/Contents/MacOS/Content Shell" \
  --user-data-dir="$(mktemp -d)" \
  --fingerprint-profile="/Users/zy.yuan/Develop/browser-runtime-projects/chromium-minimal-runtime/config/mac_chrome_profile.json" \
  --fp-api-trace \
  --fp-api-trace-file=/tmp/fp_api_trace.log \
  'data:text/html,<html><body>fp-v3-ok</body></html>'
```

页面里手动核对（预期值取自 `mac_chrome_profile.json`）：

```js
navigator.userAgent            // Chrome/137.0.0.0 ...
navigator.platform              // "MacIntel"
navigator.hardwareConcurrency   // 8
navigator.deviceMemory          // 8
navigator.webdriver              // false
navigator.languages              // ["en-US", "en"]
navigator.plugins.length         // > 0（chrome_pdf 模式）
window.chrome.runtime.id         // undefined
window.chrome.csi()              // {startE, onloadT, pageT, tran}
screen.width / screen.availWidth // 1440 / 1440
speechSynthesis.getVoices().length  // 8
navigator.permissions.query({name:'geolocation'}).then(r => r.state)  // "prompt"
document.createElement('canvas').getContext('webgl').getParameter(
  document.createElement('canvas').getContext('webgl')
    .getExtension('WEBGL_debug_renderer_info').UNMASKED_RENDERER_WEBGL)
  // "ANGLE (Apple, ANGLE Metal Renderer: Apple M2, ...)"
```

再看 `/tmp/fp_api_trace.log`，确认每个 `[FP_API_TRACE]` 埋点都在预期时机触发，作为"真 Chrome vs content_shell 行为差异"的对照日志。

## 六、未覆盖 / 已知缺口

沿用 `docs/e0488508e6-v2/TODO-akamai-gaps.md` 里已经记录、这次没有解决的部分（该文档第 4、7 条描述的 speech/webdriver 缺口是这次提交解决的，其余仍然存在）：

- `window.chrome.webstore` 不存在（`InstallWindowChrome()` 仍只有 `app`/`csi`/`loadTimes`/`runtime`）。
- 设备能力开关位（`vibrate`/`getBattery`/`DeviceMotionEvent`/`DeviceOrientationEvent` 等）没有对应 `fp-*` 开关。
- 行为事件轨迹（鼠标/键盘/触摸事件计数）完全空白，纯零交互场景下可能是明显信号。
- 时间锚定：`time.mode`/`virtualize_delays` 字段在画像 JSON 里存在但没有解析代码，只做了 timezone。
- `network.tls`/`network.http2`（JA3/JA4、HTTP2 帧顺序等传输层指纹）完全未实现。
- `devicePixelRatio` 仍跟随宿主机器，没有覆盖机制。
- 多画像池 / 随机选择（`plan-runtime-profile-mock.md` 里设计的 `profile_selection`/`profile_pool`）没有代码支持，只能跑单一固定画像。
- `config/runtime.yaml` 仍不生效，唯一真实入口是 `--fingerprint-profile=<json>`。
- 这批改动仍然直接改在 `chromium-workspace/src` 里，没有导出成 `patches/` 下的独立 patch 文件。
- `navigator.webdriver` 覆盖只是一个全局布尔值，没有对齐 CDP Automation domain 的其它副作用。
- `speechSynthesis` 语音列表是写死的 8 个 macOS 语音，不会随画像里声明的操作系统/语言环境切换（Windows 画像也会拿到这份 macOS 列表）。
