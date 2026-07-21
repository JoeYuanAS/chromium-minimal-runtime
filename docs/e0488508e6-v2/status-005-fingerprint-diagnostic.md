# 本地指纹诊断页

## 目的

新增一个本地诊断工具，用于查看当前 `Content Shell` 运行时实际暴露的浏览器指纹面。该工具只采集和展示信息，不修改运行时行为。

## 文件

- `tools/fingerprint_diagnostic/index.html`
- `tools/fingerprint_diagnostic/server.py`
- `scripts/run_fingerprint_diagnostic.sh`

## 使用方式

```bash
cd /Users/zy.yuan/Develop/browser-runtime-projects/chromium-minimal-runtime
scripts/run_fingerprint_diagnostic.sh
```

默认会启动本地服务：

```text
http://127.0.0.1:8787/
```

并用当前输出应用打开：

```text
output/content-shell-minimal/Content Shell.app
```

如果要指定应用路径：

```bash
APP="/path/to/Content Shell.app" scripts/run_fingerprint_diagnostic.sh
```

如果希望同时开启 CDP：

```bash
REMOTE_DEBUGGING_PORT=9231 scripts/run_fingerprint_diagnostic.sh
```

## 采集内容

- 请求头：由本地 server 回显 `User-Agent`、`Accept-Language` 等请求头。
- 自动化标记：`navigator.webdriver`、`window.webdriver`、Selenium/Phantom/CDP 常见全局符号。
- Navigator：UA、platform、languages、hardwareConcurrency、deviceMemory、maxTouchPoints、webdriver 等。
- 属性存在性：Akamai 文档中提到的 `navigator` 属性 bitmap 相关字段。
- Plugins/MimeTypes：长度、枚举、反向引用摘要、对象类型。
- `window.chrome`：对象存在性、keys、runtime/connect/sendMessage 形状。
- Screen/Window：窗口尺寸、screen、DPR、visualViewport。
- Storage/Runtime：localStorage、sessionStorage、indexedDB、caches、crypto。
- Permissions/Media：permissions query、mediaDevices、speechSynthesis、RTC 构造器存在性。
- WebGL：vendor、renderer、unmasked vendor/renderer、limits、extensions。
- Canvas：稳定绘制后的 dataURL hash 和像素采样 hash。
- Audio：OfflineAudioContext 渲染后的 sample hash。
- Native/Descriptor：常见函数 `toString()` 和关键属性 descriptor。

## 输出

页面支持：

- 重新采集；
- 复制 JSON；
- 下载 JSON；
- 保存到本地。

通过本地 server 打开时，点击“保存到本地”会写入：

```text
output/fingerprint-reports/
```
