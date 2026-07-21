# Content Shell v2 裁剪计划

基线 commit：

```text
e0488508e67c7243b2f21e478727d1989f9d1e71
```

当前目标不是立刻把 Chromium 源码抽成独立小仓库，而是在固定 commit 上继续维护 patch stack，逐步减少 `content_shell` 的源码依赖、链接依赖和最终 app 体积。

当前已验证基线：

```text
Chromium 原始编译 app: 约 298M
当前提取 app:        约 205M
GN deps target:       约 6951 个
源码目录级闭包估算:   约 10-12G
```

关联检测文档：

```text
/Users/zy.yuan/Develop/browser-runtime-projects/chromium-minimal-runtime/docs/Akamai 检测.md
```

v2 裁剪必须把 Akamai 检测点作为兼容性红线。当前版本已经出现 Akamai 打不开/不通过的情况，所以后续裁剪不能只按“能编译、能启动、体积变小”判断成功，还要验证静态指纹、属性存在性、函数原生性、媒体/RTC/speech、时间和整机 profile 是否仍然自洽。

## 一、裁剪原则

### 1. 保留的底线能力

这些能力暂时不作为裁剪目标：

- Blink DOM/CSS/Layout/JS 执行能力。
- V8。
- Network Service。
- Cookie、Storage、Cache、IndexedDB 等现代网站基础存储能力。
- DevTools Protocol。
- 基础 GPU/compositor 能力。
- macOS 有头窗口启动能力。
- 现代网站常见图片格式基础解码能力。

原因：这些是采集运行时和反爬一致性的核心。过早裁掉会导致“体积小但不像真实浏览器”。

### 1.1 Akamai 兼容性红线

以下能力不能因为体积原因直接删除，除非已经有 native profile/mock 层提供与目标设备一致的替代行为：

- `navigator.webdriver`、`window.webdriver`、Selenium/Phantom 自动化标记必须保持 absent / undefined。
- `window.chrome` 的存在性和结构必须与 UA 匹配。Chrome UA 需要合理的 `chrome.runtime` 形状；Safari/iOS profile 则不应暴露 Chrome 对象。
- `navigator` 属性存在性 bitmap 不能随意变化，包括 `credentials`、`bluetooth`、`getGamepads`、`hardwareConcurrency`、`mediaDevices`、`permissions`、`serviceWorker`、`sendBeacon` 等。
- `navigator.plugins` / `navigator.mimeTypes` 不能只返回随便的数组；需要 PluginArray/MimeTypeArray 形状、长度、枚举属性和 descriptor 与目标浏览器一致。
- `screen`、`window.inner/outer`、`devicePixelRatio`、`platform`、`maxTouchPoints`、`productSub`、`standalone` 必须组成真实设备 profile。
- `RTCPeerConnection`、`mediaDevices`、`speechSynthesis.getVoices()` 等 API 不能粗暴移除；若目标 profile 应该存在，就要返回稳定结构。
- `Function.prototype.toString`、`Object.keys`、`getOwnPropertyDescriptor`、`hasOwnProperty`、`Symbol.toStringTag` 等反射探测不能暴露 JS 注入痕迹。
- `Date.now()`、performance 时间、sensor 派生时间字段必须锚定真实时间窗口，不能因为虚拟时间导致反重放校验异常。

裁剪策略调整：

```text
能删实现，不删表面形状；
能禁用后端，不破坏 API 存在性；
能 native mock，不用 JS patch；
能整机 profile 随机，不逐字段乱随机。
```

### 1.2 裁剪准入规则：能 mock 才能裁

v2 裁剪采用以下准入规则：

```text
可以先裁剪后端实现，然后用 native/profile mock 代替表面行为；
如果某个检测点不能 mock、mock 后反射不自然、或无法证明与目标 profile 自洽，就暂时不要裁剪。
```

具体判断：

- 只影响后端能力、不影响 JS 表面形状的，可以优先裁。
- 会改变 `typeof`、属性存在性、descriptor、枚举顺序、`Function.prototype.toString` 的，必须先有 native mock 方案。
- 会改变 Akamai 高优先级检测点的，必须先有本地探针 baseline 和 mock 后对比。
- mock 只能在整机 profile 约束下进行，不能逐字段乱补。
- 如果 API 在目标 profile 中应该存在，但真实后端被裁掉，则 mock 层必须返回真实浏览器风格的空结果、权限拒绝或稳定错误，而不是让 API 消失。

裁剪决策表：

| 裁剪对象 | 可否裁剪 | 条件 |
|---|---|---|
| test/debug 运行时依赖 | 默认保留 | 当前仍需要调试、CDP、Tracing 和协议验证；runtime-only 版本可另开开关裁剪 |
| 图片解码 / 基础渲染 | 默认保留 | Google 搜索结果页会触发真实图片解码；此类能力不能靠 mock 替代 |
| WebNN / on-device model | 可以裁 | 目标 profile 不依赖该 API，或 Blink 表面可稳定 disabled |
| WebGPU / Dawn | 谨慎裁 | WebGL 不受影响，`navigator.gpu` 行为有 profile 定义 |
| WebRTC 后端 | 有条件裁 | `RTCPeerConnection` 表面、错误、ICE 行为可 mock |
| speech voices 后端 | 有条件裁 | `speechSynthesis.getVoices()` 可返回 profile voices |
| plugins/PDF 后端 | 有条件裁 | `PluginArray` / `MimeTypeArray` 可 native mock |
| navigator 属性 | 不直接裁 | 必须由 profile 控制 present/absent/stub |
| screen/window/time | 不直接裁 | 必须保持真实设备自洽 |

### 1.3 调试/CDP 保留规则

当前版本优先做 `debug-capable minimal`，不是极限 runtime-only 包。

以下能力默认保留：

- DevTools Protocol / CDP。
- DevTools 调试入口和内置 DevTools frontend。
- Tracing / debug 相关运行时依赖。
- content shell 现有 test support 中被调试、WebTest、协议验证间接依赖的部分。
- GPU fallback 相关库，除非确认目标 profile 和 Akamai 探针都不受影响。

原因：

```text
当前还需要用 CDP 和调试能力继续开发/验证 Akamai mock；
不能为了几十 MB 体积，把后续调试和协议验证工具链先砍掉。
```

因此，以下内容暂不作为默认裁剪项：

- `//services/device/public/cpp:test_support`
- `//base/test:test_trace_processor_bundle_data`
- `libtest_trace_processor.dylib`
- DevTools / Tracing 相关资源和协议目标

如果后续需要极限 runtime-only 版本，必须单独加 build/package 开关，例如：

```text
content_shell_keep_devtools_frontend=false
KEEP_DEBUG_SUPPORT=0
KEEP_GPU_FALLBACKS=0
```

并且需要单独验证：

- 右键 Inspect 预期不可用，或有外部 CDP client 替代。
- CDP 核心域是否仍可用。
- Tracing / Performance / Runtime / Page / Network 域是否符合预期。
- Akamai 探针没有因为 API 表面变化而退化。
- mock 层已经覆盖被裁能力。

### 2. 优先裁掉的对象

优先裁剪三类东西：

- 明显错误进入运行时的测试依赖。
- Chrome 产品层能力。
- MVP 不需要、但体积或依赖面很大的服务。

### 3. 每轮裁剪必须可验证

每一轮裁剪后至少验证：

```bash
buildtools/mac/gn gen out/ContentShell
autoninja -C out/ContentShell content_shell
open -n "output/content-shell-minimal/Content Shell.app" --args 'data:text/html,<html><body>ok</body></html>'
codesign --verify --verbose=6 "output/content-shell-minimal/Content Shell.app"
```

如果某项裁剪导致现代网站基础能力明显下降，应回退或改成 feature flag。

## 二、第一阶段：保留调试能力，先消除可安全裁剪项

### 目标 1：默认保留 `libtest_trace_processor.dylib`

当前结论：

```text
Content Shell Framework 依赖 @loader_path/Libraries/libtest_trace_processor.dylib
```

这一路径虽然看起来像 test 运行时依赖，但当前版本仍需要调试、CDP、Tracing 和协议验证能力。因此 v2 默认不移除它，打包脚本也默认保留：

```text
Contents/Frameworks/Content Shell Framework.framework/Versions/C/Libraries/libtest_trace_processor.dylib
```

仅当后续明确要构建极限 `runtime-only` 包时，才允许通过单独开关验证性移除：

```bash
KEEP_DEBUG_SUPPORT=0 scripts/package_content_shell_minimal.sh
```

runtime-only 裁剪动作：

1. 用 `otool -L` 确认 framework 的直接依赖。
2. 用 `gn desc out/ContentShell <target> deps --all` 追踪哪个 target 拉入 `test_trace_processor`。
3. 在 GN 层评估是否存在非 test 的 tracing/protocol 替代路径。
4. 重新链接 `Content Shell Framework`。
5. 额外验证 CDP attach、DevTools tracing、Akamai 检测 baseline。

预期收益：

- app 体积减少约 12M。
- runtime-only 包可以删除一个明显偏测试/trace 的运行时依赖。

风险：

- 如果 tracing 初始化路径误用了 test processor，可能影响 DevTools tracing 或内部 metrics。
- debug-capable 版本不能接受默认禁用高级 tracing 或影响基础 DevTools/CDP 连接。

验证：

```bash
otool -L "Content Shell.app/Contents/Frameworks/Content Shell Framework.framework/Versions/C/Content Shell Framework" | rg test_trace
```

debug-capable 版本期望有输出；runtime-only 版本在完成额外验证后才期望无输出。

### 目标 2：默认保留 fake geolocation 的 `test_support`

当前结论：

为了让 `content_shell` 启动稳定，并保留调试、WebTest/协议验证相关能力，当前默认保留：

```text
//services/device/public/cpp:test_support
```

后续如果要做 runtime-only 包，可以评估它是否拉入 gtest/gmock 和一批测试辅助文件；但在 debug-capable 主线中不把它作为默认裁剪对象。

runtime-only 裁剪动作：

1. 找到 `content/shell` 中 fake geolocation 所需的最小接口。
2. 新增一个只服务于 content shell 的极小 fake geolocation target。
3. 避免依赖 `test_support`。
4. 确认 GN deps 中 `googletest` / `gmock` 不再被 runtime-only target 拉入。
5. 额外验证 CDP、定位权限、Akamai 检测点、基础页面启动。

预期收益：

- 减少测试依赖面。
- 为后续源码闭包抽取降低复杂度。

风险：

- Geolocation API 行为可能变化。
- 需要保留网页请求定位权限时的稳定默认行为。

验证：

```bash
buildtools/mac/gn desc out/ContentShell //content/shell:content_shell deps --all | rg 'googletest|gmock|test_support'
```

期望只剩必要构建工具相关项，运行时链路不再依赖 fake test support。

## 三、第二阶段：继续移除大块非 MVP 服务

### 目标 3：WebNN / TFLite / LiteRT / Chrome ML

当前已通过 GN args 关闭：

```gn
webnn_use_tflite = false
webnn_use_litert = false
webnn_use_chrome_ml_api = false
build_with_model_execution = false
```

但 GN deps 里仍能看到：

```text
services/webnn
third_party/tflite
services/on_device_model
```

裁剪动作：

1. 追踪 `services/webnn` 被谁拉入。
2. 在 `content_shell_minimal_root` 下禁用 WebNN service registration。
3. Blink modules/AI/WebNN 入口改成 feature disabled 或空实现。
4. 确认 `third_party/tflite` 不再出现在 deps 目录闭包中。

预期收益：

- 可能减少数百 MB 源码闭包。
- 减少 ML runtime 相关编译复杂度。

风险：

- 网站使用 WebNN API 时不可用。
- MVP 采集场景通常可接受。
- Akamai 当前清单未把 WebNN 作为高优先级检测点，但删除 Blink 暴露面前仍需确认属性存在性是否变化。

### 目标 4：On-device translation / AI modules

当前已关闭：

```gn
enable_on_device_translation = false
use_on_device_model_service = false
```

但 Blink AI / translation 相关代码仍有残留依赖。

裁剪动作：

1. 在 Blink modules 中把 AI translation/language detector 相关 target 从 content shell 路径移除。
2. 禁止 `services/on_device_model` 注册到 utility service。
3. 清理 optimization guide 中与模型执行相关依赖。

预期收益：

- 减少 model service、language detection、optimization guide 依赖面。

风险：

- 网站相关实验性 AI API 不可用。
- 对常规网页采集影响低。

### 目标 5：Dawn / WebGPU / Vulkan / SwiftShader

当前 app 仍受 GPU 栈影响，依赖统计中较重：

```text
third_party/dawn
third_party/swiftshader
third_party/angle
third_party/vulkan-headers
third_party/vulkan-loader
```

现有 GN args 已关闭部分后端：

```gn
angle_enable_vulkan = false
dawn_use_swiftshader = false
dawn_enable_vulkan = false
```

裁剪动作：

1. 明确 MVP 是否需要 WebGPU。
2. 如果不需要，禁用 Blink WebGPU 入口和 Dawn service。
3. 保留 WebGL 所需的最小 ANGLE 路径。
4. 优先移除 Vulkan 和 SwiftShader 路径。
5. 不先裁掉全部 GPU/compositor，避免破坏有头一致性。
6. 如果 `navigator.gpu` 在目标 Chrome profile 中应存在，则先实现 profile 化的 native 表面行为，再裁 Dawn 后端；如果不能 mock，就暂缓裁 WebGPU。

预期收益：

- 源码闭包有机会减少 1G 以上。
- 运行时 app 也可能减少若干 dylib/resource。

风险：

- WebGPU 不可用。
- WebGL 指纹可能变化。
- 反爬场景下 WebGL 一致性很敏感，因此必须小步验证。
- Akamai 侧虽然重点不是 WebGPU，但 WebGL vendor/renderer、canvas 和 GPU 行为会影响更广泛指纹评分。

验证：

- WebGL 基础页面可运行。
- `navigator.gpu` 行为符合预期。
- 常见 WebGL 指纹脚本不崩溃。

## 四、第三阶段：裁 Chrome 产品层和组件残留

### 目标 6：Signin / Sync / Trusted Vault

当前已经做过一批裁剪，但需要继续收口。

裁剪动作：

1. 追踪 `components/signin`、`components/sync`、`trusted_vault` 的剩余依赖。
2. 对 content shell 路径下不需要的 identity manager、OAuth registry、sync protocol target 继续条件移除。
3. 如果某些 protocol proto 只是被公共 target 间接拉入，改成更窄的 public dependency。

预期收益：

- 减少 Chrome 账号体系依赖。
- 减少 proto/generated 文件。

风险：

- 某些网络请求或 storage 代码可能通过公共组件误用 signin buildflags。

### 目标 7：Enterprise / Policy / Safe Browsing

当前已关闭多项 enterprise args 和 `safe_browsing_mode = 0`。

裁剪动作：

1. 清理 `components/enterprise/**` 剩余 deps。
2. 清理 policy 注册路径。
3. 清理 safe browsing 相关资源和服务注册。

预期收益：

- 减少 Chrome 管理策略相关依赖。

风险：

- 某些 URL formatter、download、permission 代码可能通过公共组件间接拉入。

### 目标 8：Password manager / Autofill / Payments / Digital Goods

MVP 采集运行时不需要 Chrome 表单增强和支付产品功能。

裁剪动作：

1. 禁用 password manager 公共 target。
2. 禁用 autofill mojom 中 content shell 不需要的部分。
3. 禁用 payments/digital goods schema mojom。
4. 保留网页原生表单能力，不影响 DOM input。

预期收益：

- 减少 components 依赖面。

风险：

- 网站调用 Payment Request API 时行为变化。
- 普通表单输入不能受影响。

## 五、第四阶段：媒体和设备能力裁剪

### 目标 9：媒体编解码和 capture

当前已关闭：

```gn
media_use_ffmpeg = false
media_use_libvpx = false
media_use_symphonia = false
media_use_openh264 = false
enable_av1_decoder = false
```

仍需继续检查：

- `media/capture`
- `media/webrtc`
- `media/mojo`
- `media/audio`
- Apple video capture

裁剪动作：

1. MVP 不需要音视频采集时，移除 camera/microphone capture service。
2. WebRTC 如果采集场景不需要，继续裁掉 peer connection 相关实现。
3. 保留 HTMLMediaElement 的最低限度行为，避免页面探测直接异常。
4. 裁 WebRTC/capture 前，先确认 `RTCPeerConnection`、`navigator.mediaDevices`、permissions query 的 mock 行为。

预期收益：

- 减少 media 和 WebRTC 依赖。
- 降低 macOS 权限弹窗风险。

风险：

- 网站检测 WebRTC 指纹时行为变化。
- 反爬场景可能需要“存在但不可用”的一致性策略，而不是完全删除。
- Akamai 清单明确检查 `RTCPeerConnection`、`navigator.mediaDevices` 和相关能力位。裁剪 media/WebRTC 前必须先定义 profile mock 行为。

### 目标 10：Bluetooth / Gamepad / VR / MIDI / Serial / HID

这些设备能力不是 MVP 必需。

裁剪动作：

1. 禁用 VR service。
2. 禁用 Bluetooth service。
3. 禁用 Gamepad、MIDI、Serial、HID 非必要 service。
4. 保证对应 Web API 的错误表现稳定，而不是崩溃或未定义。
5. 如果 Akamai bitmap 中目标 profile 要求某属性存在，则只裁后端，不裁 JS 属性表面。

预期收益：

- 减少 device/services 依赖面。

风险：

- 某些指纹脚本会探测这些 API。
- 应统一返回“不可用/权限拒绝/无设备”，而不是对象消失得过于异常。
- Akamai 会读取 `navigator.bluetooth`、`getGamepads`、`permissions` 等存在性 bitmap。是否存在必须由目标设备 profile 控制，不能由编译时随机缺失决定。

## 六、第五阶段：WebUI、资源和 generated 文件裁剪

### 目标 11：Content internal WebUI resources

当前已经对部分 WebUI resources 做过裁剪。

裁剪动作：

1. 列出最终 app 中所有 `.pak`、resources、mojo generated 文件。
2. 保留 DevTools 必需资源。
3. 删除 NTP、settings、Chrome product WebUI、composebox 等资源。
4. `optimize_webui = false` 的影响需要重新评估，避免反而保留更多调试资源。

预期收益：

- 减少 pak/resource 体积。
- 降低 Chrome 产品层资源耦合。

风险：

- DevTools 或 content shell 内置页面可能打不开。

### 目标 12：Metrics / UKM / Variations / Private Metrics

MVP 不需要完整 Chrome telemetry。

裁剪动作：

1. 继续清理 `components/metrics`、`components/ukm`、`components/variations` 的运行时注册。
2. 保留必要的 base feature list 和 field trial 框架。
3. 避免再出现 FieldTrial 初始化崩溃。

预期收益：

- 减少 telemetry 相关依赖。

风险：

- Chromium 很多 feature gate 依赖 variations/field trial 框架，不能粗暴删除。
- FieldTrial/FeatureList 初始化异常会影响页面启动和检测脚本执行，必须保留最小稳定框架。

## 六点五、Akamai 回归验证

每一轮裁剪后增加 Akamai 相关 smoke test。即使暂时没有真实目标站，也要至少跑本地检测脚本或探针页，覆盖：

### 静态环境探针

检查：

- `navigator.webdriver`
- Selenium/Phantom 全局变量。
- `window.chrome` 结构。
- `navigator.plugins` / `mimeTypes`。
- navigator 属性存在性 bitmap。
- screen/window 几何。
- language/timezone/platform/productSub/maxTouchPoints。

### 原生性和 descriptor 探针

检查：

- `Function.prototype.toString.call(navigator.plugins.item)`
- `Object.getOwnPropertyDescriptor(Navigator.prototype, "...")`
- `Object.keys(window.chrome || {})`
- `Object.prototype.toString.call(navigator.plugins)`
- `Symbol.toStringTag`

### 媒体和通信探针

检查：

- `typeof RTCPeerConnection`
- `navigator.mediaDevices`
- `speechSynthesis.getVoices()`
- permissions query 的返回结构。

### 时间探针

检查：

- `Date.now()` 与 `performance.now()` 单调关系。
- timezone 与 locale 是否匹配 profile。
- 页面启动后生成 payload 的时间窗口是否真实。

### 验收要求

裁剪后的 runtime 至少满足：

```text
Akamai 检测清单中的最高优先级自动化标记全部 absent；
目标 profile 的 navigator/window/screen 属性存在性稳定；
函数反射不暴露 JS hook；
没有因为裁剪导致 API 直接 crash 或 undefined 异常；
```

如果某项裁剪让 Akamai 探针结果变差，则该裁剪必须回退，或先实现 profile/mock 替代层。

## 七、打包提取流程裁剪

源码裁剪之外，还要把 packaging 从手工步骤变成可重复流程。

### 目标 13：依赖闭包式提取 app

新增脚本目标：

```text
scripts/package_content_shell_minimal.sh
```

脚本职责：

1. 从 `out/ContentShell/Content Shell.app` 创建 staging app。
2. 用 `otool -L` 递归收集 `@loader_path` / `@executable_path` dylib。
3. 复制必要 `Resources`、`Libraries`、`Helpers`。
4. 编译并注入 `content_shell_app_launcher.c`。
5. ad-hoc codesign。
6. 运行 smoke test。
7. 验证运行后 app bundle 没有新增文件，签名仍有效。

预期收益：

- 防止再次漏 dylib。
- 每次源码裁剪后都能复现 output app。

## 八、建议 patch 分组

后续维护时建议按以下 patch 组推进：

```text
patches/chromium/e0488508e6-v2/
  0001-build-content-shell-minimal-flag.patch
  0010-drop-test-trace-processor.patch
  0020-replace-fake-geolocation-test-support.patch
  0030-disable-webnn-tflite-on-device-model.patch
  0040-disable-dawn-webgpu-vulkan-swiftshader.patch
  0050-trim-signin-sync-enterprise-policy.patch
  0060-trim-media-capture-webrtc-device-services.patch
  0070-trim-webui-metrics-variations-resources.patch
  0080-macos-package-launcher-and-signing.patch
```

每个 patch 都应该满足：

- 可以单独说明目的。
- 可以从干净 commit 应用。
- 应用后可编译，或明确依赖前序 patch。
- 有对应验证命令。

## 九、优先级排序

第一优先级：

1. packaging 脚本化和可重复打包。
2. 启动配置/profile mock 框架。
3. Akamai 检测 baseline 与回归探针。
4. 保留 CDP/DevTools/Tracing/test_support 的 debug-capable 最小包。

第二优先级：

1. WebNN / TFLite / on-device model。
2. Signin / Sync / Enterprise / Policy。
3. 不影响 Akamai 可见面的资源和服务裁剪。

第三优先级：

1. WebGPU / Vulkan / SwiftShader runtime-only 可选包。
2. Media capture / WebRTC。
3. device services。
4. WebUI resources。
5. Metrics / UKM / Variations。

## 十、成功标准

v2 阶段成功标准：

- `content_shell` 从固定 commit + patch stack 可重复编译。
- `output/content-shell-minimal/Content Shell.app` 可重复打包。
- app 可通过 `open -n` 启动。
- 运行后 `codesign --verify` 仍通过。
- debug-capable 默认保留 `libtest_trace_processor.dylib`、`test_support`、CDP、DevTools、Tracing。
- runtime-only 包可以另开开关裁剪 debug/test 依赖，但必须额外通过 CDP/Tracing/Akamai 回归验证。
- GN deps target 数从约 6951 明显下降。
- 源码目录级闭包从约 10-12G 开始下降。
- 提取 app 小于当前约 205M。

最终判断标准不是单纯体积，而是：

```text
像真实 Chromium 一样跑现代网页，同时不携带 Chrome 产品层和测试运行时。
```
