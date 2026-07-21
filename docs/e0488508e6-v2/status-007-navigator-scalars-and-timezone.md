# 配置驱动指纹 Mock（阶段 B 标量字段 + 时区）

接续 `status-006`，本轮继续按"整机 profile 优先 + native mock 优先"补齐 navigator 标量字段和时区，全部 native、零 JS 注入。

## 本轮覆盖的检测点

| 字段 | 来源 profile 字段 | 实现层 |
|---|---|---|
| `navigator.platform` | `navigator.platform` | Blink getter 读 switch |
| `navigator.productSub` | `navigator.productSub` | Blink getter 读 switch |
| `navigator.vendor` | `navigator.vendor` | Blink getter 读 switch |
| `navigator.hardwareConcurrency` | `navigator.hardwareConcurrency` | Blink getter 读 switch |
| `navigator.deviceMemory` | `navigator.deviceMemory` | Blink getter 读 switch |
| `Intl...timeZone` / `Date` 偏移 | 顶层 `timezone` | `TZ` 环境变量（ICU 原生识别）|

`navigator.maxTouchPoints` 已在 profile 中解析但本轮未接入 getter（桌面端默认 0 已自洽），留待触屏 profile 阶段。

## 设计

核心机制：**browser 进程把 profile 翻译成命令行 switch，Blink 渲染进程读取 switch**。JSON 解析只发生在 browser 侧；Blink 只读简单字符串 switch（Chromium 本身大量配置就是这样流动的），因此 `Function.prototype.toString`、descriptor、枚举顺序等反射探针不会暴露任何 hook 痕迹。

### 新增 Blink switch

`third_party/blink/public/common/switches.h` / `third_party/blink/common/switches.cc`：

```text
fp-navigator-platform
fp-navigator-product-sub
fp-navigator-vendor
fp-hardware-concurrency
fp-device-memory
```

### Blink getter 改动（读 switch，缺省回退 host/默认值）

- `third_party/blink/renderer/core/frame/navigator.cc`
  - `Navigator::platform()` / `productSub()` / `vendor()`：switch 非空则返回 `String::FromUtf8(switch)`。
- `third_party/blink/renderer/core/frame/navigator_concurrent_hardware.cc`
  - `hardwareConcurrency()`：switch 解析为 `unsigned` 且 `>0` 时返回，否则 `base::SysInfo::NumberOfProcessors()`。
- `third_party/blink/renderer/core/frame/navigator_device_memory.cc`
  - `deviceMemory()`：switch 解析为 `double` 且 `>0` 时返回，否则 `ApproximatedDeviceMemory`。

### browser 翻译 + 时区

- `content/shell/browser/shell_content_browser_client.cc`
  - `AppendExtraCommandLineSwitches()`：当子进程是 renderer 且 profile 非空时，把上述字段 append 成 `fp-*` switch。
- `content/shell/app/shell_main_delegate.cc`
  - `BasicStartupComplete()` 最前面（**早于 ICU 初始化**）：若 profile 有 timezone，`base::Environment::SetVar("TZ", tz)`。子进程继承该环境变量，因此 browser 与 renderer 时区一致。

### profile loader 扩展

`content/shell/common/shell_fingerprint_profile.{h,cc}` 新增解析与访问器：
`navigator.platform / productSub / vendor / hardwareConcurrency / deviceMemory / maxTouchPoints` 和顶层 `timezone`。

## 编译

```bash
cd /Users/zy.yuan/Develop/browser-runtime-projects/chromium-workspace/src
autoninja -C out/ContentShell content_shell
```

本轮触及 Blink core（navigator.cc 等），增量编译比 status-006 略重，已成功。

注意：WTF 的 UTF-8 构造是 `String::FromUtf8(std::string_view)`（小写 `tf8`），不是 `FromUTF8`。

## 运行验证

对比"无 profile（host 默认）"、"Mac Chrome profile"、"Windows-like 测试 profile"三组：

| 字段 | host 默认 | mac_chrome_137_m2 | win-like 测试 |
|---|---|---|---|
| platform | MacIntel | MacIntel | **Win32** |
| productSub | 20030107 | 20030107 | **20100101** |
| vendor | Google Inc. | Google Inc. | **Acme Browser Inc.** |
| hardwareConcurrency | 8 | 8 | **4** |
| deviceMemory | **16** | **8** | **4** |
| timeZone | Asia/Shanghai | **Asia/Singapore** | **America/New_York** |
| Date 偏移(min) | -480 | -480 | **300** |
| languages | en-US | en-US,en | **fr-FR,fr** |

关键证据：
- `deviceMemory` 从 host 的 16 被强制为 profile 的 8/4 —— switch 覆盖生效；
- `timeZone` 从 host 的 Asia/Shanghai 改为 profile 时区，且 `Date.getTimezoneOffset()` 在 America/New_York 下变为 300 —— ICU 原生识别 `TZ` 生效；
- win-like profile 下 platform/productSub/vendor/hardwareConcurrency 全部按 profile 改变 —— 证明 switch 读取路径对全部标量字段有效。

## 累计已 native mock 的 Akamai 检测面

- UA / UA-CH / Accept-Language / navigator.languages（status-006）
- navigator.webdriver = false（content_shell 默认）
- navigator.platform / productSub / vendor / hardwareConcurrency / deviceMemory（本轮）
- timezone（Intl + Date，本轮）

## 尚未做（后续）

- `navigator.maxTouchPoints` 接入（触屏 profile）。
- `navigator.plugins` / `mimeTypes`（native PluginArray，阶段 C）。
- `window.chrome` 结构与属性存在性 bitmap（阶段 D）。
- `screen` / `window` 几何（阶段 E）。
- `RTCPeerConnection` / `mediaDevices` / `speechSynthesis` / permissions（阶段 F）。
- WebGL vendor/renderer、Canvas/Audio stable noise（阶段 G）。
