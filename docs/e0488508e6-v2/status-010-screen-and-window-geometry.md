# 配置驱动指纹 Mock（阶段 E：screen / window 几何）

接续 `status-009`，本轮处理 `screen.*` 与 `window` 几何。

## 先测量：默认状态的问题

无 profile 时（宿主为 MacBook，dpr=2）：

| 字段 | 默认值 | 问题 |
|---|---|---|
| `screen.width/height` | 1470 × 956 | 跟随**宿主显示器**——同一 profile 换机器就变，与所声明设备不一致 |
| `screen.colorDepth/pixelDepth` | **30** | 10-bit/HDR 屏的少见值；真实 Chrome 几乎恒为 **24**，30 是明显异常 |
| `screen.availHeight` | 跟随宿主 Dock | 不稳定 |
| `window.innerWidth/Height` | **800 × 600** | content_shell 固定默认窗口，是 content_shell 的特征指纹 |
| `window.outerWidth/Height` | 800 × 656 | 同上 |

## 设计

两类几何来源不同，分别处理，都保持"配置驱动 + native"：

### 1) screen.* —— Blink getter 级覆盖（switch 驱动）

`screen.*` 全部源于 `display::ScreenInfo`（`rect` / `available_rect` / `depth`），由 `Screen::GetRect()` / `Screen::colorDepth()` 读取。

- 新增 Blink switch（`third_party/blink/{public/common,common}/switches.{h,cc}`）：
  `fp-screen-width` / `-height` / `-avail-width` / `-avail-height` / `-avail-left` / `-avail-top` / `-color-depth`（逻辑/DIP，缺省=宿主值）。
- `third_party/blink/renderer/core/frame/screen.cc`：
  - `GetRect(available)` 取到 rect 后、在 physical-pixels quirk 之前，用 switch 覆盖对应分量（available 用 avail-* 四项，full 用 width/height）；
  - `colorDepth()` 优先读 `fp-screen-color-depth`。
- `pixelDepth()` 复用 `colorDepth()`，自动一致。

### 2) window 几何 —— 真正 resize 窗口（不伪造 getter）

`window.innerWidth/Height`、`outerWidth/Height`、`screenX/Y` 都源于真实窗口尺寸/位置。**伪造 getter 会与布局/媒体查询/`getBoundingClientRect` 矛盾**，因此选择**实际把窗口创建成 profile 指定的尺寸**，让这些值自然派生、彼此一致。

- 复用 content_shell 既有的 `--content-shell-host-window-size=WxH`（`Shell::GetShellDefaultSize()` 读取，作用于 web 内容/inner 尺寸）。
- `content/shell/app/shell_main_delegate.cc::BasicStartupComplete()`：从 profile 读 `window.innerWidth/innerHeight`，在窗口创建前 append 该 switch（与 TZ 设置同处，早于 `Shell::Initialize`）。

### loader + config

- `content/shell/common/shell_fingerprint_profile.{h,cc}`：解析 `screen.{width,height,availWidth,availHeight,availLeft,availTop,colorDepth}` 与 `window.{innerWidth,innerHeight}`（均为可选，缺省回落宿主）。
- `content/shell/browser/shell_content_browser_client.cc`：把 `screen.*` 翻译成 renderer 命令行 switch。
- `config/mac_chrome_profile.json`：合并了原先重复的 `screen` 键（JSON 重复键后者覆盖前者，曾导致取到旧块），统一为单一块：

```json
"screen": {"width":1440,"height":900,"availLeft":0,"availTop":25,
           "availWidth":1440,"availHeight":875,"colorDepth":24},
"window": {"innerWidth":1280,"innerHeight":720}
```

## 运行验证（baseline vs profile）

| 检测点 | 无 profile | profile |
|---|---|---|
| `screen.width × height` | 1470 × 956（宿主）| **1440 × 900** |
| `screen.availWidth × availHeight` | 1470 × 836 | **1440 × 875** |
| `screen.availLeft / availTop` | 0 / 33 | 0 / **25** |
| `screen.colorDepth / pixelDepth` | **30 / 30** | **24 / 24** |
| `window.innerWidth × innerHeight` | 800 × 600 | **1280 × 720** |
| `window.outerWidth × outerHeight` | 800 × 656 | **1280 × 776** |
| `window.screenX / screenY` | 0 / 210 | 0 / **90**（窗口居中后自然派生）|
| `devicePixelRatio` | 2 | 2 |
| `orientation.type / angle` | landscape-primary / 0 | 同 |

要点：
- `colorDepth` 异常 30 → 24，与真实 Chrome 一致。
- `screen.*` 不再跟随宿主、由 profile 固定，跨机器稳定。
- 窗口是**真实 resize**（inner/outer/screenX/Y 全部联动一致），无 getter 伪造、无布局矛盾。

## 编译

`autoninja -C out/ContentShell content_shell` 成功。注意：本轮改了 Blink 公共 `switches.h`，触发 blink core 大范围增量重编（~12 分钟），属正常。

## 累计已 native mock 的检测面

UA / UA-CH / Accept-Language / languages / webdriver / platform / productSub / vendor / hardwareConcurrency / deviceMemory / timezone / plugins / mimeTypes / pdfViewerEnabled / window.chrome / **screen.{width,height,avail*,colorDepth,pixelDepth} / window 实际尺寸（inner/outer/screenX/Y）**。

## 残留 / 后续

- `outerHeight - innerHeight = 56`（content_shell 标题栏），真实 Chrome 的浏览器 chrome 高度不同；因 content_shell 无 tab/omnibox UI，属固有差异，暂不处理。
- `devicePixelRatio` 仍跟随宿主（当前 Mac=2，与 profile 设备一致）；跨 host 强一致需覆盖 dsf，会影响渲染缩放，单列后续评估。
- 阶段 F：`RTCPeerConnection` / `mediaDevices.enumerateDevices` / `speechSynthesis` / `permissions.query` 行为。
- 阶段 G：WebGL vendor/renderer、Canvas/Audio stable noise。
- `navigator.maxTouchPoints` 接入。
