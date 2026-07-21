# 配置驱动指纹 Mock（阶段 G：WebGL unmasked vendor/renderer）

接续 `status-011`，本轮处理 GPU 指纹面 `WEBGL_debug_renderer_info` 的 `UNMASKED_VENDOR_WEBGL` / `UNMASKED_RENDERER_WEBGL`。

## 先测量

| 检测点 | content_shell 默认 | 说明 |
|---|---|---|
| `gl.getParameter(gl.VENDOR)` | `WebKit` | 与真实 Chrome 一致（通用值），无需改 |
| `gl.getParameter(gl.RENDERER)` | `WebKit WebGL` | 同上 |
| `UNMASKED_VENDOR_WEBGL` | `Google Inc. (Apple)` | 真实 Chrome 格式；但值来自**真实宿主 GPU** |
| `UNMASKED_RENDERER_WEBGL` | `ANGLE (Apple, Apple M2, OpenGL 4.1)` | **泄漏真实宿主 GPU + 后端**；换机器就变，与所声明设备不一致 |
| `getParameter.toString()` | `[native code]` | 干净 |
| WebGL2 unmasked renderer | 同上 | WebGL2 走同一 getParameter 路径 |

问题：`UNMASKED_*` 直接读宿主 GPU（`ContextGL()->GetString(GL_VENDOR/GL_RENDERER)`）。本机恰为 M2 所以看似一致，但一旦换到 Intel Mac / Linux，就会与 "Mac M2 Chrome" profile 矛盾。且 content_shell 用的是 OpenGL 后端，真实 Chrome on Mac 默认是 **Metal** 后端，渲染串不同。

## 设计

沿用 browser→switch→Blink 机制，在 WebGL getParameter 的两个 unmasked 分支做返回值覆盖。

### 新增 Blink switch

`third_party/blink/{public/common,common}/switches.{h,cc}`：

```text
fp-webgl-vendor     # UNMASKED_VENDOR_WEBGL 覆盖
fp-webgl-renderer   # UNMASKED_RENDERER_WEBGL 覆盖
```

### Blink 改动（单点）

`third_party/blink/renderer/modules/webgl/webgl_rendering_context_base.cc`
`getParameter()` 的 `kUnmaskedRendererWebgl` / `kUnmaskedVendorWebgl` 分支：switch 非空则返回 profile 串，否则回落 `ContextGL()->GetString(...)`。

- 只改返回值、不改函数对象本身，`getParameter.toString()` 仍是 `[native code]`，反射安全。
- WebGL2（`WebGL2RenderingContextBase` 继承同一 getParameter）自动覆盖，无需额外改。

### loader + translate + config

- `content/shell/common/shell_fingerprint_profile.{h,cc}`：解析 `webgl.{unmaskedVendor,unmaskedRenderer}`（兼容 `vendor`/`renderer` 简写）。
- `content/shell/browser/shell_content_browser_client.cc`：renderer 进程 append 两个 switch。
- `config/mac_chrome_profile.json`：改为真实 Chrome on Mac (Metal) 的串：

```json
"webgl": {
  "unmaskedVendor": "Google Inc. (Apple)",
  "unmaskedRenderer": "ANGLE (Apple, ANGLE Metal Renderer: Apple M2, Unspecified Version)"
}
```

## 运行验证（profile）

| 检测点 | 结果 |
|---|---|
| `UNMASKED_VENDOR_WEBGL` | `Google Inc. (Apple)` ✅ |
| `UNMASKED_RENDERER_WEBGL` | `ANGLE (Apple, ANGLE Metal Renderer: Apple M2, Unspecified Version)` ✅ |
| WebGL2 `UNMASKED_RENDERER_WEBGL` | 同上（同步覆盖）✅ |
| `getParameter.toString()` | `function getParameter() { [native code] }` ✅ 无 hook |
| `VENDOR` / `RENDERER` | `WebKit` / `WebKit WebGL`（未改，与真机一致）✅ |

要点：即便 content_shell 实际后端是 OpenGL，也能稳定报告真实 Chrome 的 Metal 渲染串，跨宿主一致。

## 编译

`autoninja -C out/ContentShell content_shell` 成功。改了 Blink 公共 `switches.h` + 巨型 `webgl_rendering_context_base.cc`，触发 blink core 大范围增量重编（~9.5 分钟），属正常。

## 残留 / 后续

- **Canvas / Audio stable noise 未做**：本轮测得 `canvas_hash` / `audio_sum` 仍为宿主原始输出。canvas/audio 指纹主要用于**跨站追踪**（隐私），而非"是否机器人"判定；相较之下 GPU 一致性对反爬检测优先级更高，故本轮聚焦 WebGL。stable-noise 需在 2D canvas 读回路径 / 音频 buffer 注入确定性噪声，工作量较大，单列后续（阶段 H）。config 已预留 `canvas`/`audio` 字段。
- `Notification.permission` / `speechSynthesis` 语音列表（见 status-011 残留）。
- `navigator.maxTouchPoints` 接入。

## 累计已 native mock 的检测面

UA / UA-CH / Accept-Language / languages / webdriver / platform / productSub / vendor / hardwareConcurrency / deviceMemory / timezone / plugins / mimeTypes / pdfViewerEnabled / window.chrome / screen 几何 / window 尺寸 / permissions 默认状态 / **WebGL unmasked vendor+renderer（WebGL1/2）**。
