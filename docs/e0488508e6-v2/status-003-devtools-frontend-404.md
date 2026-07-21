# v2 变更记录 003：恢复右键 Inspect / DevTools 前端资源

日期：2026-06-17

## 背景

右键 `Inspect` 已经能打开 DevTools 窗口，但窗口内访问：

```text
http://127.0.0.1:<port>/devtools/devtools_app.html?targetType=tab
```

返回：

```text
Server returned HTTP status 404
```

用户要求保留检查能力，或者至少能通过编译参数决定是否保留。

## 根因

`content_shell_minimal_root = true` 时，`content/shell/BUILD.gn` 会从 `content_shell.pak` 中移除：

- `content/browser/devtools/devtools_resources.pak`
- `third_party/blink/public/resources/inspector_overlay_resources.pak`
- `ui/webui/resources/webui_resources.pak`

同时，`content/browser/devtools/features.gni` 中的 `enable_devtools_frontend` 也被 `content_shell_minimal_root` 直接关闭，导致 DevTools 前端资源 target 不会生成。

因此右键菜单能启动 DevTools HTTP server，但 server 里没有 `/devtools/devtools_app.html` 对应资源，最终返回 404。

## 已改源码

新增 GN 参数：

```gn
content_shell_keep_devtools_frontend = true
```

默认含义：

- `content_shell_minimal_root = true` 仍然保留最小根目标策略。
- `content_shell_keep_devtools_frontend = true` 时，保留内置 DevTools frontend 和 inspector overlay。
- runtime-only 包可以显式设置 `content_shell_keep_devtools_frontend = false`，但只能用于不需要右键 Inspect 的版本。

涉及文件：

```text
/Users/zy.yuan/Develop/browser-runtime-projects/chromium-workspace/src/build/config/content_shell_minimal.gni
/Users/zy.yuan/Develop/browser-runtime-projects/chromium-workspace/src/content/browser/devtools/features.gni
/Users/zy.yuan/Develop/browser-runtime-projects/chromium-workspace/src/content/shell/BUILD.gn
/Users/zy.yuan/Develop/browser-runtime-projects/chromium-workspace/src/third_party/blink/public/BUILD.gn
/Users/zy.yuan/Develop/browser-runtime-projects/chromium-workspace/src/content/shell/browser/shell_web_contents_view_delegate_mac.mm
```

右键菜单行为也保持：

- `ShellDevToolsFrontend::Show(web_contents_)`
- `Activate()`
- `InspectElementAt(params_.x, params_.y)`

## 构建依赖

启用内置 DevTools frontend 后，构建必须恢复 DevTools 前端工具链：

```text
third_party/node/mac_arm64/node-darwin-arm64/bin/node
third_party/devtools-frontend/src/node_modules/@rollup/rollup-darwin-arm64
```

当前 checkout 的实际 Node 版本来自：

```text
third_party/node/update_node_binaries
NODE_VERSION="v24.12.0"
```

注意：`third_party/node/README.chromium` 中的 Node 版本信息是旧的，不能作为本 checkout 的准确信息。

## 打包修正

项目侧 launcher 也做了一个小修：

```text
/Users/zy.yuan/Develop/browser-runtime-projects/chromium-minimal-runtime/src/content_shell_app_launcher.c
```

修正点：

- 强制 `CHROME_LOG_FILE=/tmp/content_shell.log`。
- 启动前 `chdir("/tmp")`。

目的：避免 `open -n Content Shell.app` 时在 `.app/Contents/MacOS/` 下生成空的 `content_shell.log`，让 smoke 脚本保持干净。

## 编译与打包

GN：

```bash
cd /Users/zy.yuan/Develop/browser-runtime-projects/chromium-workspace/src
buildtools/mac/gn gen out/ContentShell
```

编译：

```bash
/Users/zy.yuan/Develop/browser-runtime-projects/chromium-workspace/depot_tools/autoninja \
  -C out/ContentShell content_shell
```

打包：

```bash
cd /Users/zy.yuan/Develop/browser-runtime-projects/chromium-minimal-runtime
CHROMIUM_SRC=/Users/zy.yuan/Develop/browser-runtime-projects/chromium-workspace/src \
BUILD_DIR=out/ContentShell \
  scripts/package_content_shell_minimal.sh
```

结果：

```text
196M output/content-shell-minimal/Content Shell.app
codesign valid on disk
```

## 验证结果

直接验证 DevTools frontend：

```bash
output/content-shell-minimal/Content\ Shell.app/Contents/MacOS/Content\ Shell.bin \
  --user-data-dir=/tmp/content-shell-devtools-profile \
  --remote-debugging-port=9231 \
  'data:text/html,<html><body><button id="x">inspect me</button></body></html>'

curl -D - \
  'http://127.0.0.1:9231/devtools/devtools_app.html?targetType=tab'
```

结果：

```text
HTTP/1.1 200 OK
Content-Type:text/html
```

基础 smoke：

```bash
scripts/smoke_content_shell_app.sh
```

结果：

```text
smoke ok
```

## 后续规则

当前主线是 `debug-capable minimal`，默认保留：

- DevTools frontend。
- Inspector overlay。
- CDP server。
- 右键 Inspect。

如果后续要做极限 `runtime-only` 包，可以设置：

```gn
content_shell_keep_devtools_frontend = false
```

但该版本预期不支持内置右键 Inspect，只能依赖外部 CDP client；并且需要单独验证 Akamai 检测和调试流程是否仍满足目标。
