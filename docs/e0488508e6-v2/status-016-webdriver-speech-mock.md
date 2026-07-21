# navigator.webdriver 显式覆盖 + speechSynthesis.getVoices() mock

接续 `status-015` 用 `--fp-api-trace` 实测 royalmail 页面后确认的两个缺口（见 `TODO-akamai-gaps.md` 第一节第 4、7 条）：`speechSynthesis.getVoices()` 透出真实（在这个裁剪版里其实是空的）系统语音列表，`navigator.webdriver` 没有走 profile 覆盖机制、只是隐式凑巧为 `false`。本轮把这两个补上。

## navigator.webdriver

- 新增开关 `kFingerprintNavigatorWebdriver`（`fp-navigator-webdriver`，值 `"true"`/`"false"`），风格跟 `kFingerprintNavigatorPlatform` 等其它 navigator 字段一致。
- `content/shell/common/shell_fingerprint_profile.{h,cc}`：新增 `navigator_webdriver()`（`std::optional<bool>`），解析 `navigator.webdriver`（profile JSON 里这个字段之前是存在的，只是完全没被读取）。
- `content/shell/browser/shell_content_browser_client.cc`：profile 有值时把它翻译成 `fp-navigator-webdriver=true|false` 转发给 renderer。
- `third_party/blink/renderer/core/frame/navigator.cc::webdriver()`：先读 `fp_override`，非空直接按 override 返回；否则维持原来的 `AutomationControlledEnabled() || ApplyAutomationOverride()` 逻辑。跟其它 navigator.* 字段的 override 优先级完全一致。

`mac_chrome_profile.json` 本来就有 `"navigator": {"webdriver": false}`，不需要改 JSON，编译后这个字段就会从"没人读"变成"真的生效"。

## speechSynthesis.getVoices()

- 新增开关 `kFingerprintSpeechVoicesMode`（`fp-speech-voices-mode`，目前只支持值 `"mac_defaults"`）。
- `shell_fingerprint_profile.{h,cc}`：新增 `speech_voices_mode()`，解析顶层 `speech.mode`。
- `shell_content_browser_client.cc`：非空时转发给 renderer。
- `third_party/blink/renderer/modules/speech/speech_synthesis.{h,cc}`：`getVoices()` 在 `TryEnsureMojomSynthesis()` 之后调用新增的 `MaybeApplyFingerprintMockVoices()`——如果 `voice_list_` 还是空的（这个裁剪构建目前就是这样，真实 mojo TTS 后端要么没有要么没连上）且开关值是 `mac_defaults`，就用 `mojom::blink::SpeechSynthesisVoice::New(...)` 直接在进程内构造一份静态的 macOS 标准语音列表（Samantha/Alex/Fred/Victoria/Karen/Daniel/Moira/Tessa，`Samantha` 标 `is_default`，全部 `is_local_service=true`），塞进 `voice_list_` 后返回。用一个 `fp_mock_voices_applied_` 标记只做一次，不会每次调用都重建。

这份语音列表不追求跟任何一台真机字节级一致——目标只是"非空、看起来像正常 macOS Chrome 该有的语音列表"，不是"空列表"这种明显的裁剪/无头特征。如果以后要做得更精细（比如让列表随 profile 变化、覆盖更多语言），可以把 `kMockVoices` 数组换成从 profile JSON 读取的可配置列表。

`mac_chrome_profile.json` 新增了 `"speech": {"mode": "mac_defaults"}` 才会激活这个 mock；不加这个字段行为不变（保持原来可能为空的真实列表）。

## 编译 + 验证

跟之前几轮一样：

```bash
cd /Users/zy.yuan/Develop/browser-runtime-projects/chromium-workspace/src
autoninja -C out/ContentShell content_shell
```

验证方法：重新跑一遍 `status-015.md` 里的 `--fp-api-trace` 采集流程，然后在页面里手动跑：

```js
console.log(navigator.webdriver);          // 应为 false
console.log(speechSynthesis.getVoices());  // 应为长度 8 的数组，不是空数组
```

或者直接看 trace 日志——`navigator.webdriver`/`speechSynthesis.getVoices` 这两条埋点依然会照常打印，行为没变，只是背后的返回值现在受 profile 控制了。

## 未覆盖 / 后续可以做得更细的地方

- `navigator.webdriver` 的 override 是全局布尔，没有对齐 CDP Automation domain 的其它副作用（比如某些 CDP 命令仍然可能间接暴露自动化痕迹）；这次只覆盖了 JS 可读的 `navigator.webdriver` 属性本身。
- `speechSynthesis` mock 列表是写死的 8 个 macOS 系统语音，没有做到"随 profile 里声明的操作系统/语言环境自动调整"（比如 Windows profile 应该给 Windows 风格的语音列表，现在无论什么 profile 都是这份 macOS 列表）。如果以后要支持跨平台 profile，需要把 `kMockVoices` 换成按 `profile.name()`/UA 平台分支的多套列表。
