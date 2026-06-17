# MVP 路线

## MVP 0：环境验证

目标：能编译并运行 `content_shell`。

交付：

- fetch Chromium 脚本
- GN args
- content_shell 能打开网页

## MVP 1：基础采集 Runtime

目标：封装最小 BrowserRuntime。

能力：

- goto
- evaluate
- screenshot
- dumpDom
- cookie 持久化
- proxy 配置

## MVP 2：Profile 系统

目标：同一个 Profile 下固定指纹。

能力：

- UA 配置
- language/timezone/screen 配置
- navigator hook
- canvas hook
- webgl hook

## MVP 3：有头/无头统一

目标：有头和无头检测结果一致。

能力：

- 同一套 Runtime
- 指纹对比测试页
- 网络请求对比
- Canvas/WebGL 对比

## MVP 4：采集任务脚本

目标：用户能写 YAML 任务批量采集。

示例：

```yaml
profile: mac_chrome_profile
headless: true
steps:
  - goto: "https://example.com"
  - wait: "body"
  - extract:
      title: "title"
      links: "a"
```

## MVP 5：数据保存和导出

能力：

- SQLite 保存任务结果
- CSV 导出
- JSON 导出
- 失败重试
- 代理池

