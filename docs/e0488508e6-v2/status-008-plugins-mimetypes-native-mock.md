# 配置驱动指纹 Mock（阶段 C：navigator.plugins / mimeTypes）

接续 `status-007`，本轮做 Akamai 重点检测项 `navigator.plugins` / `navigator.mimeTypes` / `navigator.pdfViewerEnabled` 的 native mock。

## 背景：为什么必须 mock

Blink 里 `navigator.plugins` 由 `DOMPluginArray` 构造，逻辑是：

```cpp
DOMPluginArray::DOMPluginArray(window) {
  if (IsPdfViewerAvailable()) {
    // crbug.com/1164635：为降低指纹、提高互操作，硬编码的固定插件列表
    Vector<String> plugins{"PDF Viewer", "Chrome PDF Viewer",
                           "Chromium PDF Viewer", "Microsoft Edge PDF Viewer",
                           "WebKit built-in PDF"};
    ...
  }
}
```

- 真实 Chrome 桌面端固定暴露这 5 个 PDF 插件 + 2 个 mime（`application/pdf`、`text/pdf`）。
- 本项目编译关闭了 PDF（`enable_pdf=false`），导致 `IsPdfViewerAvailable()` 返回 false，`navigator.plugins` 为**空**。
- 空 plugins 在 Akamai/反爬里是明显的非真实 Chrome 信号。

`navigator.mimeTypes`（`DOMMimeTypeArray`）和 `navigator.pdfViewerEnabled` 都从同一来源派生，因此只要驱动 `IsPdfViewerAvailable()` 即可三者一致。

## 设计

沿用"browser 翻译 profile → switch，Blink 读 switch"机制，零 JS 注入。

### 新增 Blink switch

`third_party/blink/{public/common,common}/switches.{h,cc}`：

```text
fp-plugins-mode   # "chrome_pdf" | "empty" | 缺省(host 默认)
```

### Blink 改动（单点）

`third_party/blink/renderer/modules/plugins/dom_plugin_array.cc`
`DOMPluginArray::IsPdfViewerAvailable()` 开头读 switch：
- `chrome_pdf` → 返回 true（复用 Chrome 原生硬编码 5 插件构造路径）；
- `empty` → 返回 false；
- 缺省 → 原 `PluginData` 逻辑。

这一处改动会级联到：
- `navigator.plugins`（5 个 `DOMPlugin`，真实 `PluginInfo`/`MimeClassInfo` 对象）；
- `navigator.mimeTypes`（`GetFixedMimeTypeArray()` 取第一个插件的 2 个 mime）；
- `navigator.pdfViewerEnabled`（直接调用 `IsPdfViewerAvailable()`）。

因为复用 Chrome 自己的原生对象，所以 `PluginArray`/`MimeTypeArray` 形状、`item()`/`namedItem()`/数字与命名索引、反向引用（`mimeType.enabledPlugin`）、`Object.prototype.toString`、`Function.prototype.toString` 全部与真实 Chrome 一致，反射探针无 hook 痕迹。

### browser 翻译 + loader + config

- `content/shell/common/shell_fingerprint_profile.{h,cc}`：解析 `plugins.mode`。
- `content/shell/browser/shell_content_browser_client.cc`：renderer 进程 append `fp-plugins-mode`。
- `config/mac_chrome_profile.json`：新增 `"plugins": {"mode": "chrome_pdf"}`。

## 运行验证（baseline vs profile）

| 检测点 | 无 profile | chrome_pdf profile |
|---|---|---|
| `plugins.length` | 0 | **5** |
| 插件名 | [] | PDF Viewer / Chrome PDF Viewer / Chromium PDF Viewer / Microsoft Edge PDF Viewer / WebKit built-in PDF |
| `mimeTypes.length` | 0 | **2**（application/pdf, text/pdf）|
| `pdfViewerEnabled` | false | **true** |
| `toString(plugins)` | [object PluginArray] | [object PluginArray] |
| `toString(plugins[0])` | — | [object Plugin] |
| `namedItem('Chrome PDF Viewer')` | — | 命中 |
| `plugins['Chrome PDF Viewer'].name` | — | Chrome PDF Viewer |
| `plugins[0].length` | — | 2 |
| `plugins[0][0].type` | — | application/pdf |
| `mimeTypes[0].enabledPlugin.name`（反向引用）| — | PDF Viewer |
| `mimeTypes['application/pdf'].type` | — | application/pdf |
| `Function.prototype.toString.call(plugins.item)` | function item() { [native code] } | { [native code] }（无 hook）|

结论：profile 下 `navigator.plugins`/`mimeTypes`/`pdfViewerEnabled` 与真实 Chrome 桌面端完全一致，且 native、反射安全。

## 编译

`autoninja -C out/ContentShell content_shell` 成功（本轮触及 blink modules/plugins + common，增量链接通过）。

## 累计已 native mock 的检测面

UA / UA-CH / Accept-Language / languages / webdriver / platform / productSub / vendor / hardwareConcurrency / deviceMemory / timezone / **plugins / mimeTypes / pdfViewerEnabled**。

## 尚未做（后续）

- `window.chrome` 结构与 navigator 属性存在性 bitmap（阶段 D）。
- `screen` / `window` 几何（阶段 E）。
- `RTCPeerConnection` / `mediaDevices` / `speechSynthesis` / permissions（阶段 F）。
- WebGL vendor/renderer、Canvas/Audio stable noise（阶段 G）。
- `navigator.maxTouchPoints` 接入。
- profile `plugins` 的按权重自定义列表（当前先支持与真机一致的 `chrome_pdf` / `empty`，自定义列表偏离真机反而更易被识别，暂不优先）。
