# DevTools 当前页面调试修复

## 问题

DevTools 前端资源已经恢复后，右键 Inspect 可以打开 DevTools 窗口，但 DevTools 不能调试当前页面。

原因是最小化编译宏 `CONTENT_SHELL_MINIMAL_ROOT` 仍然关闭了 `ShellDevToolsBindings` 中的 `DevToolsFrontendHost`。这会导致 DevTools 前端页面虽然可以加载，但没有创建前端和被检查页面之间的 embedder bridge。

## 本次修改

在 `content/shell/BUILD.gn` 中，当 `content_shell_keep_devtools_frontend=true` 时，给 `content_shell_lib` 增加：

```gn
CONTENT_SHELL_KEEP_DEVTOOLS_FRONTEND=1
```

在以下文件中，让 DevTools 前端桥接代码在最小化版本里也随该开关保留：

- `content/shell/browser/shell_devtools_bindings.h`
- `content/shell/browser/shell_devtools_bindings.cc`

保留内容包括：

- `DevToolsFrontendHost` 头文件和成员字段；
- `ReadyToCommitNavigation()` 中创建 `DevToolsFrontendHost::Create(...)` 的逻辑；
- `HandleMessageFromDevToolsFrontend(...)` 的前端消息通道。

## 编译与打包验证

已执行：

```bash
cd /Users/zy.yuan/Develop/browser-runtime-projects/chromium-workspace/src
buildtools/mac/gn gen out/ContentShell
/Users/zy.yuan/Develop/browser-runtime-projects/chromium-workspace/depot_tools/autoninja -C out/ContentShell content_shell

cd /Users/zy.yuan/Develop/browser-runtime-projects/chromium-minimal-runtime
CHROMIUM_SRC=/Users/zy.yuan/Develop/browser-runtime-projects/chromium-workspace/src BUILD_DIR=out/ContentShell scripts/package_content_shell_minimal.sh
scripts/smoke_content_shell_app.sh
```

结果：

- `gn gen` 成功；
- `content_shell` 增量编译成功；
- 输出应用仍在 `output/content-shell-minimal/Content Shell.app`；
- 打包后应用大小约 `196M`；
- `scripts/smoke_content_shell_app.sh` 通过；
- `http://127.0.0.1:9231/devtools/devtools_app.html?targetType=tab` 返回 `200 OK`；
- `/json/list` 可以列出当前 `page` target；
- `shell_devtools_bindings.o` 中已包含 `DevToolsFrontendHost::Create` 和 `HandleMessageFromDevToolsFrontend` 符号。

## 手动复测建议

启动输出应用后，在页面上右键选择 Inspect。预期结果：

- DevTools 窗口可以打开；
- Elements/Console 能绑定当前页面；
- Console 中执行 `document.URL` 应返回当前被检查页面 URL；
- Elements 面板高亮节点时，应能联动当前页面。
