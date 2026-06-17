# Chromium Minimal Runtime

目标：基于 Chromium 的 `content_shell/headless_shell` 思路，裁剪 Chrome 产品层，保留 Blink、V8、Network、Skia、ANGLE 等核心能力，做一个用于数据采集的最小浏览器运行时。

## 核心目标

1. 精简：不要书签、同步、扩展、密码管理、PDF、打印等 Chrome 产品功能。
2. 高兼容：尽量支持 95% 现代网站，保留真实浏览器引擎能力。
3. 可配置指纹：支持 Navigator、Canvas、WebGL、Audio、Timezone、Language、Screen、TLS/HTTP2 等采集相关配置。
4. 有头/无头一致：有头和无头使用同一套 Runtime、Profile、NetworkContext、StoragePartition。
5. 面向采集：提供 goto、click、input、wait、evaluate、extract、screenshot 等 API。

## 推荐技术路线

不要 fork `chrome/` 产品层，而是从 Chromium 的 `content_shell` 或 `headless_shell` 思路切入。

保留：

- `content/`
- `blink/`
- `v8/`
- `net/`
- `services/network/`
- `skia/`
- `ui/`
- `gpu/`
- `third_party/angle/`
- `storage/`
- `devtools/`

尽量禁用：

- extensions
- sync
- signin
- bookmarks
- password manager
- pdf
- printing
- translate
- safe browsing
- autofill
- media router
- enterprise

## 项目结构

```text
chromium-minimal-runtime/
├── README.md
├── docs/
│   ├── 方案设计.md
│   ├── 指纹配置.md
│   ├── 有头无头一致性.md
│   ├── Chromium裁剪清单.md
│   └── MVP路线.md
├── config/
│   ├── mac_chrome_profile.json
│   └── runtime.yaml
├── scripts/
│   ├── fetch_chromium.sh
│   ├── gen_args.sh
│   └── build_content_shell.sh
├── src/
│   ├── app_main.cc
│   ├── browser_runtime.h
│   ├── browser_runtime.cc
│   ├── fingerprint_profile.h
│   ├── fingerprint_profile.cc
│   ├── automation_api.h
│   └── automation_api.cc
└── examples/
    └── collect_task.yaml
```

## 当前状态

这是初始化骨架，不包含完整 Chromium 源码。实际开发时建议把本项目作为 Chromium 源码树外的设计与 patch 管理仓库，或放入 Chromium `src/collector_browser/` 子目录中。

## 快速运行 Content Shell

如果只是验证 `content_shell` 能跑起来，不必先拉完整 Chromium 源码，可以下载 Chromium 官方 snapshot 里的 `content-shell.zip`：

```bash
scripts/fetch_content_shell_snapshot.sh
scripts/run_content_shell_snapshot.sh 1645137 --remote-debugging-port=9222 https://example.com
```

不指定 revision 时脚本会读取当前平台的 `LAST_CHANGE`。上面的 `1645137` 是已验证过的 `Mac_Arm` snapshot。

## 最小源码 Checkout

如果要改 `content_shell` 源码，但暂时不拉完整历史和完整工作树，可以使用 sparse partial clone：

```bash
scripts/fetch_chromium_sparse_source.sh
```

默认 commit 是 `e0488508e67c7243b2f21e478727d1989f9d1e71`，对应已验证的 `Mac_Arm/1645137` snapshot。该脚本使用：

- `--depth=1`：不拉 git 历史。
- `--filter=blob:none`：按需拉文件内容。
- `sparse-checkout`：默认只展开 `content/shell`、`content/public`、`build`、`tools` 等起步路径。

注意：这个 sparse checkout 适合先读和改 `content_shell`。如果要从源码完整编译 `content_shell`，仍需要继续展开 DEPS 依赖和更多源码路径。
