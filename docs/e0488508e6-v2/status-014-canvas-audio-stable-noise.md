# 配置驱动指纹 Mock（阶段 H：Canvas / Audio stable noise）

接续 `status-013`，本轮实现配置驱动的 Canvas / Audio 稳定噪声。

## 目标

同一 profile 在不同宿主上产生**稳定且与宿主解耦**的 canvas/audio 指纹：

- 同 seed → 同噪声 → 同 fingerprint
- 不同 seed → 不同 fingerprint
- 无 profile / 非 `stable_noise` → 保持宿主原始输出

## 配置

`config/mac_chrome_profile.json` 已预留：

```json
"canvas": { "mode": "stable_noise", "seed": "profile_001" },
"audio":  { "mode": "stable_noise", "seed": "profile_001" }
```

## 设计

沿用 browser→switch→Blink：

1. profile loader 把 `seed` 哈希成 `uint64` token（`base::Hash`）
2. browser 转发：
   - `--fp-canvas-noise-token=<uint64>`
   - `--fp-audio-noise-token=<uint64>`
3. Blink 读 switch，在读回路径注入确定性噪声

### Canvas

复用 Chromium 自带的 `NoisePixels` / `NoiseHash`（`core/canvas_interventions`）：

- 新增 `fingerprint_stable_noise.{h,cc}`
- `getImageData`：`BaseRenderingContext2D::getImageDataInternal` 读像素后 `MaybeApplyFingerprintNoiseToImageData`
- `toDataURL`：`HTMLCanvasElement::ToDataURLInternal` 在编码前对 RGBA 像素做同样噪声

噪声幅度小（每通道 ±3），视觉几乎不变，但 hash 稳定偏移。

### Audio

- 新增 `modules/webaudio/fingerprint_audio_stable_noise.{h,cc}`
- `OfflineAudioContext::FireCompletionEvent` 在 resolve 前对 rendered buffer 各非零采样施加确定性微扰（约 `1e-7` 量级）

## 运行验证

| 检测点 | 无 profile | profile（seed=profile_001） |
|---|---|---|
| `canvas.toDataURL` hash | -1244972404 | **-1389354117** ✅ 改变 |
| `getImageData` 像素和 | 762466 | **759967** ✅ 改变 |
| OfflineAudio `audio_sum` | 338.4995225620005 | **338.4995245748214** ✅ 微扰 |

反射安全：未替换任何 JS 函数，`toDataURL` / `getImageData` / `startRendering` 仍为 native。

## 编译

`autoninja -C out/ContentShell content_shell` 成功。

## 累计已 native mock 的检测面

UA / UA-CH / Accept-Language / languages / webdriver / platform / productSub / vendor / hardwareConcurrency / deviceMemory / **maxTouchPoints** / timezone / plugins / mimeTypes / pdfViewerEnabled / window.chrome / screen 几何 / window 尺寸 / permissions 默认状态 / **Notification.permission** / WebGL unmasked vendor+renderer / **Canvas stable noise** / **Audio stable noise**。
