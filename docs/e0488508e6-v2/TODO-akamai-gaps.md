# TODO：Akamai 检测点 / 配置层遗留缺口

接续 `status-005` ~ `status-014` 的指纹 mock 进度，对照 `docs/Akamai 检测.md` 一~十类检测点逐项核实后，记录尚未落地的部分，供下一轮 patch 使用。当前实现全部在
`chromium-workspace/src`（未导出成 patch，见「运行时配置」一节）。

## 一、Akamai 检测点清单里尚未覆盖的

1. **`window.chrome.webstore` 存在性**（清单二）。当前 `InstallWindowChrome()` 只装配了 `app`/`csi`/`loadTimes`/`runtime`，没有 `webstore`。落地前需要先对真实 Chrome 桌面新 profile 抓一次，确认 `webstore` 是否存在（不同 Chrome 版本/渠道可能不同），再决定装配还是保持 `undefined`。

2. **设备能力开关位 `adp`**（清单五：`vibrate`/`getBattery`/`DeviceMotionEvent`/`DeviceOrientationEvent` 等存在性）。目前完全没有对应的 `fp-*` switch，也没有任何 status 文档验证过桌面 Mac Chrome 场景下这组值是否自洽。需要先测量 content_shell 默认状态 vs 真机，再决定是否需要 mock（清单原文的 `adp` 示例来自 iOS Safari fp，桌面场景的具体位含义还需重新核对）。

3. **行为事件采集 `mev/kev/tev/pev/doe/dme/oev` + `mst` 计数**（清单六）。有意搁置——纯 sign 场景下 sensor 允许全空。如果后续被判定卡在"零交互"，需要用 trusted input（`isTrusted=true`）合成鼠标/键盘轨迹。

4. ~~**`speechSynthesis.getVoices()` 返回空**（清单八，status-011/012 残留）。~~ **已解决，见 `status-016-webdriver-speech-mock.md`（2026-07-16）**。真实桌面 Chrome 有系统 TTS voice 列表，0 是明显的 headless/minimal 特征。**2026-07-16 用 `--fp-api-trace` 实测确认**：royalmail 页面加载过程中确实调用了 `SpeechSynthesis::getVoices()`（一次运行里命中 4 次），且 `speech_synthesis.cc` 里这个函数除了 `FP_API_TRACE` 埋点之外，只是 `TryEnsureMojomSynthesis()` + 返回 `voice_list_`，完全没有 `fp_override`/profile 读取——坐实了这条不是理论推测。已加 `kFingerprintSpeechVoicesMode`（`fp-speech-voices-mode=mac_defaults`）+ `MaybeApplyFingerprintMockVoices()`，`voice_list_` 为空时用静态 macOS 语音列表填充，`mac_chrome_profile.json` 已加 `speech.mode: mac_defaults`。

5. **时间锚定 / 反重放**（清单九）。目前只做了 timezone（status-007）。清单要求的"`Date.now()` 锚定真实时间、只虚拟化执行耗时"完全没有实现——`mac_chrome_profile.json` 里新增的 `time.mode`/`virtualize_delays` 字段目前**没有任何代码解析**（`shell_fingerprint_profile.cc` 里搜不到 `time` 相关字段），纯占位。

6. **`devicePixelRatio` 跨宿主一致性**（清单四残留，status-010）。当前跟随宿主（本机 Mac=2，与 profile 声明设备一致，但换机器会变）。覆盖 dsf 会影响渲染缩放，需要单独评估影响面。

7. ~~**`navigator.webdriver` 没有走 profile 机制，靠隐式默认值凑巧对**~~ **已解决，见 `status-016-webdriver-speech-mock.md`（2026-07-16）**。（新发现，2026-07-16 用 `--fp-api-trace` 实测确认）`Navigator::webdriver()`（`third_party/blink/renderer/core/frame/navigator.cc`）逻辑原来是 `RuntimeEnabledFeatures::AutomationControlledEnabled() || probe::ApplyAutomationOverride(...)`，跟其它 navigator 字段不一样，没有 `fp_override`/`kFingerprintNavigator*` 这套 switch 读取——是"默认行为凑巧对"而不是"显式 mock"，没有兜底逻辑。已加 `kFingerprintNavigatorWebdriver`（`fp-navigator-webdriver=true|false`），`navigator.cc::webdriver()` 现在跟其它 navigator.* 字段一样优先读 `fp_override`；`mac_chrome_profile.json` 本来就有 `navigator.webdriver: false`，编译后自动生效，不用改 JSON。

## 二、本仓库配置层的遗留（与 Akamai 清单无直接对应，但影响可用性）

7. **`config/runtime.yaml` 完全不生效**。全仓库（含 `chromium-workspace/src` 和 `scripts/*.sh`）都没有 `--runtime-config` 或 yaml 解析逻辑；唯一真实入口是手动传 `--fingerprint-profile=<json>`。`runtime.yaml` 里的 `runtime.*`（headless/data_dir/proxy/viewport）现在只是文档说明。需要决定：a) 实现一个真正的 loader；或 b) 去掉这层，只维护 profile json + 启动脚本参数，避免文档与实现脱节。

8. **`mac_chrome_profile.json` 的 `network.tls` / `network.http2`（`"chrome_like"`）未消费**。`shell_fingerprint_profile.cc` 只解析了 `network.acceptLanguage`，TLS/HTTP2 层指纹（JA3、H2 SETTINGS 帧顺序等）目前完全没做。是否需要看目标风控是否做传输层检测（Akamai sensor 本身这次逆向的是 JS 层 `sensor_data`，未涉及 TLS 层，但仓库旧 profile schema 里保留了这两个字段，需明确要不要做）。

9. **多 profile 池 + 随机选择未实现**。`plan-runtime-profile-mock.md` 设计的 `profile_selection`（`fixed`/`random_per_launch`/`random_per_profile`/`random_per_origin`）和 `profile_pool`（多设备候选集）都没有代码支持，目前只能跑单一固定 profile。

## 三、实测案例：royalmail.com 被服务端 RST_STREAM（2026-07-13）

用 `mac_chrome_profile.json` 实测 `https://www.royalmail.com/track-your-item#/tracking-results/<单号>`，页面本身能加载，但真正取运单数据的
`https://api-web.royalmail.com/mailpieces/microsummary/v1/summary/<单号>` 请求在 DevTools 里报 `net::ERR_HTTP2_PROTOCOL_ERROR`。抓 netlog（`--log-net-log`）逐帧核实：

- CORS 预检（OPTIONS）正常拿到 200，`Access-Control-Allow-Origin` 等头齐全——不是 CORS 问题。
- 确认 profile 已生效：实际发出的 `Sec-CH-UA: "Google Chrome";v="137", "Chromium";v="137", "Not/A)Brand";v="24"`、`User-Agent: ...Chrome/137.0.0.0...`，跟 profile 一致——排除了 UA/UA-CH 层面的问题。
- 真正的 GET 请求发出后（HTTP2 SETTINGS 握手正常完成），约 1.3~1.5 秒后收到服务端 `HTTP2_SESSION_RECV_RST_STREAM {error_code: "2 (INTERNAL_ERROR)"}`，从未收到任何响应头——是**服务端主动重置流**，Chromium 据此上报 `ERR_HTTP2_PROTOCOL_ERROR`。不是客户端 bug，不是裁剪 patch 影响，也不是 TLS 握手层面的问题（握手和 SETTINGS 交换都正常完成）。
- 请求头里带了一个 `x-rmg-recaptcha` 头，值是 `P1_<JWT>` 形式，但 JWT payload 解出来是 **MessagePack 二进制**（可见字段名 `pd`/`exp`/`passkey`，值本身是加密的），不是标准 reCAPTCHA token——这本质上是站点自己的客户端风控 sensor 载荷（很可能就是 Akamai Bot Manager 的 sensor_data 变体，或者站点自建的等价机制），在发起 API 请求前由页面 JS 采集生成。
- 约 1.3 秒的延迟 + 直接 RST 而非返回干净的 403/JSON，符合 Akamai/WAF 常见的"软拦截"手法：服务端异步评估这个 token/风控分数后，故意用协议层错误而不是正常错误响应搞坏连接，增加排查难度。

**结论（有证据支持，但未 100% 坐实到具体某一项）**：UA/UA-CH 这类已经 mock 的字段本身没问题；被拒大概率是这个加密 sensor 载荷所反映的风控分数不够，而不是传输层协议实现的问题。token 内容加密无法解读，无法精确定位是哪一个信号导致的，但结合 docs/Akamai 检测.md 的检测点清单，最可能的嫌疑还是本文档第一节里已经记录、尚未 mock 的几项：六（行为事件轨迹全空）、五（adp 设备能力位未验证）、二（`chrome.webstore` 缺失）、八（`speechSynthesis` 语音列表为空）。也不能排除是 TLS 层指纹（JA3/JA4，跟 UA-CH 是两回事，本文档第二节 `network.tls`/`network.http2` 提到过未实现）或者纯粹是这台机器的 IP/网络环境被判定可疑、与浏览器指纹无关。

**下一步验证建议**：拿真实桌面 Chrome 在同一网络环境下对同一单号抓一份 netlog 做对照，看 a) 真 Chrome 是否也会在短时间内重复请求同一单号后被拦（判断是不是请求频率/IP 信誉问题，跟指纹无关）；b) 真 Chrome 发出的 `x-rmg-recaptcha` token 大小/生成耗时是否和 content_shell 有明显差异（间接判断 token 生成阶段用到的环境探测是否被 content_shell 的缺口影响到了）。

### 对照结果（同网络环境，真实 Chrome 149 vs content_shell + mac_chrome_profile.json 伪装 Chrome 137）

用同一单号在同一台机器上跑了一遍真实 `Google Chrome.app`（同一网络/IP），抓 netlog 逐项对比：

- **真 Chrome 请求成功**：同样先 OPTIONS 预检 200，然后 GET 拿到 `HTTP/1.1 200`、`content-type: application/json`、`content-length: 432`——是真实的运单数据，不是被拦。
- **延迟几乎一样**：真 Chrome 从发出 GET 到收到响应头，也用了约 **1.29 秒**，跟 content_shell 被 RST 前的等待时间（约 1.3～1.5 秒）基本一致。说明这个延迟就是该接口本身的正常后端耗时，**不是"风控异步评分需要额外时间"**——之前这个推测可以排除；content_shell 这边只是在同样的时间点上，后端选择了重置流而不是回包。
- **请求头逐项比对，结构完全一致**：`x-rmg-language`、`sec-ch-ua-platform`、`accept-language`、`x-profile-type`、`sec-ch-ua`、`x-rmg-recaptcha`、`sec-ch-ua-mobile`、`x-ibm-client-id`、`user-agent`、`accept`、`origin`、`sec-fetch-*`、`referer`、`accept-encoding`、`cookie`、`priority`——两边字段、顺序都一样，content_shell 没有缺头或多头。唯一差异是版本号本身：真机是 `Chrome/149`（当前真实最新版），profile 伪装的是 `Chrome/137`（版本落后，但单纯版本旧不至于被硬拦，大量真实用户也在用旧版 Chrome）。
- **`x-rmg-recaptcha` token 长度接近**：真 Chrome 1769 字符，content_shell 1751 字符，没有量级上的差异；内容本身是加密的，看不出具体字段差异。
- **TLS 握手层面**：这次 netlog 的详细度不够，两边都只能看到 `ech_enabled: true` 这种粗粒度信息，看不到 ClientHello 的 cipher/extension 顺序，没法在这个层面比出 JA3/JA4 指纹差异——如果要继续深挖 TLS 层，需要用 `tshark`/`tcpdump` 抓包算 JA3/JA4，netlog 本身不够。

**结论**：请求头、CORS、UA/UA-CH、后端延迟这几项已经逐一排除，content_shell 和真 Chrome 在网络可观察层面几乎没有差异。真正导致被拦的信号大概率藏在 `x-rmg-recaptcha` 这个加密 payload 里——也就是页面 JS 采集环境信息时用到的某个信号，跟本文档第一节已经记录、还没做的几项（`chrome.webstore`、adp 设备能力位、行为事件轨迹、`speechSynthesis` 语音列表）关联性最大，也不排除是 TLS ClientHello 层面的指纹（需要另外抓包验证）。由于 token 加密无法直接定位是哪一项，建议按性价比顺序把清单里剩下的几项逐一补上（`chrome.webstore` 改动最小可以先做），每做完一项就重新跑一遍这个对照测试，看这条请求是否转为 200。

## 四、导出 patch

`content/shell/common/shell_fingerprint_profile.{h,cc}` 及各阶段改动目前都直接改在 `chromium-workspace/src`，尚未导出为独立 patch 文件（`patches/` 下）。按 status-006 的建议，应导出为类似 `0090-config-driven-fingerprint-profile.patch` 的独立 patch，纳入版本控制，避免 `chromium-workspace/src` 的改动只存在于本机 checkout 里。
