# 源码级 API 调用埋点（`--fp-api-trace`）

接续 `status-014` 和 `docs/e0488508e6-v2/TODO-akamai-gaps.md` 第三节的 royalmail 实测——为了搞清楚 `x-rmg-recaptcha` 这类加密 sensor payload 到底摸了浏览器哪些能力，且不依赖一份可能对不上号的通用 Akamai 清单，本轮在 `chromium-workspace/src`（未纳入版本控制，故单独记录本文档，方便后续对照原版 Chromium 源码 diff）里加了一个诊断专用的开关：**`--fp-api-trace`**。

## 设计

- 新增命令行开关 `--fp-api-trace`（布尔，无需值）。缺省完全不生效，只做一次 `HasSwitch()` 检查，零开销。
- 命中时，每个被埋点的 getter/方法在被调用时打一行 `LOG(INFO) << "[FP_API_TRACE] <name>"`。这条日志走 Chromium 现有的日志通道（`CHROME_LOG_FILE`/终端），**子进程也能看到**（前面调试 fingerprint profile 加载失败日志时已经验证过子进程日志会透传到同一个输出）。
- 可选新增开关 `--fp-api-trace-file=<path>`：带上后每条 trace 行**额外**追加写入这个文件（append 模式），不影响 `LOG(INFO)` 那份输出，两者同时生效。用来把整次加载的 trace 收敛到一个干净文件里，不用从掺杂大量其它 Chromium 日志噪音的终端/主日志里 grep。多进程（browser/renderer/GPU）并发追加写同一个文件时，靠 POSIX `O_APPEND` 语义保证短行不会互相截断，行与行之间可能交错但每行本身完整。只对没被强 sandbox 限制文件写入的进程生效——如果某个 renderer 进程的沙箱不允许直接 `fopen()`，这个文件写入会静默失败（`LOG(INFO)` 那份仍然正常输出，不受影响）。
- 不碰任何 JS 可见的对象/描述符——纯 C++ 层打点，`Function.prototype.toString`、`Object.getOwnPropertyDescriptor` 等反射探测结果和没打点时完全一样，不会被页面脚本感知到。
- browser 进程自己启动时若命令行带这两个开关，会通过 `AppendExtraCommandLineSwitches`（`kForwardSwitches` 列表）自动转发给所有子进程（renderer/GPU/utility），不需要手动为每个子进程单独指定。
- 所有埋点位置（宏 `FP_API_TRACE(name)`、canvas/audio 的独立函数、window.chrome、permission manager）现在都收敛到同一个共享实现 `blink::switches::FingerprintApiTraceLog(const char* name)`（定义在 `switches.cc`），不再各自重复一份 `HasSwitch()` + `LOG(INFO)` 逻辑——之前是 11 处各自复制这段逻辑，现在只有这一处真正做 `HasSwitch`/文件写入判断，各调用点的宏/函数体缩成一行转发调用。

## 改动清单（全部是对已有文件的修改，没有新增源文件，因此**不需要改任何 BUILD.gn**）

### 开关定义 + 共享实现

- `third_party/blink/public/common/switches.h`：新增声明 `kFingerprintApiTrace`、`kFingerprintApiTraceFile`、共享函数 `FingerprintApiTraceLog(const char*)`。
- `third_party/blink/common/switches.cc`：定义 `kFingerprintApiTrace[] = "fp-api-trace"`、`kFingerprintApiTraceFile[] = "fp-api-trace-file"`，以及 `FingerprintApiTraceLog()` 的实现——先 `HasSwitch(kFingerprintApiTrace)` 判断（未命中直接返回），命中后 `LOG(INFO)`，再看 `kFingerprintApiTraceFile` 是否有值，有则 `fopen(path, "a")` 追加一行并 `fclose`。
- `content/shell/browser/shell_content_browser_client.cc`：`AppendExtraCommandLineSwitches()` 的 `kForwardSwitches` 数组里加了 `blink::switches::kFingerprintApiTrace` 和 `blink::switches::kFingerprintApiTraceFile`，让这两个开关跟其它已经透传的 switch（如 `kFingerprintProfile`）一样自动转发给子进程。

### 埋点位置（按 Akamai 检测点清单的类别分组）

| 检测点类别 | 文件 | 函数 | trace 名称 |
|---|---|---|---|
| 一/三 webdriver | `third_party/blink/renderer/core/frame/navigator.cc` | `Navigator::webdriver()` | `navigator.webdriver` |
| 三 高熵字段 | 同上 | `Navigator::platform()` / `productSub()` / `vendor()` | `navigator.platform` / `navigator.productSub` / `navigator.vendor` |
| 三 高熵字段 | `third_party/blink/renderer/core/frame/navigator_concurrent_hardware.cc` | `NavigatorConcurrentHardware::hardwareConcurrency()` | `navigator.hardwareConcurrency` |
| 三 高熵字段 | `third_party/blink/renderer/core/frame/navigator_device_memory.cc` | `NavigatorDeviceMemory::deviceMemory()` | `navigator.deviceMemory` |
| 三 plugins/mimeTypes | `third_party/blink/renderer/modules/plugins/dom_plugin_array.cc` | `DOMPluginArray::IsPdfViewerAvailable()` | `navigator.plugins/mimeTypes/pdfViewerEnabled` |
| 四 屏幕几何 | `third_party/blink/renderer/core/frame/screen.cc` | `height()` / `width()` / `colorDepth()` / `availLeft()` / `availTop()` / `availHeight()` / `availWidth()` | `screen.*` |
| 八 媒体/GPU | `third_party/blink/renderer/modules/webgl/webgl_rendering_context_base.cc` | `getParameter()` 的 `kUnmaskedRendererWebgl` / `kUnmaskedVendorWebgl` 分支 | `WebGLRenderingContext.getParameter(UNMASKED_*)` |
| 八 媒体（语音） | `third_party/blink/renderer/modules/speech/speech_synthesis.cc` | `SpeechSynthesis::getVoices()` | `speechSynthesis.getVoices` |
| 二 window.chrome | `content/shell/renderer/shell_render_frame_observer.cc` | `ChromeCsi()` / `ChromeLoadTimes()` / `ChromeNoop()`（通过 `MakeNativeFunction` 传入的 name 区分具体是 `app.getDetails`/`connect`/`sendMessage` 等） | `window.chrome.<member>` |
| 八 权限 | `content/shell/browser/shell_permission_manager.cc` | `ShellPermissionManager::GetPermissionStatus()` | `navigator.permissions.query/Notification.permission` |
| canvas 指纹 | `third_party/blink/renderer/core/canvas_interventions/fingerprint_stable_noise.{h,cc}` 新增导出函数 `FingerprintApiTrace()`，从 `html_canvas_element.cc::ToDataURLInternal()` 和 `base_rendering_context_2d.cc::getImageDataInternal()` 调用 | 见下 | `canvas.toDataURL` / `ctx2d.getImageData` |
| audio 指纹 | `third_party/blink/renderer/modules/webaudio/fingerprint_audio_stable_noise.{h,cc}` 新增导出函数 `FingerprintApiTraceAudio()`，从 `offline_audio_context.cc::FireCompletionEvent()` 调用 | 见下 | `OfflineAudioContext.FireCompletionEvent` |

canvas/audio 两处没有像其它文件那样用 `#define FP_API_TRACE(name)` 宏，而是在已有的 `fingerprint_stable_noise.{h,cc}` / `fingerprint_audio_stable_noise.{h,cc}`（这两个文件本来就是给 canvas/audio noise 用的小工具文件，`html_canvas_element.cc`/`base_rendering_context_2d.cc`/`offline_audio_context.cc` 本来就已经 `#include` 了它们）里加了一个导出函数。这样可以直接在那三个体量很大的文件里调用，**不需要给它们新增任何 include**，降低触碰大文件的风险。

## 本轮**没有**覆盖的点（如实记录，别假装做了）

- `chrome.webstore`——本来就不存在，没有可埋点的位置。
- adp 设备能力位（`vibrate`/`getBattery`/`DeviceMotionEvent` 等）——content_shell 里这些没有被我们的 profile 机制覆盖过，没有现成的改动点可以顺手加。
- `RTCPeerConnection` 构造、`mediaDevices.enumerateDevices()`——所在文件（WebRTC/mediastream 相关）体量大、改动风险高，本轮先跳过，没有强行加。
- `Function.prototype.toString` 等反射探针本身——这类是这次装配 `window.chrome`/plugins 时的**架构性保证**（原生 V8 函数天然 `[native code]`），不是"被调用"的东西，没法用同样方式埋点。

## 编译

```bash
cd /Users/zy.yuan/Develop/browser-runtime-projects/chromium-workspace/src
buildtools/mac/gn gen out/ContentShell
autoninja -C out/ContentShell content_shell
```

本轮没有新增源文件，`gn gen` 理论上不需要重新识别新文件，但因为改了 `third_party/blink/public/common/switches.h` 这种被广泛 include 的头文件，会触发 Blink core 大范围增量重编（参考 status-010/012 的经验，大概 10 分钟量级），属正常。

## 用法

```bash
"out/ContentShell/Content Shell.app/Contents/MacOS/Content Shell" \
  --user-data-dir="$(mktemp -d)" --no-first-run --disable-breakpad \
  --fingerprint-profile=/Users/zy.yuan/Develop/browser-runtime-projects/chromium-minimal-runtime/config/mac_chrome_profile.json \
  --fp-api-trace \
  --fp-api-trace-file=/tmp/fp_api_trace.log \
  "https://www.royalmail.com/track-your-item#/tracking-results/<单号>"
```

终端里 grep `[FP_API_TRACE]` 就能看到页面加载过程中实际调用了哪些被埋点的 API、调用了几次、大致顺序；加了 `--fp-api-trace-file` 的话同样的内容也会追加进 `/tmp/fp_api_trace.log`，跑完直接 `cat`/`sort | uniq -c` 那个文件就行，不用再从终端一堆其它 Chromium 日志里挑。因为这套东西打点的是 C++ 实现本身，真实 Chrome 没法装同样的东西（闭源发行版，没源码也不能重新编译），所以这份 trace **只能拿来看 content_shell 自己摸了什么**，没法跟真 Chrome 直接比对调用列表——如果要跟真 Chrome 对比"摸没摸某个 API"，还是得用 `tools/api_usage_probe/`（CDP 注入的办法，两边都能跑，但有 JS 层 hook 的局限，见该工具自己的文档）。这两套工具是互补的：content_shell 这边先用源码级 trace 摸清楚"我自己在这次加载里到底调用了什么、和 profile 是否生效对得上"，真 Chrome 那边继续靠 CDP 或抓包去看。

### 已验证的坑：`--fp-api-trace-file` 在沙箱化的子进程里会静默失效

实测跑了两遍 royalmail 页面后，`/tmp/fp_api_trace.log` 里 101 行**全部**是同一条 `navigator.permissions.query/Notification.permission`（这是 `shell_permission_manager.cc::GetPermissionStatus()` 打的，跑在 browser 进程）。navigator.\*/screen.\*/webgl/canvas/audio/speechSynthesis/window.chrome 这些埋在 renderer 进程里的点一条都没写进文件——不是没触发，是 renderer 进程默认跑在沙箱里，`fopen(path, "a")` 直接被拒绝、静默失败（这正是设计时写在文档里的那条注释预告的情况，现在实测坐实了）。

结论：**`--fp-api-trace-file` 目前只能可靠捕获 browser 进程侧的埋点**（目前只有 permission manager 这一处）。要拿到 renderer 侧那十来个点的完整数据，两个可行办法：

1. 加 `--no-sandbox` 跑 content_shell（纯诊断用，不要在生产/对抗场景下用这个开关，因为它本身就是一个巨大的检测信号），renderer 进程就能直接写文件了。
2. 不依赖 `--fp-api-trace-file`，改用 Chromium 自带的 `--enable-logging=stderr --log-file=/tmp/chrome_full.log`（或者直接把终端输出重定向到文件），因为 `LOG(INFO)` 本身不经过文件系统沙箱检查，子进程日志一直都能正常透传到这个统一日志里；跑完之后 `grep '\[FP_API_TRACE\]' /tmp/chrome_full.log` 一样能拿到全量数据，缺点是文件里会混着大量无关的 Chromium 日志噪音。

下次要看全量 trace，用其中一种重新采集。

## 如何跟原版 Chromium 对比（`chromium-workspace/src` 未纳入版本控制）

因为这个 checkout 不是 git 仓库，没法直接 `git diff` 出改动。不需要另外编译一份干净 Chromium——直接对照 [source.chromium.org](https://source.chromium.org/chromium/chromium/src) 上的同名文件即可：

1. 用上面"改动清单"表格逐个文件、逐个函数去核对——每一处都写清楚了具体文件路径和函数名，在 source.chromium.org 里搜到对应文件/函数，跟本仓库当前内容对照着看就知道多了哪几行。
2. 如果只关心某一类检测点（比如 screen.* 或 window.chrome），直接照表格里的行去查就够了，不用整文件通读。
3. 后续如果要把这套 trace 正式沉淀成 patch（参考 `patches/patch_e0488508e6-v1.txt` 的方式），建议单独导出一个 `0091-fp-api-trace.patch`，跟指纹 mock 主 patch 分开，因为这个纯粹是诊断工具、不该进生产 patch 集。

（`tools/fp_api_trace/apply_fp_api_trace.py` 之前是为了把这套埋点重放到另一份干净 checkout 上编译对比用的，如果之后真的想编译一份 vanilla Chromium 做逐行 trace diff，这个脚本还在，可以直接用；日常核对改动量的话用上面 source.chromium.org 的办法就够了。）
