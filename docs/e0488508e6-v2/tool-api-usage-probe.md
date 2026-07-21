# API 调用探针：真机 Chrome vs content_shell 对照

## 目的

`docs/Akamai 检测.md` 的检测点清单是从别的站点的 sensor 脚本反混淆得出的通用清单，不一定精确覆盖 royalmail 这次实际用到的加密 `x-rmg-recaptcha` payload 采集了哪些浏览器能力。与其继续猜"清单里哪一项没做对"，不如直接**监控页面 JS 在构造这个 payload 之前，实际读取/调用了哪些 API**，两边（真 Chrome、content_shell）跑一遍，取交集/差集。

## 原理

用 CDP（DevTools Protocol）的 `Page.addScriptToEvaluateOnNewDocument` 在**页面自身脚本执行之前**注入一段探针脚本（`instrument.js`）。它只做包装、不改变返回值：

- 给 `navigator.*`、`screen.*`、`window.chrome`、`WebGLRenderingContext.getParameter`、`canvas.toDataURL`、`speechSynthesis.getVoices`、`Notification.permission`、`navigator.permissions.query`、`RTCPeerConnection`、`Function.prototype.toString` 等一批高价值指纹 API 加日志包装，每次被读/被调用就记一条 `{name, kind, t}` 到 `window.__apiHits`。
- 同时 hook `XMLHttpRequest`/`fetch`，一旦发现请求 URL 命中 `microsummary|recaptcha|akam/`（也就是真正携带 sensor 数据的那条请求），就把当时的 `__apiHits` 整体拷贝一份存进 `window.__apiHitsAtSensorRequest`——这就是"构造这个 payload 之前，页面到底摸了哪些 API"的精确列表。
- 因为是 CDP 层面注入、且只做透明包装（`toString` 也做了转发），真 Chrome 和 content_shell 都能直接用同一份脚本，不需要改代码。

`Page.addScriptToEvaluateOnNewDocument` 保证脚本在该 tab 每次导航时都先于页面自己的任何 `<script>` 执行，等价于 Puppeteer 的 `evaluateOnNewDocument`。

## 文件

- `tools/api_usage_probe/instrument.js` —— 注入脚本本体。
- `tools/api_usage_probe/probe_api_usage.py` —— CDP 驱动：建新 tab、注入脚本、导航、监听 `Network.requestWillBeSent` 抓 sensor 请求的真实请求头、抓完导出 `window.__apiHits` 到 JSON。
- `tools/api_usage_probe/diff_api_hits.py` —— 对比两份探针 JSON，输出"只有一边碰过的 API"、"两边都碰但次数不同的 API"、以及 sensor 请求头是否有缺失字段。

## 使用方式

依赖（在你本机装一次）：

```bash
pip3 install requests websocket-client
```

第一步，两个浏览器都要**额外加 `--remote-debugging-port`**（跟之前抓 netlog 的命令并列即可，端口用不同的，方便先后跑）：

```bash
# 真 Chrome
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --user-data-dir="$(mktemp -d)" --no-first-run --no-default-browser-check \
  --remote-debugging-port=9223

# content_shell（记得带 profile）
"out/ContentShell/Content Shell.app/Contents/MacOS/Content Shell" \
  --user-data-dir="$(mktemp -d)" --no-first-run --disable-breakpad \
  --fingerprint-profile=/Users/zy.yuan/Develop/browser-runtime-projects/chromium-minimal-runtime/config/mac_chrome_profile.json \
  --remote-debugging-port=9224
```

两个都启动后（不用先导航到任何页面，探针脚本会在下一次导航时自动生效），分别跑：

```bash
cd /Users/zy.yuan/Develop/browser-runtime-projects/chromium-minimal-runtime/tools/api_usage_probe

python3 probe_api_usage.py --port 9223 \
  --url "https://www.royalmail.com/track-your-item#/tracking-results/<换一个没测过的单号>" \
  --out real_chrome_hits.json --timeout 25

python3 probe_api_usage.py --port 9224 \
  --url "https://www.royalmail.com/track-your-item#/tracking-results/<同一个单号>" \
  --out content_shell_hits.json --timeout 25
```

跑完对比：

```bash
python3 diff_api_hits.py real_chrome_hits.json content_shell_hits.json
```

输出会列出：

- 只有真 Chrome 摸过、content_shell 完全没碰的 API（最值得关注——这些很可能就是被读取时行为不对/直接抛错/返回值异常，导致 sensor 提前放弃采集或标记异常）。
- 两边都摸了但调用次数不同的 API。
- sensor 请求头逐项 diff（含 `x-rmg-recaptcha` 长度对比）。

## 局限

- 只能看到"读取/调用了哪个 API"，看不到"读到的值对不对"——值本身的正确性还是要靠 `tools/fingerprint_diagnostic` 那份结构化对照。两个工具配合用：先用 diff 结果缩小范围，再用诊断页确认具体字段的值是否跟真机一致。
- TLS ClientHello / HTTP2 帧顺序这类传输层特征，CDP 探针看不到，需要另外用 `tshark`/`tcpdump` 抓包算 JA3/JA4。
- 无法保证 sensor 脚本一定通过我们 hook 的这些"入口"读取数据（它可能用了没覆盖到的冷门 API），如果两边 diff 完全一样、但依然一边被拒一边成功，说明信号来自我们没覆盖的路径，需要回去看 `Network.requestWillBeSent` 抓到的完整请求头和 `__apiHits` 全量日志（`--key full`），或者干脆去定位、反混淆 royalmail 实际加载的那个 sensor JS 文件本身。
