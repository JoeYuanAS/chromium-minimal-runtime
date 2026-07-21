# 配置驱动指纹 Mock（残留收尾：maxTouchPoints + Notification.permission）

接续 `status-012`，本轮收尾两个小残留。

## 1) navigator.maxTouchPoints

### 问题

Blink getter（`NavigatorEvents::maxTouchPoints`）已支持读 `fp-max-touch-points` switch，profile loader 也已解析 `navigator.maxTouchPoints`，但 **browser 未把 profile 值翻译成 renderer switch**，导致配置无效。

### 修复

`content/shell/browser/shell_content_browser_client.cc`：在 renderer 进程命令行 append：

```text
--fp-max-touch-points=<int>
```

### 验证

| profile.maxTouchPoints | 实测 `navigator.maxTouchPoints` |
|---|---|
| 0（mac_chrome_profile 默认） | 0 |
| 5（临时 profile） | **5** ✅ |

## 2) Notification.permission

### 问题

`permissions.query({name:'notifications'})` 已在阶段 F 修成 `prompt`，但 `Notification.permission` 仍为 `"denied"`。

原因：`BlinkNotificationServiceImpl::GetPermissionStatus` 在 `GetPlatformNotificationService() == nullptr` 时直接返回 DENIED，不走 PermissionManager。content_shell 原先返回 nullptr。

### 修复

新增最小实现 `ShellPlatformNotificationService`（不真正弹通知，只让 mojo 路径能继续走到 PermissionManager）：

- `content/shell/browser/shell_platform_notification_service.{h,cc}`
- `ShellBrowserContext::GetPlatformNotificationService()` 懒创建并返回该服务
- `BUILD.gn` 注册源文件

配合已有 `permissions.mode: "chrome_defaults"`，PermissionManager 对 NOTIFICATIONS 返回 ASK → Blink 映射为 `"default"`。

### 验证

| 检测点 | 无 profile | profile |
|---|---|---|
| `Notification.permission` | denied | **default** ✅ |
| `permissions.query(notifications)` | denied | **prompt** ✅ |

## 残留说明

- `speechSynthesis.getVoices()`：Mac 上 TTS 后端存在；同步首次调用常返回空列表，真实 Chrome 也常需等 `voiceschanged`。未做额外 mock，暂不视为阻塞。
