# MVP 文档索引

本文档目录记录当前 `content_shell` 最小运行时 MVP 的实际状态，重点是：

- 源码如何获取、生成 GN 配置、编译 `content_shell`。
- 编译产物如何提取到本项目的 `output/content-shell-minimal/`。
- 当前为了让 macOS app bundle 能启动，做了哪些临时修补。
- 已经裁剪了哪些能力，哪些还没有从源码层彻底裁剪。

当前验证过的输出位置：

```text
/Users/zy.yuan/Develop/browser-runtime-projects/chromium-minimal-runtime/output/content-shell-minimal/Content Shell.app
```

当前对应 Chromium 源码目录：

```text
/Users/zy.yuan/Develop/browser-runtime-projects/chromium-workspace/src
```

当前状态摘要：

- `out/ContentShell` 原始编译产物可编译成功。
- 提取后的 `Content Shell.app` 当前大小约 `205M`。
- `open -n Content Shell.app` 已验证可以启动。
- `codesign --verify --verbose=6 Content Shell.app` 已验证通过。
- 仍存在若干未从源码层彻底消除的依赖，例如 `libtest_trace_processor.dylib`。

文档列表：

- [编译与启动方式](./编译与启动方式.md)
- [已改与未改清单](./已改与未改清单.md)

