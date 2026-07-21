#!/usr/bin/env python3
"""
Applies the exact same --fp-api-trace instrumentation (see
docs/e0488508e6-v2/status-015-api-usage-tracer.md in chromium-minimal-runtime)
to a second, clean Chromium checkout, so you can build content_shell (or
`chrome`) from an unmodified tree and diff the "[FP_API_TRACE]" log output
against the content_shell in chromium-workspace/src line-for-line -- both
sides running literally the same instrumentation code.

Why this exists: chromium-workspace/src is not under version control, so
there's no `git diff` to hand you. This script instead replays the exact
literal find/replace edits that were made there, against whatever Chromium
src/ root you point it at. Each edit is verified to match exactly once
before being applied; if your checkout's revision differs enough that a
context snippet doesn't match, that file is skipped and reported instead of
silently corrupting anything.

Usage:
    python3 apply_fp_api_trace.py /path/to/clean/chromium/src
    python3 apply_fp_api_trace.py /path/to/clean/chromium/src --dry-run

Then build as usual, e.g.:
    cd /path/to/clean/chromium/src
    gn gen out/Default
    autoninja -C out/Default content_shell
    "out/Default/Content Shell.app/Contents/MacOS/Content Shell" \\
        --user-data-dir="$(mktemp -d)" --no-first-run --disable-breakpad \\
        --fp-api-trace <url>
"""
import argparse
import os
import sys

# Each entry: (path relative to src/, old_string, new_string).
# old_string must appear EXACTLY ONCE in the file for the edit to apply.
EDITS = [
    (
        "third_party/blink/public/common/switches.h",
        """BLINK_COMMON_EXPORT extern const char kFingerprintCanvasNoiseToken[];
BLINK_COMMON_EXPORT extern const char kFingerprintAudioNoiseToken[];
}  // namespace switches""",
        """BLINK_COMMON_EXPORT extern const char kFingerprintCanvasNoiseToken[];
BLINK_COMMON_EXPORT extern const char kFingerprintAudioNoiseToken[];

// Diagnostic-only: when present (no value needed), every instrumented
// fingerprint-relevant getter/method (navigator.*, window.chrome, screen.*,
// WebGL getParameter, canvas/audio readback, permissions, notifications,
// speechSynthesis, window.chrome install) logs one LOG(INFO) line tagged
// "[FP_API_TRACE]" so real Chrome vs content_shell API-touch behavior can be
// diffed via the shared process log. Zero-cost when absent (single
// HasSwitch() check, cached per call site). Never enable in production.
BLINK_COMMON_EXPORT extern const char kFingerprintApiTrace[];
}  // namespace switches""",
    ),
    (
        "third_party/blink/common/switches.cc",
        """const char kFingerprintCanvasNoiseToken[] = "fp-canvas-noise-token";
const char kFingerprintAudioNoiseToken[] = "fp-audio-noise-token";

}  // namespace switches""",
        """const char kFingerprintCanvasNoiseToken[] = "fp-canvas-noise-token";
const char kFingerprintAudioNoiseToken[] = "fp-audio-noise-token";

// Diagnostic-only API-usage tracer. See switches.h for details.
const char kFingerprintApiTrace[] = "fp-api-trace";

}  // namespace switches""",
    ),
    (
        "content/shell/browser/shell_content_browser_client.cc",
        """      switches::kExposeInternalsForTesting,
      switches::kFingerprintProfile,
      switches::kRunWebTests,""",
        """      switches::kExposeInternalsForTesting,
      switches::kFingerprintProfile,
      blink::switches::kFingerprintApiTrace,
      switches::kRunWebTests,""",
    ),
    (
        "third_party/blink/renderer/core/frame/navigator.cc",
        """#include "base/command_line.h"
#include "third_party/blink/public/common/switches.h"\n""",
        """#include "base/command_line.h"
#include "base/logging.h"
#include "third_party/blink/public/common/switches.h"\n""",
    ),
    (
        "third_party/blink/renderer/core/frame/navigator.cc",
        """#include "third_party/blink/renderer/platform/language.h"

namespace blink {

Navigator::Navigator(ExecutionContext* context) : NavigatorBase(context) {}

String Navigator::productSub() const {
  const std::string fp_override =""",
        """#include "third_party/blink/renderer/platform/language.h"

// Diagnostic-only: logs one line per call when --fp-api-trace is passed, so
// real-Chrome-vs-content_shell API-touch behavior can be diffed. See
// switches.h for details. No-op (single HasSwitch() check) otherwise.
#define FP_API_TRACE(name)                                    \\
  do {                                                         \\
    if (base::CommandLine::ForCurrentProcess()->HasSwitch(      \\
            switches::kFingerprintApiTrace)) {                  \\
      LOG(INFO) << "[FP_API_TRACE] " name;                      \\
    }                                                            \\
  } while (0)

namespace blink {

Navigator::Navigator(ExecutionContext* context) : NavigatorBase(context) {}

String Navigator::productSub() const {
  FP_API_TRACE("navigator.productSub");
  const std::string fp_override =""",
    ),
    (
        "third_party/blink/renderer/core/frame/navigator.cc",
        """String Navigator::vendor() const {
  const std::string fp_override =""",
        """String Navigator::vendor() const {
  FP_API_TRACE("navigator.vendor");
  const std::string fp_override =""",
    ),
    (
        "third_party/blink/renderer/core/frame/navigator.cc",
        """String Navigator::platform() const {
  const std::string fp_override =""",
        """String Navigator::platform() const {
  FP_API_TRACE("navigator.platform");
  const std::string fp_override =""",
    ),
    (
        "third_party/blink/renderer/core/frame/navigator.cc",
        """bool Navigator::webdriver() const {
  if (RuntimeEnabledFeatures::AutomationControlledEnabled())""",
        """bool Navigator::webdriver() const {
  FP_API_TRACE("navigator.webdriver");
  if (RuntimeEnabledFeatures::AutomationControlledEnabled())""",
    ),
    (
        "third_party/blink/renderer/core/frame/navigator_concurrent_hardware.cc",
        """#include "base/command_line.h"
#include "base/strings/string_number_conversions.h"
#include "base/system/sys_info.h"
#include "third_party/blink/public/common/switches.h"

namespace blink {

unsigned NavigatorConcurrentHardware::hardwareConcurrency() const {
  const std::string fp_override =""",
        """#include "base/command_line.h"
#include "base/logging.h"
#include "base/strings/string_number_conversions.h"
#include "base/system/sys_info.h"
#include "third_party/blink/public/common/switches.h"

// See navigator.cc for FP_API_TRACE documentation.
#define FP_API_TRACE(name)                                    \\
  do {                                                         \\
    if (base::CommandLine::ForCurrentProcess()->HasSwitch(      \\
            switches::kFingerprintApiTrace)) {                  \\
      LOG(INFO) << "[FP_API_TRACE] " name;                      \\
    }                                                            \\
  } while (0)

namespace blink {

unsigned NavigatorConcurrentHardware::hardwareConcurrency() const {
  FP_API_TRACE("navigator.hardwareConcurrency");
  const std::string fp_override =""",
    ),
    (
        "third_party/blink/renderer/core/frame/navigator_device_memory.cc",
        """#include "base/command_line.h"
#include "base/strings/string_number_conversions.h"
#include "third_party/blink/public/common/device_memory/approximated_device_memory.h"
#include "third_party/blink/public/common/switches.h"
#include "third_party/blink/public/mojom/use_counter/metrics/web_feature.mojom-shared.h"
#include "third_party/blink/renderer/core/dom/document.h"
#include "third_party/blink/renderer/core/frame/local_dom_window.h"

namespace blink {

float NavigatorDeviceMemory::deviceMemory() const {
  const std::string fp_override =""",
        """#include "base/command_line.h"
#include "base/logging.h"
#include "base/strings/string_number_conversions.h"
#include "third_party/blink/public/common/device_memory/approximated_device_memory.h"
#include "third_party/blink/public/common/switches.h"
#include "third_party/blink/public/mojom/use_counter/metrics/web_feature.mojom-shared.h"
#include "third_party/blink/renderer/core/dom/document.h"
#include "third_party/blink/renderer/core/frame/local_dom_window.h"

// See navigator.cc for FP_API_TRACE documentation.
#define FP_API_TRACE(name)                                    \\
  do {                                                         \\
    if (base::CommandLine::ForCurrentProcess()->HasSwitch(      \\
            switches::kFingerprintApiTrace)) {                  \\
      LOG(INFO) << "[FP_API_TRACE] " name;                      \\
    }                                                            \\
  } while (0)

namespace blink {

float NavigatorDeviceMemory::deviceMemory() const {
  FP_API_TRACE("navigator.deviceMemory");
  const std::string fp_override =""",
    ),
    (
        "third_party/blink/renderer/modules/plugins/dom_plugin_array.cc",
        """#include "base/command_line.h"
#include "third_party/blink/public/common/features.h"
#include "third_party/blink/public/common/switches.h"
#include "third_party/blink/renderer/core/frame/local_dom_window.h"
#include "third_party/blink/renderer/core/frame/local_frame.h"
#include "third_party/blink/renderer/core/frame/navigator.h"
#include "third_party/blink/renderer/core/page/page.h"
#include "third_party/blink/renderer/core/page/plugin_data.h"
#include "third_party/blink/renderer/modules/plugins/dom_mime_type_array.h"
#include "third_party/blink/renderer/modules/plugins/navigator_plugins.h"
#include "third_party/blink/renderer/platform/heap/garbage_collected.h"
#include "third_party/blink/renderer/platform/wtf/text/atomic_string.h"
#include "third_party/blink/renderer/platform/wtf/vector.h"

namespace blink {""",
        """#include "base/command_line.h"
#include "base/logging.h"
#include "third_party/blink/public/common/features.h"
#include "third_party/blink/public/common/switches.h"
#include "third_party/blink/renderer/core/frame/local_dom_window.h"
#include "third_party/blink/renderer/core/frame/local_frame.h"
#include "third_party/blink/renderer/core/frame/navigator.h"
#include "third_party/blink/renderer/core/page/page.h"
#include "third_party/blink/renderer/core/page/plugin_data.h"
#include "third_party/blink/renderer/modules/plugins/dom_mime_type_array.h"
#include "third_party/blink/renderer/modules/plugins/navigator_plugins.h"
#include "third_party/blink/renderer/platform/heap/garbage_collected.h"
#include "third_party/blink/renderer/platform/wtf/text/atomic_string.h"
#include "third_party/blink/renderer/platform/wtf/vector.h"

// See navigator.cc for FP_API_TRACE documentation.
#define FP_API_TRACE(name)                                    \\
  do {                                                         \\
    if (base::CommandLine::ForCurrentProcess()->HasSwitch(      \\
            switches::kFingerprintApiTrace)) {                  \\
      LOG(INFO) << "[FP_API_TRACE] " name;                      \\
    }                                                            \\
  } while (0)

namespace blink {""",
    ),
    (
        "third_party/blink/renderer/modules/plugins/dom_plugin_array.cc",
        """bool DOMPluginArray::IsPdfViewerAvailable() {
  // Fingerprint profile override:""",
        """bool DOMPluginArray::IsPdfViewerAvailable() {
  FP_API_TRACE("navigator.plugins/mimeTypes/pdfViewerEnabled");
  // Fingerprint profile override:""",
    ),
    (
        "third_party/blink/renderer/core/frame/screen.cc",
        """#include "base/command_line.h"
#include "base/numerics/safe_conversions.h"
#include "base/strings/string_number_conversions.h"
#include "services/network/public/mojom/permissions_policy/permissions_policy_feature.mojom-blink.h"
#include "third_party/blink/public/common/switches.h"\n""",
        """#include "base/command_line.h"
#include "base/logging.h"
#include "base/numerics/safe_conversions.h"
#include "base/strings/string_number_conversions.h"
#include "services/network/public/mojom/permissions_policy/permissions_policy_feature.mojom-blink.h"
#include "third_party/blink/public/common/switches.h"\n""",
    ),
    (
        "third_party/blink/renderer/core/frame/screen.cc",
        """#include "ui/display/screen_info.h"
#include "ui/display/screen_infos.h"

namespace blink {""",
        """#include "ui/display/screen_info.h"
#include "ui/display/screen_infos.h"

// See navigator.cc for FP_API_TRACE documentation.
#define FP_API_TRACE(name)                                    \\
  do {                                                         \\
    if (base::CommandLine::ForCurrentProcess()->HasSwitch(      \\
            switches::kFingerprintApiTrace)) {                  \\
      LOG(INFO) << "[FP_API_TRACE] " name;                      \\
    }                                                            \\
  } while (0)

namespace blink {""",
    ),
    (
        "third_party/blink/renderer/core/frame/screen.cc",
        """int Screen::height() const {
  if (!DomWindow())
    return 0;
  return GetRect(/*available=*/false).height();
}

int Screen::width() const {
  if (!DomWindow())
    return 0;
  return GetRect(/*available=*/false).width();
}

unsigned Screen::colorDepth() const {""",
        """int Screen::height() const {
  FP_API_TRACE("screen.height");
  if (!DomWindow())
    return 0;
  return GetRect(/*available=*/false).height();
}

int Screen::width() const {
  FP_API_TRACE("screen.width");
  if (!DomWindow())
    return 0;
  return GetRect(/*available=*/false).width();
}

unsigned Screen::colorDepth() const {
  FP_API_TRACE("screen.colorDepth");""",
    ),
    (
        "third_party/blink/renderer/core/frame/screen.cc",
        """int Screen::availLeft() const {
  if (!DomWindow())
    return 0;
  return GetRect(/*available=*/true).x();
}

int Screen::availTop() const {
  if (!DomWindow())
    return 0;
  return GetRect(/*available=*/true).y();
}

int Screen::availHeight() const {
  if (!DomWindow())
    return 0;
  return GetRect(/*available=*/true).height();
}

int Screen::availWidth() const {
  if (!DomWindow())
    return 0;
  return GetRect(/*available=*/true).width();
}""",
        """int Screen::availLeft() const {
  FP_API_TRACE("screen.availLeft");
  if (!DomWindow())
    return 0;
  return GetRect(/*available=*/true).x();
}

int Screen::availTop() const {
  FP_API_TRACE("screen.availTop");
  if (!DomWindow())
    return 0;
  return GetRect(/*available=*/true).y();
}

int Screen::availHeight() const {
  FP_API_TRACE("screen.availHeight");
  if (!DomWindow())
    return 0;
  return GetRect(/*available=*/true).height();
}

int Screen::availWidth() const {
  FP_API_TRACE("screen.availWidth");
  if (!DomWindow())
    return 0;
  return GetRect(/*available=*/true).width();
}""",
    ),
    (
        "third_party/blink/renderer/modules/webgl/webgl_rendering_context_base.cc",
        """#include "base/command_line.h"
#include "base/compiler_specific.h"
#include "base/feature_list.h"\n""",
        """#include "base/command_line.h"
#include "base/compiler_specific.h"
#include "base/feature_list.h"
#include "base/logging.h"\n""",
    ),
    (
        "third_party/blink/renderer/modules/webgl/webgl_rendering_context_base.cc",
        """  GetCurrentUnpackState(params)

namespace blink {""",
        """  GetCurrentUnpackState(params)

// See third_party/blink/renderer/core/frame/navigator.cc for FP_API_TRACE
// documentation.
#define FP_API_TRACE(name)                                    \\
  do {                                                         \\
    if (base::CommandLine::ForCurrentProcess()->HasSwitch(      \\
            switches::kFingerprintApiTrace)) {                  \\
      LOG(INFO) << "[FP_API_TRACE] " name;                      \\
    }                                                            \\
  } while (0)

namespace blink {""",
    ),
    (
        "third_party/blink/renderer/modules/webgl/webgl_rendering_context_base.cc",
        """    case WebGLDebugRendererInfo::kUnmaskedRendererWebgl:
      if (ExtensionEnabled(kWebGLDebugRendererInfoName)) {
        // Fingerprint profile: report a stable, profile-defined GPU string""",
        """    case WebGLDebugRendererInfo::kUnmaskedRendererWebgl:
      FP_API_TRACE("WebGLRenderingContext.getParameter(UNMASKED_RENDERER_WEBGL)");
      if (ExtensionEnabled(kWebGLDebugRendererInfoName)) {
        // Fingerprint profile: report a stable, profile-defined GPU string""",
    ),
    (
        "third_party/blink/renderer/modules/webgl/webgl_rendering_context_base.cc",
        """    case WebGLDebugRendererInfo::kUnmaskedVendorWebgl:
      if (ExtensionEnabled(kWebGLDebugRendererInfoName)) {
        const std::string vendor_override =""",
        """    case WebGLDebugRendererInfo::kUnmaskedVendorWebgl:
      FP_API_TRACE("WebGLRenderingContext.getParameter(UNMASKED_VENDOR_WEBGL)");
      if (ExtensionEnabled(kWebGLDebugRendererInfoName)) {
        const std::string vendor_override =""",
    ),
    (
        "third_party/blink/renderer/core/canvas_interventions/fingerprint_stable_noise.h",
        """CORE_EXPORT std::optional<NoiseToken> FingerprintCanvasNoiseToken();
CORE_EXPORT void MaybeApplyFingerprintNoiseToImageData(ImageData* image_data);
CORE_EXPORT void MaybeApplyFingerprintNoiseToPixels(base::span<uint8_t> pixels,
                                                    int width,
                                                    int height);

}  // namespace blink""",
        """CORE_EXPORT std::optional<NoiseToken> FingerprintCanvasNoiseToken();
CORE_EXPORT void MaybeApplyFingerprintNoiseToImageData(ImageData* image_data);
CORE_EXPORT void MaybeApplyFingerprintNoiseToPixels(base::span<uint8_t> pixels,
                                                    int width,
                                                    int height);

// Diagnostic-only: logs "[FP_API_TRACE] <name>" via LOG(INFO) when
// --fp-api-trace is passed on the command line, so real-Chrome-vs-
// content_shell API-touch behavior can be diffed. No-op (single cached
// HasSwitch() check) otherwise. Exposed here (rather than a new header) so
// call sites in html_canvas_element.cc / base_rendering_context_2d.cc, which
// already include this header for the noise helpers above, don't need any
// new includes.
CORE_EXPORT void FingerprintApiTrace(const char* name);

}  // namespace blink""",
    ),
    (
        "third_party/blink/renderer/core/canvas_interventions/fingerprint_stable_noise.cc",
        """#include "base/command_line.h"
#include "base/containers/span.h"
#include "base/strings/string_number_conversions.h"\n""",
        """#include "base/command_line.h"
#include "base/containers/span.h"
#include "base/logging.h"
#include "base/strings/string_number_conversions.h"\n""",
    ),
    (
        "third_party/blink/renderer/core/canvas_interventions/fingerprint_stable_noise.cc",
        """void MaybeApplyFingerprintNoiseToImageData(ImageData* image_data) {""",
        """void FingerprintApiTrace(const char* name) {
  static const bool enabled =
      base::CommandLine::ForCurrentProcess()->HasSwitch(
          switches::kFingerprintApiTrace);
  if (enabled) {
    LOG(INFO) << "[FP_API_TRACE] " << name;
  }
}

void MaybeApplyFingerprintNoiseToImageData(ImageData* image_data) {""",
    ),
    (
        "third_party/blink/renderer/core/html/canvas/html_canvas_element.cc",
        """String HTMLCanvasElement::ToDataURLInternal(
    const String& mime_type,
    const double& quality,
    SourceDrawingBuffer source_buffer) const {
  base::TimeTicks start_time = base::TimeTicks::Now();""",
        """String HTMLCanvasElement::ToDataURLInternal(
    const String& mime_type,
    const double& quality,
    SourceDrawingBuffer source_buffer) const {
  FingerprintApiTrace("canvas.toDataURL");
  base::TimeTicks start_time = base::TimeTicks::Now();""",
    ),
    (
        "third_party/blink/renderer/modules/canvas/canvas2d/base_rendering_context_2d.cc",
        """    ImageDataSettings* image_data_settings,
    ExceptionState& exception_state) {
  if (!base::CheckMul(sw, sh).IsValid<int>()) {""",
        """    ImageDataSettings* image_data_settings,
    ExceptionState& exception_state) {
  FingerprintApiTrace("ctx2d.getImageData");
  if (!base::CheckMul(sw, sh).IsValid<int>()) {""",
    ),
    (
        "third_party/blink/renderer/modules/webaudio/fingerprint_audio_stable_noise.h",
        """MODULES_EXPORT std::optional<NoiseToken> FingerprintAudioNoiseToken();
MODULES_EXPORT void MaybeApplyFingerprintNoiseToAudioBuffer(AudioBuffer* buffer);

}  // namespace blink""",
        """MODULES_EXPORT std::optional<NoiseToken> FingerprintAudioNoiseToken();
MODULES_EXPORT void MaybeApplyFingerprintNoiseToAudioBuffer(AudioBuffer* buffer);

// Diagnostic-only: see fingerprint_stable_noise.h (canvas) for the same
// facility. Duplicated here rather than shared to avoid a new cross-module
// dependency; both just gate on --fp-api-trace and LOG(INFO).
MODULES_EXPORT void FingerprintApiTraceAudio(const char* name);

}  // namespace blink""",
    ),
    (
        "third_party/blink/renderer/modules/webaudio/fingerprint_audio_stable_noise.cc",
        """#include "base/command_line.h"
#include "base/strings/string_number_conversions.h"\n""",
        """#include "base/command_line.h"
#include "base/logging.h"
#include "base/strings/string_number_conversions.h"\n""",
    ),
    (
        "third_party/blink/renderer/modules/webaudio/fingerprint_audio_stable_noise.cc",
        """void MaybeApplyFingerprintNoiseToAudioBuffer(AudioBuffer* buffer) {""",
        """void FingerprintApiTraceAudio(const char* name) {
  static const bool enabled =
      base::CommandLine::ForCurrentProcess()->HasSwitch(
          switches::kFingerprintApiTrace);
  if (enabled) {
    LOG(INFO) << "[FP_API_TRACE] " << name;
  }
}

void MaybeApplyFingerprintNoiseToAudioBuffer(AudioBuffer* buffer) {""",
    ),
    (
        "third_party/blink/renderer/modules/webaudio/offline_audio_context.cc",
        """void OfflineAudioContext::FireCompletionEvent() {
  DCHECK(IsMainThread());""",
        """void OfflineAudioContext::FireCompletionEvent() {
  FingerprintApiTraceAudio("OfflineAudioContext.FireCompletionEvent");
  DCHECK(IsMainThread());""",
    ),
    (
        "content/shell/browser/shell_permission_manager.cc",
        """#include "base/command_line.h"
#include "base/functional/callback.h"
#include "components/content_settings/core/common/features.h"
#include "content/public/browser/permission_controller.h"
#include "content/public/browser/permission_result.h"
#include "content/public/browser/render_frame_host.h"
#include "content/public/common/content_switches.h"
#include "content/shell/common/shell_fingerprint_profile.h"
#include "content/shell/common/shell_switches.h"
#include "media/base/media_switches.h"
#include "third_party/blink/public/common/features.h"
#include "third_party/blink/public/common/permissions/permission_utils.h"
#include "url/origin.h"\n""",
        """#include "base/command_line.h"
#include "base/functional/callback.h"
#include "base/logging.h"
#include "components/content_settings/core/common/features.h"
#include "content/public/browser/permission_controller.h"
#include "content/public/browser/permission_result.h"
#include "content/public/browser/render_frame_host.h"
#include "content/public/common/content_switches.h"
#include "content/shell/common/shell_fingerprint_profile.h"
#include "content/shell/common/shell_switches.h"
#include "media/base/media_switches.h"
#include "third_party/blink/public/common/features.h"
#include "third_party/blink/public/common/permissions/permission_utils.h"
#include "third_party/blink/public/common/switches.h"
#include "url/origin.h"\n""",
    ),
    (
        "content/shell/browser/shell_permission_manager.cc",
        """    const GURL& embedding_origin) {
  base::CommandLine* command_line = base::CommandLine::ForCurrentProcess();
  const auto permission_type =""",
        """    const GURL& embedding_origin) {
  base::CommandLine* command_line = base::CommandLine::ForCurrentProcess();
  if (command_line->HasSwitch(blink::switches::kFingerprintApiTrace)) {
    // Also the underlying path for Notification.permission (goes through
    // PermissionManager once ShellPlatformNotificationService exists).
    LOG(INFO) << "[FP_API_TRACE] navigator.permissions.query/Notification.permission";
  }
  const auto permission_type =""",
    ),
    (
        "content/shell/renderer/shell_render_frame_observer.cc",
        """#include "base/command_line.h"
#include "content/public/renderer/render_frame.h"
#include "content/public/renderer/render_frame_observer.h"
#if !defined(CONTENT_SHELL_MINIMAL_ROOT)
#include "content/shell/common/render_frame_test_helper.mojom.h"
#endif
#include "content/shell/common/shell_switches.h"\n""",
        """#include "base/command_line.h"
#include "base/logging.h"
#include "content/public/renderer/render_frame.h"
#include "content/public/renderer/render_frame_observer.h"
#if !defined(CONTENT_SHELL_MINIMAL_ROOT)
#include "content/shell/common/render_frame_test_helper.mojom.h"
#endif
#include "content/shell/common/shell_switches.h"
#include "third_party/blink/public/common/switches.h"\n""",
    ),
    (
        "content/shell/renderer/shell_render_frame_observer.cc",
        """namespace content {

namespace {

// Real (native) no-op function callbacks. Using v8::Function::New means these
// report "function () { [native code] }" to Function.prototype.toString, which
// matches how Chrome's own window.chrome members appear and avoids exposing a
// JS hook.
void ChromeNoop(const v8::FunctionCallbackInfo<v8::Value>& info) {}

// chrome.csi() returns a small timing object in real Chrome.
void ChromeCsi(const v8::FunctionCallbackInfo<v8::Value>& info) {
  v8::Isolate* isolate = info.GetIsolate();""",
        """namespace content {

namespace {

// Diagnostic-only: see third_party/blink/renderer/core/frame/navigator.cc for
// FP_API_TRACE documentation. Duplicated (rather than shared) because this
// file is in content/shell/renderer, which cannot depend on blink/renderer
// internals used elsewhere.
void FingerprintApiTraceWindowChrome(const std::string& name) {
  if (base::CommandLine::ForCurrentProcess()->HasSwitch(
          blink::switches::kFingerprintApiTrace)) {
    LOG(INFO) << "[FP_API_TRACE] window.chrome." << name;
  }
}

// Real (native) no-op function callbacks. Using v8::Function::New means these
// report "function () { [native code] }" to Function.prototype.toString, which
// matches how Chrome's own window.chrome members appear and avoids exposing a
// JS hook.
void ChromeNoop(const v8::FunctionCallbackInfo<v8::Value>& info) {
  if (info.Data()->IsString()) {
    v8::String::Utf8Value name(info.GetIsolate(), info.Data());
    FingerprintApiTraceWindowChrome(std::string(*name ? *name : "?"));
  }
}

// chrome.csi() returns a small timing object in real Chrome.
void ChromeCsi(const v8::FunctionCallbackInfo<v8::Value>& info) {
  FingerprintApiTraceWindowChrome("csi");
  v8::Isolate* isolate = info.GetIsolate();""",
    ),
    (
        "content/shell/renderer/shell_render_frame_observer.cc",
        """// chrome.loadTimes() returns a (deprecated) timing object in real Chrome.
void ChromeLoadTimes(const v8::FunctionCallbackInfo<v8::Value>& info) {
  v8::Isolate* isolate = info.GetIsolate();""",
        """// chrome.loadTimes() returns a (deprecated) timing object in real Chrome.
void ChromeLoadTimes(const v8::FunctionCallbackInfo<v8::Value>& info) {
  FingerprintApiTraceWindowChrome("loadTimes");
  v8::Isolate* isolate = info.GetIsolate();""",
    ),
    (
        "content/shell/renderer/shell_render_frame_observer.cc",
        """v8::Local<v8::Function> MakeNativeFunction(v8::Local<v8::Context> context,
                                           v8::FunctionCallback callback,
                                           const char* name) {
  v8::Isolate* isolate = v8::Isolate::GetCurrent();
  v8::Local<v8::Function> fn =
      v8::Function::New(context, callback).ToLocalChecked();
  fn->SetName(V8Str(isolate, name));
  return fn;
}""",
        """v8::Local<v8::Function> MakeNativeFunction(v8::Local<v8::Context> context,
                                           v8::FunctionCallback callback,
                                           const char* name) {
  v8::Isolate* isolate = v8::Isolate::GetCurrent();
  // Passing |name| as the callback's Data lets diagnostic-only callbacks
  // (ChromeNoop) identify which window.chrome.* member was invoked when
  // --fp-api-trace is set; it has no effect on the function's observable
  // JS behavior/shape.
  v8::Local<v8::Function> fn =
      v8::Function::New(context, callback, V8Str(isolate, name))
          .ToLocalChecked();
  fn->SetName(V8Str(isolate, name));
  return fn;
}""",
    ),
    (
        "third_party/blink/renderer/modules/speech/speech_synthesis.cc",
        """#include <tuple>

#include "build/build_config.h"
#include "third_party/blink/public/common/thread_safe_browser_interface_broker_proxy.h"
#include "third_party/blink/public/platform/browser_interface_broker_proxy.h"
#include "third_party/blink/public/platform/platform.h"
#include "third_party/blink/renderer/bindings/modules/v8/v8_speech_synthesis_error_event_init.h"
#include "third_party/blink/renderer/bindings/modules/v8/v8_speech_synthesis_event_init.h"
#include "third_party/blink/renderer/core/dom/document.h"
#include "third_party/blink/renderer/core/frame/deprecation/deprecation.h"
#include "third_party/blink/renderer/core/frame/local_dom_window.h"
#include "third_party/blink/renderer/core/frame/web_feature.h"
#include "third_party/blink/renderer/core/html/media/autoplay_policy.h"
#include "third_party/blink/renderer/core/timing/dom_window_performance.h"
#include "third_party/blink/renderer/core/timing/performance.h"
#include "third_party/blink/renderer/modules/speech/speech_synthesis_error_event.h"
#include "third_party/blink/renderer/modules/speech/speech_synthesis_event.h"
#include "third_party/blink/renderer/modules/speech/speech_synthesis_voice.h"
#include "third_party/blink/renderer/platform/instrumentation/use_counter.h"

namespace blink {""",
        """#include <tuple>

#include "base/command_line.h"
#include "base/logging.h"
#include "build/build_config.h"
#include "third_party/blink/public/common/switches.h"
#include "third_party/blink/public/common/thread_safe_browser_interface_broker_proxy.h"
#include "third_party/blink/public/platform/browser_interface_broker_proxy.h"
#include "third_party/blink/public/platform/platform.h"
#include "third_party/blink/renderer/bindings/modules/v8/v8_speech_synthesis_error_event_init.h"
#include "third_party/blink/renderer/bindings/modules/v8/v8_speech_synthesis_event_init.h"
#include "third_party/blink/renderer/core/dom/document.h"
#include "third_party/blink/renderer/core/frame/deprecation/deprecation.h"
#include "third_party/blink/renderer/core/frame/local_dom_window.h"
#include "third_party/blink/renderer/core/frame/web_feature.h"
#include "third_party/blink/renderer/core/html/media/autoplay_policy.h"
#include "third_party/blink/renderer/core/timing/dom_window_performance.h"
#include "third_party/blink/renderer/core/timing/performance.h"
#include "third_party/blink/renderer/modules/speech/speech_synthesis_error_event.h"
#include "third_party/blink/renderer/modules/speech/speech_synthesis_event.h"
#include "third_party/blink/renderer/modules/speech/speech_synthesis_voice.h"
#include "third_party/blink/renderer/platform/instrumentation/use_counter.h"

// See third_party/blink/renderer/core/frame/navigator.cc for FP_API_TRACE
// documentation.
#define FP_API_TRACE(name)                                    \\
  do {                                                         \\
    if (base::CommandLine::ForCurrentProcess()->HasSwitch(      \\
            switches::kFingerprintApiTrace)) {                  \\
      LOG(INFO) << "[FP_API_TRACE] " name;                      \\
    }                                                            \\
  } while (0)

namespace blink {""",
    ),
    (
        "third_party/blink/renderer/modules/speech/speech_synthesis.cc",
        """const HeapVector<Member<SpeechSynthesisVoice>>& SpeechSynthesis::getVoices() {
  // Kick off initialization here to ensure voice list gets populated.""",
        """const HeapVector<Member<SpeechSynthesisVoice>>& SpeechSynthesis::getVoices() {
  FP_API_TRACE("speechSynthesis.getVoices");
  // Kick off initialization here to ensure voice list gets populated.""",
    ),
]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src_root", help="path to the clean Chromium src/ checkout")
    ap.add_argument("--dry-run", action="store_true", help="report what would change without writing files")
    args = ap.parse_args()

    per_file = {}
    for rel_path, old, new in EDITS:
        per_file.setdefault(rel_path, []).append((old, new))

    ok, failed = 0, 0
    for rel_path, edits in per_file.items():
        full_path = os.path.join(args.src_root, rel_path)
        if not os.path.isfile(full_path):
            print(f"[SKIP] {rel_path}: file not found")
            failed += 1
            continue
        with open(full_path, "r", encoding="utf-8") as f:
            content = f.read()
        applied_here = 0
        for old, new in edits:
            count = content.count(old)
            if count == 0:
                print(f"[FAIL] {rel_path}: an expected snippet was not found "
                      f"(checkout revision may differ) -- see script source "
                      f"for the exact text, apply by hand if needed")
                failed += 1
                continue
            if count > 1:
                print(f"[FAIL] {rel_path}: expected snippet matched {count} times "
                      f"(ambiguous) -- skipping to avoid corrupting the file")
                failed += 1
                continue
            content = content.replace(old, new, 1)
            applied_here += 1
        if applied_here == len(edits):
            ok += 1
            if not args.dry_run:
                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(content)
            print(f"[{'DRY-RUN OK' if args.dry_run else 'OK'}] {rel_path}: "
                  f"{applied_here}/{len(edits)} edit(s) applied")
        else:
            print(f"[PARTIAL] {rel_path}: {applied_here}/{len(edits)} edit(s) applied "
                  f"-- {'not writing (dry-run)' if args.dry_run else 'NOT WRITTEN, fix by hand'}")

    print(f"\n{ok} file(s) fully OK, {failed} edit(s) failed across all files.")
    if failed:
        print("Files that failed: re-check the corresponding section in "
              "docs/e0488508e6-v2/status-015-api-usage-tracer.md and apply by hand.")
        sys.exit(1)


if __name__ == "__main__":
    main()
