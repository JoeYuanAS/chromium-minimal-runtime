# v2 变更记录 001：debug-capable 打包脚本化

本轮目标：

```text
保留调试、CDP、Tracing 和 test support 能力；
先把 output/content-shell-minimal 的生成流程脚本化。
```

## 一、策略修正

用户明确要求：

```text
测试模块不能改掉，还需要调试和 CDP 协议使用。
```

因此，本版本不再把 test/debug 相关模块作为默认裁剪对象。当前输出定位为：

```text
debug-capable minimal
```

不是：

```text
runtime-only minimal
```

默认保留：

- `//base/test:test_trace_processor_bundle_data`
- `//services/device/public/cpp:test_support`
- `libtest_trace_processor.dylib`
- DevTools / CDP / Tracing 相关支持
- GPU fallback 相关库

## 二、本轮已改内容

### 1. 新增 minimal app 打包脚本

新增脚本：

```text
/Users/zy.yuan/Develop/browser-runtime-projects/chromium-minimal-runtime/scripts/package_content_shell_minimal.sh
```

脚本做的事情：

1. 从 Chromium 编译产物复制 `Content Shell.app`。
2. 把真实二进制改名为：

```text
Contents/MacOS/Content Shell.bin
```

3. 编译并注入 Mach-O launcher：

```text
Contents/MacOS/Content Shell
```

4. 默认保留调试支持：

```text
KEEP_DEBUG_SUPPORT=1
KEEP_GPU_FALLBACKS=1
```

5. 对 framework 和 dylib 执行 `strip -x`。
6. ad-hoc codesign。
7. 验证签名。

可选 runtime-only 开关：

```bash
KEEP_DEBUG_SUPPORT=0 KEEP_GPU_FALLBACKS=0 scripts/package_content_shell_minimal.sh
```

但该模式不作为当前默认版本，必须额外验证 CDP、Tracing 和 Akamai 探针。

### 2. 新增启动 smoke test 脚本

新增脚本：

```text
/Users/zy.yuan/Develop/browser-runtime-projects/chromium-minimal-runtime/scripts/smoke_content_shell_app.sh
```

验证内容：

- `open -n Content Shell.app` 能启动。
- 进程能保持运行。
- 日志写到 `/tmp/content_shell.log`，不污染 app bundle。
- 运行后 `codesign --verify` 仍通过。

## 三、本轮验证结果

### 编译验证

执行：

```bash
cd /Users/zy.yuan/Develop/browser-runtime-projects/chromium-workspace/src
buildtools/mac/gn gen out/ContentShell
autoninja -C out/ContentShell content_shell
```

结果：

```text
gn gen 成功
autoninja 成功
```

### 文件验证

当前 output app 中保留：

```text
Contents/Frameworks/Content Shell Framework.framework/Versions/C/Libraries/libEGL.dylib
Contents/Frameworks/Content Shell Framework.framework/Versions/C/Libraries/libtest_trace_processor.dylib
Contents/Frameworks/Content Shell Framework.framework/Versions/C/Libraries/libvulkan.dylib
Contents/Frameworks/Content Shell Framework.framework/Versions/C/Libraries/libvk_swiftshader.dylib
Contents/Frameworks/Content Shell Framework.framework/Versions/C/Libraries/vk_swiftshader_icd.json
Contents/Frameworks/Content Shell Framework.framework/Versions/C/Libraries/libGLESv2.dylib
```

这些文件默认保留，用于调试、Tracing、GPU fallback 和协议验证。

### 体积

当前 output app：

```text
191M output/content-shell-minimal/Content Shell.app
```

对比：

```text
205M 上一版可启动提取 app
298M Chromium 原始编译 app
```

### 启动验证

执行：

```bash
scripts/smoke_content_shell_app.sh
```

结果：

```text
open 启动成功
Content Shell.bin --log-file=/tmp/content_shell.log ...
codesign valid on disk
smoke ok
```

## 四、本轮没有裁剪的内容

按“能 mock 才能裁”和“调试/CDP 默认保留”的规则，本轮没有裁剪：

- `navigator.plugins` / `navigator.mimeTypes`
- `navigator` 属性存在性 bitmap
- `window.chrome`
- `RTCPeerConnection`
- `navigator.mediaDevices`
- `speechSynthesis.getVoices()`
- permissions query
- screen/window/time
- WebGL vendor/renderer
- Canvas/Audio
- UA / Accept-Language / TLS / HTTP2
- DevTools / CDP
- Tracing / debug support
- `//services/device/public/cpp:test_support`
- `libtest_trace_processor.dylib`

这些能力后续必须先有 native/profile mock 或明确 profile 行为，再裁后端实现。

## 五、下一步建议

### 方向 A：先做 profile/mock 基础设施

在动 WebRTC、speech、plugins、navigator bitmap 前，先实现：

- 启动读取 `runtime.yaml`
- 选择整机 profile
- profile 控制 navigator 基础字段
- profile 控制 `navigator.plugins` / `mimeTypes`
- profile 控制属性 present/absent/stub
- Akamai 本地探针

等 mock 层具备后，再裁对应后端。

### 方向 B：单独规划 runtime-only 包

如果后续要极限体积版本，再单独做：

```text
runtime-only package
```

该版本可以尝试关闭：

- `KEEP_DEBUG_SUPPORT`
- `KEEP_GPU_FALLBACKS`
- 部分 test support

但不能影响当前 debug-capable 版本。

