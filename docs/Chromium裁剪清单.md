# Chromium 裁剪清单

## 1. 保留模块

必须保留：

- Blink
- V8
- Network Service
- BoringSSL
- Skia
- ANGLE/WebGL
- ICU
- Storage
- DevTools Protocol
- Cookie
- LocalStorage
- IndexedDB
- Fetch/XHR
- Service Worker：建议 MVP 先保留
- Web Worker：建议 MVP 先保留

## 2. 优先禁用模块

可优先禁用：

- extensions
- sync
- signin
- bookmarks
- password manager
- autofill
- translate
- safe browsing
- printing
- pdf
- media router
- enterprise policy
- crash reporter
- updater
- accessibility：MVP 可以尝试关闭，但有些检测可能涉及

## 3. GN args 示例

```gn
is_debug = false
is_component_build = false
symbol_level = 0
blink_symbol_level = 0

enable_nacl = false
enable_printing = false
enable_basic_printing = false
enable_pdf = false
enable_plugins = false
enable_extensions = false
enable_web_speech = false
enable_webrtc = false
use_cups = false
use_kerberos = false

use_ozone = true
use_x11 = false
use_gtk = false
```

注意：不同 Chromium 版本支持的 GN 参数会变，需要按实际版本调整。

## 4. 不要过早删源码

先通过 GN 参数关闭功能，再用二进制体积和运行依赖分析决定是否删除源码目录。

## 5. 最小化目标

第一阶段不是追求源码最少，而是追求：

- 可编译
- 可运行
- 可采集
- 有头/无头一致
- 可配置 Profile

之后再优化体积和编译时间。

