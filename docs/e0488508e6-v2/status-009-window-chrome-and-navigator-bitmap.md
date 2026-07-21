# 配置驱动指纹 Mock（阶段 D：window.chrome 结构 + navigator 属性存在性 bitmap）

接续 `status-008`，本轮处理两个 Akamai 重点检测面：
1. `window.chrome` 是否存在、其结构是否与 Chrome UA 匹配；
2. `navigator.*` 属性存在性 bitmap（`bluetooth`/`usb`/`getGamepads`/`credentials`…）。

## 先测量，再决定改什么

构建探针枚举当前 minimal content_shell 的真实状态（profile 下）：

### navigator 属性存在性 bitmap —— 无需改动

枚举 40 个常见属性，结果全部 `true`（与真实桌面 Chrome 一致）：

```
webdriver, credentials, bluetooth, getGamepads, hardwareConcurrency,
deviceMemory, mediaDevices, permissions, serviceWorker, sendBeacon, usb,
hid, serial, geolocation, clipboard, storage, userActivation,
mediaCapabilities, presentation, wakeLock, xr, gpu, plugins, mimeTypes,
pdfViewerEnabled, maxTouchPoints, connection, scheduling, virtualKeyboard,
ink, windowControlsOverlay, userAgentData, ...  → 全部存在
```

- `"webdriver" in navigator === true`（属性存在、值为 `false`）——与真实 Chrome 一致，不是信号。
- 这些 API 由 Blink RuntimeEnabledFeatures / 构建特性原生暴露，content_shell 默认就齐全。**本阶段对 bitmap 不做任何改动**（删一个反而偏离真机）。

### window.chrome —— `exists: false`（真正的破绽）

真实 Chrome 始终暴露 `window.chrome`（`chrome.runtime`/`chrome.csi`/`chrome.loadTimes`/`chrome.app`）。
content_shell 不是 Chrome 产品层，没有 `window.chrome`，这是明显的非真实 Chrome 信号。**本阶段的核心工作就是补上它。**

## 设计：renderer 内用 V8 原生函数装配 window.chrome

关键约束：`window.chrome` 由 renderer 进程注入，而 **renderer 处于沙箱中、无法读取 profile JSON 文件**（这是初版踩的坑：直接在 renderer 调 `ShellFingerprintProfile::Get()` 读文件，沙箱拦截 → profile 为空 → 不生效）。

因此沿用阶段 B/C 的机制：**browser 翻译 profile → 命令行 switch → renderer 读 switch**。

### 新增 content_shell switch

`content/shell/common/shell_switches.h`：

```text
fp-window-chrome   # "chrome" 暴露 Chrome 式 window.chrome；缺省/其它保持原样
```

- `content/shell/common/shell_fingerprint_profile.{h,cc}`：解析 `chrome_object.mode`。
- `content/shell/browser/shell_content_browser_client.cc`：browser 在 renderer 进程命令行 append `fp-window-chrome=<mode>`。

### renderer 装配（零 JS 注入）

`content/shell/renderer/shell_render_frame_observer.cc`
`DidClearWindowObject()` 中读 switch，命中 `chrome` 时调用 `InstallWindowChrome()`：

- 通过 `frame->GetAgentGroupScheduler()->Isolate()` 取主世界 isolate；
- `MainWorldScriptContext()` 取上下文，在 C++ 层用 `v8::Object::New` / `v8::Function::New` 装配：
  - `chrome.app`：`{isInstalled:false, InstallState{...}, RunningState{...}, getDetails/getIsInstalled/installState/runningState}`；
  - `chrome.csi`、`chrome.loadTimes`：原生函数，分别返回合理的 timing 对象；
  - `chrome.runtime`：`{connect, sendMessage, id:undefined, OnInstalledReason{...}, PlatformOs{...}}`；
- 所有方法都是真正的 `v8::Function`，因此 `Function.prototype.toString` 显示 `[native code]`，与 Chrome 原生一致，**不暴露任何 JS hook**。

> 说明：这与"页面 JS 注入"本质不同——是 embedder 在 C++/V8 层装配原生对象，正是 Chrome 自身构建 `window.chrome` 的方式。

## 运行验证（baseline vs profile）

| 检测点 | 无 profile | chrome profile |
|---|---|---|
| `typeof window.chrome` | undefined | **object** |
| `Object.keys(chrome)` | — | app, csi, loadTimes, runtime |
| `typeof chrome.runtime` | — | object |
| `Object.keys(chrome.runtime)` | — | connect, sendMessage, id, OnInstalledReason, PlatformOs |
| `typeof chrome.runtime.connect` | — | function |
| `typeof chrome.runtime.sendMessage` | — | function |
| `chrome.runtime.id` | — | undefined（非扩展页）|
| `typeof chrome.csi` / `chrome.loadTimes` | — | function / function |
| `typeof chrome.app` / `app.isInstalled` | — | object / false |
| `chrome.csi()` | — | {startE,onloadT,pageT,tran:15} |
| `chrome.loadTimes()` | — | {connectionInfo:'h2', npnNegotiatedProtocol:'h2', ...} |
| `Function.prototype.toString.call(chrome.csi)` | — | `function csi() { [native code] }` |
| `Function.prototype.toString.call(chrome.runtime.connect)` | — | `function connect() { [native code] }` |
| `Object.prototype.toString.call(chrome)` | — | [object Object] |

navigator bitmap 两种情况都全 `true`（未改）。

结论：profile 下 `window.chrome` 形状与真实 Chrome 桌面端一致，且完全 native、反射安全；无 profile 时保持 content_shell 原样（opt-in）。

## 编译

`autoninja -C out/ContentShell content_shell` 成功（触及 content/shell common + browser + renderer，增量链接通过）。

## 累计已 native mock 的检测面

UA / UA-CH / Accept-Language / languages / webdriver / platform / productSub / vendor / hardwareConcurrency / deviceMemory / timezone / plugins / mimeTypes / pdfViewerEnabled / **window.chrome（app/csi/loadTimes/runtime）**。navigator 属性存在性 bitmap 已确认与真机一致（无需改）。

## 尚未做（后续）

- `screen` / `window` 几何（阶段 E）。
- `RTCPeerConnection` / `mediaDevices.enumerateDevices` / `speechSynthesis` / `permissions.query` 行为（阶段 F）。
- WebGL vendor/renderer、Canvas/Audio stable noise（阶段 G）。
- `navigator.maxTouchPoints` 接入。
- `chrome.app` / `chrome.runtime` 枚举值的随机化/profile 化（当前固定为真机典型值，足够一致）。
