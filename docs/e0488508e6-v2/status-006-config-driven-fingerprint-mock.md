# 配置驱动指纹 Mock（阶段 A + B 核心）

## 目标

按 `plan-runtime-profile-mock.md` 的"整机 profile 优先 + native mock 优先"原则，让 `content_shell` 启动时读取一个 JSON profile，并在 native 层把以下 Akamai 高优先级检测点统一对齐：

- `navigator.userAgent` 与 HTTP `User-Agent` 一致；
- `navigator.userAgentData` / `Sec-CH-UA`（含 high-entropy）与 UA 一致；
- `navigator.languages` / `navigator.language` 与 HTTP `Accept-Language` 一致；
- `navigator.webdriver` 保持 `false`。

本阶段全部走 Chromium 已有的 native embedder 通道，**没有任何页面 JS 注入**，因此 `Function.prototype.toString`、descriptor、枚举顺序等反射探针不会暴露 hook 痕迹。

## 命令行入口

```bash
Content Shell --fingerprint-profile=/path/to/profile.json <url>
```

- profile 在 browser 进程早期按需加载（首次访问 `ShellFingerprintProfile::Get()` 时）。
- 该 switch 会通过 `AppendExtraCommandLineSwitches` 转发给子进程，供后续 renderer 侧阶段使用。
- 文件缺失/解析失败时回退到 content_shell 默认值（不崩溃）。
- 显式 `--user-agent` 优先级高于 profile。

## profile schema（本阶段消费字段）

```json
{
  "name": "mac_chrome_137_m2",
  "browser": {
    "userAgent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) ... Chrome/137.0.0.0 Safari/537.36",
    "userAgentData": {
      "brands": [{"brand": "Google Chrome", "version": "137"}, ...],
      "fullVersionList": [{"brand": "Google Chrome", "version": "137.0.0.0"}, ...],
      "mobile": false,
      "platform": "macOS",
      "platformVersion": "15.3.0",
      "architecture": "arm",
      "bitness": "64",
      "model": "",
      "uaFullVersion": "137.0.0.0"
    }
  },
  "navigator": { "languages": ["en-US", "en"] },
  "network": { "acceptLanguage": "en-US,en;q=0.9" }
}
```

- `userAgent` 也兼容顶层 `userAgent`（旧版 profile）。
- `languages` 与 `network.acceptLanguage` 可只给其一，loader 会互相派生：
  - 只有 `languages` 时，按 Chrome 风格生成 `en-US,en;q=0.9`；
  - 只有 `acceptLanguage` 时，剥离 q 值得到 `["en-US","en"]`。

参考 profile：`config/mac_chrome_profile.json`，运行配置：`config/runtime.yaml`。

## 源码改动（chromium-workspace/src）

新增：

- `content/shell/common/shell_fingerprint_profile.h`
- `content/shell/common/shell_fingerprint_profile.cc`
  - `ShellFingerprintProfile`：JSON 解析 + 进程级单例（懒加载 `--fingerprint-profile`）。
  - 使用本 revision 的 `base::DictValue` / `base::ListValue` / `base::JSONReader::ReadDict` API。

修改：

- `content/shell/common/shell_switches.h`：新增 `kFingerprintProfile = "fingerprint-profile"`。
- `content/shell/BUILD.gn`：登记新源文件。
- `content/shell/browser/shell_content_browser_client.cc`：
  - `GetUserAgent()`：返回 profile UA；
  - `GetShellUserAgentMetadata()`：从 profile 构造 `blink::UserAgentMetadata`；
  - `GetShellLanguage()`：返回 profile 的 `Accept-Language`（带 q 值，供网络层）；
  - `AppendExtraCommandLineSwitches()`：转发 `--fingerprint-profile`。
- `content/shell/browser/shell.cc`：
  - 在 `Shell` 构造时把 `RendererPreferences::accept_languages` 设为**不带 q 值**的语言列表，驱动 `navigator.languages`。

关键区分：网络 `Accept-Language` header 带 q 值（`en-US,en;q=0.9`），而 renderer pref 的 `accept_languages` 必须是裸列表（`en-US,en`），否则 q 值会泄漏进 `navigator.languages`。

## 编译验证

```bash
cd /Users/zy.yuan/Develop/browser-runtime-projects/chromium-workspace/src
buildtools/mac/gn gen out/ContentShell
autoninja -C out/ContentShell content_shell
```

结果：`gn gen` 成功（新源文件被识别），`content_shell` 增量编译 + 链接成功。

## 运行验证

用本地 server 回显请求头、页面 `fetch` 上报 JS 指纹，启动：

```bash
"out/ContentShell/Content Shell.app/Contents/MacOS/Content Shell" \
  --user-data-dir="$(mktemp -d)" --no-first-run --disable-breakpad \
  --fingerprint-profile=config/mac_chrome_profile.json \
  http://127.0.0.1:8799/
```

实测结果（profile = `mac_chrome_137_m2`）：

| 检测点 | 结果 | 一致性 |
|---|---|---|
| HTTP `User-Agent` | `...Chrome/137.0.0.0 Safari/537.36` | = JS `navigator.userAgent` ✓ |
| `Accept-Language` header | `en-US,en;q=0.9` | ✓ |
| `Sec-CH-UA` | `"Google Chrome";v="137", "Chromium";v="137", "Not/A)Brand";v="24"` | = `navigator.userAgentData.brands` ✓ |
| `navigator.languages` | `["en-US","en"]` | 无 q 值泄漏 ✓ |
| `navigator.language` | `en-US` | ✓ |
| `navigator.webdriver` | `false` | ✓ |
| UA-CH high-entropy | platform=macOS, platformVersion=15.3.0, architecture=arm, bitness=64, uaFullVersion=137.0.0.0, fullVersionList | 全部来自 profile ✓ |

browser 进程日志确认：`Loaded fingerprint profile 'mac_chrome_137_m2' from ...`。

## 尚未做（后续阶段）

仍按 plan 的"能 mock 才能裁"红线推进，下面这些字段当前还是 content_shell 默认值，需要更深的 native binding 改动：

- `navigator.platform` / `productSub` / `vendor` / `hardwareConcurrency` / `deviceMemory` / `maxTouchPoints`（阶段 B 剩余）。
- `navigator.plugins` / `mimeTypes`（native `PluginArray`，阶段 C）。
- `window.chrome` 结构与属性存在性 bitmap（阶段 D）。
- `screen` / `window` 几何、timezone / Intl、时间锚定（阶段 E）。
- `RTCPeerConnection` / `mediaDevices` / `speechSynthesis` / permissions（阶段 F）。
- WebGL vendor/renderer、Canvas/Audio stable noise（阶段 G）。

## patch 归属

本次属于建议 patch 分组中的指纹 mock 框架起点，后续应导出为独立 patch（例如 `0090-config-driven-fingerprint-profile.patch`）。
