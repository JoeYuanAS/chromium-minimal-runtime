# 启动配置驱动的指纹 Mock 计划

关联文档：

```text
/Users/zy.yuan/Develop/browser-runtime-projects/chromium-minimal-runtime/docs/Akamai 检测.md
/Users/zy.yuan/Develop/browser-runtime-projects/chromium-minimal-runtime/docs/指纹配置.md
```

目标：启动 `Content Shell` 时读取配置文件，按整机 profile 控制 JS 层、渲染层、网络层和时间层暴露的信息。重点不是“逐字段随机”，而是从配置里的真实设备候选集中选择一个自洽 profile，并在 native 层暴露一致行为。

## 一、核心原则

### 1. 整机 profile 优先

不能这样做：

```text
UA 随机一个；
screen 随机一个；
plugins 随机一个；
timezone 随机一个；
WebGL 随机一个。
```

这会产生不存在的设备组合。

应该这样做：

```text
先选择一个完整 profile；
所有字段从这个 profile 派生；
同一个 profile/session 内保持稳定；
需要随机时只在 profile 候选集之间随机。
```

### 2. native mock 优先

Akamai 会检查：

- `Function.prototype.toString`
- `Object.keys`
- `getOwnPropertyDescriptor`
- `hasOwnProperty`
- `Symbol.toStringTag`

因此不建议用页面 JS 注入来 patch 高敏感 API。优先在 Chromium/Blink native 层改：

- Navigator 相关 IDL / C++ getter。
- PluginArray / MimeTypeArray。
- Screen / Window geometry。
- Permissions / MediaDevices / SpeechSynthesis。
- WebGL getParameter。
- Canvas / Audio 稳定扰动。
- Network headers / TLS / HTTP2。

### 3. profile 稳定随机

随机必须可控：

- `profile_selection = fixed`：固定使用指定 profile。
- `profile_selection = random_per_launch`：每次启动随机一个 profile。
- `profile_selection = random_per_profile`：同一个 data_dir 稳定随机。
- `profile_selection = random_per_origin`：同一个 origin 稳定随机，风险较高，后期再做。

建议 MVP 先做：

```text
fixed
random_per_profile
```

## 二、启动配置入口

现有配置：

```text
config/runtime.yaml
config/mac_chrome_profile.json
```

建议扩展启动参数：

```bash
Content Shell \
  --runtime-config=/path/to/runtime.yaml \
  --fingerprint-profile=/path/to/profile.json \
  --fingerprint-seed=profile_001
```

也可以只传：

```bash
Content Shell --runtime-config=/path/to/runtime.yaml
```

由 `runtime.yaml` 指向 profile 池。

## 三、建议配置结构

### runtime.yaml

```yaml
runtime:
  headless: false
  data_dir: ./data/profile_001
  proxy: ""
  viewport:
    width: 1440
    height: 900

fingerprint:
  enabled: true
  selection: random_per_profile
  seed: profile_001
  profile_pool:
    - ./config/profiles/mac_chrome_137_m2.json
    - ./config/profiles/mac_chrome_137_intel.json
    - ./config/profiles/ios_safari_17_iphone.json
  akamai_compat:
    enabled: true
    strict_property_presence: true
    native_reflection_safe: true
```

### profile.json

```json
{
  "name": "mac_chrome_137_m2",
  "browser": {
    "brand": "Chrome",
    "major": 137,
    "userAgent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
    "userAgentData": {
      "brands": [
        {"brand": "Google Chrome", "version": "137"},
        {"brand": "Chromium", "version": "137"},
        {"brand": "Not/A)Brand", "version": "24"}
      ],
      "mobile": false,
      "platform": "macOS"
    }
  },
  "navigator": {
    "platform": "MacIntel",
    "product": "Gecko",
    "productSub": "20030107",
    "vendor": "Google Inc.",
    "languages": ["en-US", "en"],
    "hardwareConcurrency": 8,
    "deviceMemory": 8,
    "maxTouchPoints": 0,
    "webdriver": false,
    "properties": {
      "credentials": "present",
      "bluetooth": "present",
      "getGamepads": "present",
      "hardwareConcurrency": "present",
      "mediaDevices": "present",
      "permissions": "present",
      "serviceWorker": "present",
      "sendBeacon": "present"
    }
  },
  "plugins": {
    "mode": "choose",
    "choices": [
      {
        "weight": 70,
        "plugins": [
          {
            "name": "PDF Viewer",
            "filename": "internal-pdf-viewer",
            "description": "Portable Document Format",
            "mimeTypes": [
              {
                "type": "application/pdf",
                "suffixes": "pdf",
                "description": "Portable Document Format"
              }
            ]
          }
        ]
      },
      {
        "weight": 30,
        "plugins": []
      }
    ]
  },
  "chrome_object": {
    "mode": "chrome",
    "runtime": {
      "connect": "native_stub",
      "sendMessage": "native_stub"
    },
    "webstore": "absent"
  },
  "screen": {
    "width": 1440,
    "height": 900,
    "availWidth": 1440,
    "availHeight": 875,
    "deviceScaleFactor": 2,
    "colorDepth": 24,
    "pixelDepth": 24
  },
  "timezone": "Asia/Singapore",
  "intl": {
    "locale": "en-US"
  },
  "webgl": {
    "vendor": "Apple Inc.",
    "renderer": "Apple M2"
  },
  "canvas": {
    "mode": "stable_noise",
    "seed": "profile"
  },
  "audio": {
    "mode": "stable_noise",
    "seed": "profile"
  },
  "media": {
    "rtc": "present_no_local_ip_leak",
    "mediaDevices": "present_empty_devices",
    "speechSynthesis": {
      "mode": "profile_voices",
      "voices": [
        {
          "name": "Samantha",
          "lang": "en-US",
          "localService": true,
          "default": true
        }
      ]
    }
  },
  "permissions": {
    "notifications": "prompt",
    "geolocation": "prompt",
    "camera": "prompt",
    "microphone": "prompt"
  },
  "time": {
    "mode": "real_anchor",
    "virtualize_delays": false
  },
  "network": {
    "acceptLanguage": "en-US,en;q=0.9",
    "tls": "chrome_like",
    "http2": "chrome_like"
  }
}
```

## 四、Akamai 检测点映射

### 1. 自动化标记

配置项：

```json
{
  "navigator": {
    "webdriver": false
  }
}
```

实现要求：

- `navigator.webdriver` 返回 `false` 或按目标浏览器表现为 `undefined`。
- 不注入 `window.webdriver`。
- 不注入 Selenium/Phantom/CDP automation 全局符号。

### 2. `window.chrome`

配置项：

```json
{
  "chrome_object": {
    "mode": "chrome"
  }
}
```

模式：

- `absent`：Safari/iOS profile 使用。
- `chrome`：Chrome profile 使用，暴露合理的 `chrome.runtime` 形状。
- `minimal_chromium`：只暴露 Chromium 真机一致的最小对象。

实现要求：

- 对象属性枚举顺序稳定。
- `connect` / `sendMessage` 是 native function 形态。
- descriptor 与目标 Chrome 一致。

### 3. `navigator.plugins` / `navigator.mimeTypes`

配置项：

```json
{
  "plugins": {
    "mode": "choose",
    "choices": []
  }
}
```

模式：

- `fixed`：固定插件列表。
- `choose`：从候选列表按权重选择一个插件组合。
- `empty`：移动端 Safari 等无插件 profile。

实现要求：

- 返回真实 `PluginArray`，不是普通 JS array。
- 支持 `length`、数字索引、name 索引、`item()`、`namedItem()`、`refresh()`。
- `MimeTypeArray` 与 plugin 反向引用一致。
- 枚举属性、descriptor、`Object.prototype.toString` 与目标浏览器一致。
- 同一次启动内结果稳定，不允许每次访问随机变化。

### 4. navigator 属性存在性 bitmap

配置项：

```json
{
  "navigator": {
    "properties": {
      "credentials": "present",
      "bluetooth": "present",
      "getGamepads": "present",
      "mediaDevices": "present"
    }
  }
}
```

取值：

- `present`
- `absent`
- `present_stub`
- `present_permission_denied`

实现要求：

- `typeof navigator.xxx` 与 profile 一致。
- 如果存在但不可用，应返回真实浏览器风格的 Promise rejection 或空结果。
- 不要出现 C++ 空指针、JS undefined 行为混乱。

### 5. screen/window 几何

配置项：

```json
{
  "screen": {
    "width": 1440,
    "height": 900,
    "availWidth": 1440,
    "availHeight": 875,
    "deviceScaleFactor": 2
  }
}
```

实现要求：

- `screen`、`window.innerWidth`、`outerWidth`、viewport、deviceScaleFactor 自洽。
- 移动端 profile 要同步 touch、maxTouchPoints、orientation。
- 桌面端不要误暴露 iOS-only 字段。

### 6. RTC / mediaDevices / speechSynthesis

配置项：

```json
{
  "media": {
    "rtc": "present_no_local_ip_leak",
    "mediaDevices": "present_empty_devices",
    "speechSynthesis": {
      "mode": "profile_voices"
    }
  }
}
```

实现要求：

- Akamai 会检查 `RTCPeerConnection` 是否为 function。
- `navigator.mediaDevices` 的存在性与 UA/profile 一致。
- `speechSynthesis.getVoices()` 不应长期返回异常空值，除非目标真机如此。
- 返回结构必须稳定，可由 profile 指定 voices。

### 7. 时间和反重放

配置项：

```json
{
  "time": {
    "mode": "real_anchor",
    "virtualize_delays": false
  }
}
```

实现要求：

- `Date.now()` 锚定真实当前时间。
- `performance.now()` 单调递增。
- 不要为了加速执行让 Akamai payload 时间窗失真。
- 如果后续做虚拟时间，只虚拟 wait/sleep，不虚拟 sensor 关键时间戳。

## 五、实现分层

### Layer 1：配置加载

目标：

- 启动早期读取 `runtime.yaml`。
- 解析 profile pool。
- 按 selection 策略选定一个 profile。
- 将 profile 放入 browser process 可访问的 `RuntimeFingerprintProfile`。

建议位置：

- `content/shell/app/shell_main_delegate.cc`
- `content/shell/browser/shell_browser_context.cc`
- 本项目可先维护配置结构和解析器，后续以 patch 形式注入 Chromium。

### Layer 2：浏览器进程策略

负责：

- UA / Accept-Language。
- permission 默认行为。
- media device 策略。
- timezone/locale 初始化。
- DevTools 暴露时不污染页面环境。

### Layer 3：Blink renderer 暴露面

负责：

- `navigator.*`
- `window.chrome`
- `screen`
- `plugins` / `mimeTypes`
- `speechSynthesis`
- `permissions`
- `mediaDevices`
- `RTC`

高敏感点必须在 native binding 层实现，避免 JS patch。

### Layer 4：渲染和硬件指纹

负责：

- WebGL vendor/renderer。
- Canvas stable noise。
- Audio stable noise。
- devicePixelRatio。

### Layer 5：网络层

负责：

- User-Agent header。
- Accept-Language。
- Header 顺序。
- TLS/HTTP2 行为。

这一层不一定在第一版全部完成，但配置 schema 要预留。

## 六、开发阶段计划

### 阶段 A：配置 schema 和 profile 选择

交付：

- `runtime.yaml` 支持 `fingerprint` 节。
- profile pool 支持 fixed / random_per_profile。
- 选中 profile 后输出调试日志。

验证：

- 同一个 data_dir 多次启动选择同一个 profile。
- 改 seed 后选择可变化。

### 阶段 B：navigator 基础字段

交付：

- userAgent。
- platform。
- product/productSub/vendor。
- languages/language。
- hardwareConcurrency。
- maxTouchPoints。
- webdriver。

验证：

- Akamai 静态探针字段自洽。
- `navigator.webdriver` 不暴露自动化。

### 阶段 C：plugins/mimeTypes

交付：

- `PluginArray` / `MimeTypeArray` native profile mock。
- 支持从配置 choices 中按权重选择。
- 同一 session 稳定。

验证：

- `navigator.plugins.length`。
- `navigator.plugins[0]`。
- `navigator.plugins.item(0)`。
- `navigator.plugins.namedItem(name)`。
- `Object.keys(navigator.plugins)`。
- `Object.prototype.toString.call(navigator.plugins)`。
- descriptor 对齐目标真机。

### 阶段 D：window.chrome 和属性存在性 bitmap

交付：

- Chrome profile 暴露 `window.chrome`。
- Safari/iOS profile 不暴露。
- navigator properties 按 profile present/absent/stub。

验证：

- Akamai bitmap 对齐 profile。
- 函数 `toString()` 不暴露 hook。

### 阶段 E：screen/timezone/Intl/time

交付：

- screen/window 几何自洽。
- timezone/Intl locale。
- real_anchor 时间模式。

验证：

- `Intl.DateTimeFormat().resolvedOptions().timeZone`。
- Date/performance 单调和真实窗口。

### 阶段 F：media/RTC/speech/permissions

交付：

- `RTCPeerConnection` profile 行为。
- `mediaDevices.enumerateDevices()` profile 行为。
- `speechSynthesis.getVoices()` profile voices。
- permissions query 统一返回。

验证：

- Akamai 媒体能力探针。
- 不触发 macOS 权限弹窗。

### 阶段 G：WebGL/Canvas/Audio

交付：

- WebGL vendor/renderer。
- Canvas stable noise。
- Audio stable noise。

验证：

- 同一 profile 输出稳定。
- 不同 profile 可差异。
- 有头/无头一致。

### 阶段 H：网络层

交付：

- UA header。
- Accept-Language。
- TLS/HTTP2 chrome_like 预留或接入。

验证：

- JS UA 与 HTTP UA 一致。
- Accept-Language 与 navigator.languages 一致。

## 七、Akamai 回归用例

新增本地探针页面或脚本，输出：

```json
{
  "automation": {
    "navigator.webdriver": false,
    "window.webdriver": "undefined",
    "seleniumGlobals": []
  },
  "navigator": {
    "ua": "...",
    "platform": "...",
    "pluginsLength": 1,
    "language": "en-US",
    "propertyBitmap": "..."
  },
  "chrome": {
    "exists": true,
    "keys": [],
    "runtimeConnectType": "function"
  },
  "screen": {
    "width": 1440,
    "height": 900,
    "dpr": 2
  },
  "reflection": {
    "nativeFunctionsOk": true,
    "descriptorsOk": true
  },
  "media": {
    "rtc": "function",
    "mediaDevices": "object",
    "voicesLength": 1
  },
  "time": {
    "realAnchor": true,
    "monotonic": true
  }
}
```

每次裁剪后对比 baseline。如果 mock 层还没实现，裁剪计划中对应 API 不允许直接删除。

## 八、与裁剪计划的关系

裁剪和 mock 的顺序应是：

```text
先定义 profile 表面行为；
再裁掉后端实现；
最后用 Akamai 探针确认表面行为没有退化。
```

更准确地说，v2 的工作模式允许“先裁剪后端，再用 mock 代替”，但必须满足一个硬条件：

```text
能 mock 的才裁；
不能 mock 的先保留；
mock 后不自然的也先保留。
```

这里的“能 mock”不是指能用 JS 临时 patch 出一个值，而是指：

- `typeof`、属性存在性、descriptor、枚举顺序稳定。
- `Function.prototype.toString` 不暴露 hook。
- `Object.prototype.toString` / `Symbol.toStringTag` 与目标浏览器一致。
- Promise resolve/reject、错误类型、权限状态像真实浏览器。
- 同一个 profile/session 内结果稳定。
- 与 UA、platform、screen、plugins、media、timezone、network 全局自洽。

例如：

- 裁 WebRTC 前，先确定 `RTCPeerConnection` 是否仍存在、返回什么错误、是否泄漏本地 IP。
- 裁 speech 前，先确定 `speechSynthesis.getVoices()` 返回 profile voices 还是目标真机空列表。
- 裁 plugins/PDF 前，先确定 `navigator.plugins` 是否应该有 PDF Viewer。
- 裁 Bluetooth/Gamepad 前，先确定对应 navigator 属性是 absent 还是 present stub。

不能先裁的例子：

- 还没有 native `PluginArray` mock 时，不要因为禁用 PDF 就让 Chrome profile 的 `navigator.plugins` 形状异常。
- 还没有 RTC profile mock 时，不要把 `RTCPeerConnection` 直接裁成 undefined。
- 还没有 speech voices mock 时，不要让目标 macOS/iOS profile 的 `speechSynthesis.getVoices()` 永久异常空。
- 还没有属性存在性 bitmap 控制时，不要随意裁 `navigator.bluetooth`、`getGamepads`、`mediaDevices`、`permissions` 等会被 Akamai 枚举的属性。

## 九、成功标准

第一版成功标准：

- 启动时可以指定 `runtime.yaml`。
- 可以从 profile pool 选择一个 profile。
- `navigator.plugins` 可由配置固定或按权重随机选择。
- `navigator` 基础字段与 screen/timezone/language 自洽。
- 自动化标记全部 absent/false。
- 函数原生性和 descriptor 不暴露 JS hook。
- Akamai 检测清单中的静态高优先级项可以本地探针通过。

第二版成功标准：

- media/RTC/speech/permissions profile 化。
- WebGL/Canvas/Audio 稳定扰动 profile 化。
- 网络 UA/Accept-Language/TLS/HTTP2 与 JS profile 对齐。
- 裁剪 WebNN/WebGPU/media/device services 后，Akamai 探针结果不退化。
