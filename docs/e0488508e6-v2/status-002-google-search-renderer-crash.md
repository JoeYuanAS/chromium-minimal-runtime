# v2 变更记录 002：修复 Google 搜索后 Renderer 白屏

日期：2026-06-17

## 背景

当前 `output/content-shell-minimal/Content Shell.app` 可以启动，但用户反馈：

- 检测页面打不开。
- Google 首页输入搜索后白屏。

本次先停止继续裁剪，按稳定性回归处理。

## 复现结论

使用干净 profile 和 CDP 复现：

```bash
output/content-shell-minimal/Content\ Shell.app/Contents/MacOS/Content\ Shell.bin \
  --user-data-dir=/tmp/content-shell-google-profile \
  --remote-debugging-port=9228 \
  --enable-logging=stderr \
  --v=1 \
  'https://www.google.com'
```

通过 CDP 设置 `textarea[name=q]` 并提交表单后，旧版本会收到：

```text
Inspector.targetCrashed
```

系统崩溃报告显示 `Content Shell Helper (Renderer)` 发生 `SIGABRT`。

## 根因

这不是单纯打包脚本问题。对比结果：

- 打包后的最小 app 会崩。
- `/chromium-workspace/src/out/ContentShell/Content Shell.app` 原始编译产物也会崩。

因此问题在当前源码/编译配置组合，而不是 `.app` 提取过程本身。

直接从终端启动未 strip 的原始二进制后，拿到可读栈：

```text
FATAL: third_party/blink/renderer/platform/image-decoders/skia/skia_image_decoder_base.cc:46
NOTREACHED hit.

blink::SkiaImageDecoderBase::Decode
blink::ImageDecoder::FrameCount
blink::DeferredImageDecoder::PrepareLazyDecodedFrames
blink::BitmapImage::SetData
blink::ImageResourceContent::UpdateImage
```

修复第一个崩溃后，又暴露第二个崩溃：

```text
FATAL: third_party/blink/renderer/platform/wtf/vector.h:1533
Check failed: i < size() (4294967295 vs. 1).

blink::SkiaImageDecoderBase::Decode
cc::SoftwareImageDecodeCache::DecodeImageInTask
```

综合判断：

- Google 搜索结果页加载真实图片资源时触发 Skia image decoder 路径。
- Skia 返回了 Blink 没有防御的异常动画帧信息：
  - 未知 `SkCodecAnimation::Blend`。
  - 非法 `fRequiredFrame`，例如第 0 帧依赖第 0 帧，导致 `dependent_index - 1` 下溢为 `4294967295`。
- Blink 原逻辑把这些“不应发生”的状态用 `NOTREACHED`/CHECK 放大成 renderer abort。

## 已改源码

文件：

```text
/Users/zy.yuan/Develop/browser-runtime-projects/chromium-workspace/src/third_party/blink/renderer/platform/image-decoders/skia/skia_image_decoder_base.cc
```

改动：

1. `ConvertAlphaBlendSource()` 遇到未知 `SkCodecAnimation::Blend` 时，不再 `NOTREACHED()` 终止 renderer，而是记录 `DLOG(ERROR)` 并按 `SrcOver` 处理。
2. `InitializeNewFrame()` 遇到非法 `fRequiredFrame` 时，把该帧当作独立帧处理，避免 self/future dependency。
3. `GetViableReferenceFrameIndex()` 增加防御：`kNotFound` 或 `>= dependent_index` 的 required frame 直接返回 `kNotFound`，不进入下溢循环。

本次没有裁剪 test/CDP/DevTools/Tracing 模块。

## 编译与打包

编译：

```bash
cd /Users/zy.yuan/Develop/browser-runtime-projects/chromium-workspace/src
PATH='/Users/zy.yuan/Develop/browser-runtime-projects/chromium-workspace/depot_tools/python-bin:/Users/zy.yuan/Develop/browser-runtime-projects/chromium-workspace/depot_tools:'"$PATH" \
  autoninja -C out/ContentShell content_shell
```

结果：

```text
ninja: Entering directory `out/ContentShell'
[1/8] CXX ... skia_image_decoder_base.o
[8/8] COPY_BUNDLE_DATA 'Content Shell Framework.framework' ...
```

打包：

```bash
cd /Users/zy.yuan/Develop/browser-runtime-projects/chromium-minimal-runtime
CHROMIUM_SRC='/Users/zy.yuan/Develop/browser-runtime-projects/chromium-workspace/src' \
BUILD_DIR='out/ContentShell' \
  scripts/package_content_shell_minimal.sh
```

结果：

```text
191M output/content-shell-minimal/Content Shell.app
codesign valid on disk
```

## 验证结果

Google 搜索自动化验证通过：

```text
page before:
  title: Google
  url: https://www.google.com.hk/

submit:
  ok: true

state after:
  title: content shell test - Google 搜索
  ready: complete
  text: 搜索结果 ...

crashed: false
exceptions: 0
```

日志检查：

```bash
rg -n 'FATAL|NOTREACHED|Unexpected SkCodec|targetCrashed' /tmp/cs-fixed2.log
```

结果：无输出。

基础 smoke：

```bash
scripts/smoke_content_shell_app.sh
```

结果：

```text
smoke ok
```

签名验证：

```bash
codesign --verify --verbose=2 output/content-shell-minimal/Content\ Shell.app
```

结果：

```text
valid on disk
satisfies its Designated Requirement
```

## 后续规则

图片解码属于真实网站基础能力，不能继续作为默认裁剪对象。

后续裁剪必须满足：

- Google 搜索提交后不出现 renderer crash。
- CDP 仍能 attach 并执行 `Runtime.evaluate`。
- Akamai 检测页可打开后再看具体检测点。
- 不能 mock 的基础渲染、网络、图片、JS 执行能力，不裁。
