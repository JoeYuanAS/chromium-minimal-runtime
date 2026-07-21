// Injected via CDP Page.addScriptToEvaluateOnNewDocument, so it runs before
// any page script (document_start equivalent) on every navigation in this tab.
// It wraps a curated list of high-value fingerprinting APIs with logging
// shims, WITHOUT changing return values, so page behavior (and the sensor's
// output) stays identical between runs -- we're only observing, not spoofing.
(function () {
  if (window.__apiHits) return;
  window.__apiHits = [];

  function record(name, kind, extra) {
    try {
      window.__apiHits.push({
        name: name,
        kind: kind,
        t: performance.now(),
        extra: extra,
      });
    } catch (e) {}
  }

  function wrapGetter(obj, prop, label) {
    try {
      var desc =
        Object.getOwnPropertyDescriptor(obj, prop) ||
        Object.getOwnPropertyDescriptor(Object.getPrototypeOf(obj), prop);
      if (!desc || !desc.get) return;
      var origGet = desc.get;
      Object.defineProperty(obj, prop, {
        configurable: true,
        enumerable: desc.enumerable,
        get: function () {
          record(label || prop, "get");
          return origGet.call(this);
        },
      });
    } catch (e) {}
  }

  function wrapMethod(obj, prop, label) {
    try {
      var orig = obj[prop];
      if (typeof orig !== "function") return;
      var wrapped = function () {
        record(label || prop, "call", arguments.length);
        return orig.apply(this, arguments);
      };
      wrapped.toString = function () {
        return orig.toString();
      };
      obj[prop] = wrapped;
    } catch (e) {}
  }

  // ---- navigator surface ----
  [
    "webdriver", "platform", "productSub", "vendor", "product",
    "hardwareConcurrency", "deviceMemory", "maxTouchPoints", "languages",
    "language", "userAgent", "plugins", "mimeTypes", "pdfViewerEnabled",
    "credentials", "bluetooth", "usb", "hid", "serial", "geolocation",
    "clipboard", "storage", "mediaDevices", "permissions", "serviceWorker",
    "userAgentData", "onLine", "cookieEnabled", "doNotTrack",
  ].forEach(function (p) {
    wrapGetter(Navigator.prototype, p, "navigator." + p);
  });
  ["vibrate", "sendBeacon", "getBattery", "getGamepads"].forEach(function (p) {
    wrapMethod(Navigator.prototype, p, "navigator." + p + "()");
  });

  // ---- window.chrome ----
  wrapGetter(window, "chrome", "window.chrome");
  try {
    if (window.chrome) {
      Object.keys(window.chrome).forEach(function (k) {
        wrapMethod(window.chrome, k, "window.chrome." + k + "()");
      });
      if (window.chrome.runtime) {
        Object.keys(window.chrome.runtime).forEach(function (k) {
          wrapMethod(window.chrome.runtime, k, "window.chrome.runtime." + k + "()");
        });
      }
    }
  } catch (e) {}

  // ---- screen / window geometry ----
  ["width", "height", "availWidth", "availHeight", "availLeft", "availTop",
   "colorDepth", "pixelDepth"].forEach(function (p) {
    wrapGetter(Screen.prototype, p, "screen." + p);
  });

  // ---- WebGL ----
  try { wrapMethod(WebGLRenderingContext.prototype, "getParameter", "WebGLRenderingContext.getParameter"); } catch (e) {}
  try { wrapMethod(WebGL2RenderingContext.prototype, "getParameter", "WebGL2RenderingContext.getParameter"); } catch (e) {}
  try { wrapMethod(WebGLRenderingContext.prototype, "getExtension", "WebGLRenderingContext.getExtension"); } catch (e) {}

  // ---- canvas / audio ----
  try { wrapMethod(HTMLCanvasElement.prototype, "toDataURL", "canvas.toDataURL"); } catch (e) {}
  try { wrapMethod(HTMLCanvasElement.prototype, "toBlob", "canvas.toBlob"); } catch (e) {}
  try { wrapMethod(CanvasRenderingContext2D.prototype, "getImageData", "ctx2d.getImageData"); } catch (e) {}
  try { wrapMethod(OfflineAudioContext.prototype, "startRendering", "OfflineAudioContext.startRendering"); } catch (e) {}
  try { wrapMethod(AudioContext.prototype, "createOscillator", "AudioContext.createOscillator"); } catch (e) {}

  // ---- speech / media / permissions ----
  try { wrapMethod(SpeechSynthesis.prototype, "getVoices", "speechSynthesis.getVoices"); } catch (e) {}
  try { wrapGetter(Notification, "permission", "Notification.permission"); } catch (e) {}
  try { wrapMethod(Permissions.prototype, "query", "navigator.permissions.query"); } catch (e) {}
  try { wrapMethod(MediaDevices.prototype, "enumerateDevices", "mediaDevices.enumerateDevices"); } catch (e) {}
  try { wrapMethod(MediaDevices.prototype, "getUserMedia", "mediaDevices.getUserMedia"); } catch (e) {}

  // ---- RTCPeerConnection (constructor call) ----
  try {
    var OrigRTC = window.RTCPeerConnection;
    if (OrigRTC) {
      var WrappedRTC = function () {
        record("RTCPeerConnection", "construct");
        var inst = Object.create(OrigRTC.prototype);
        return OrigRTC.apply(inst, arguments) || inst;
      };
      WrappedRTC.prototype = OrigRTC.prototype;
      window.RTCPeerConnection = WrappedRTC;
    }
  } catch (e) {}

  // ---- reflection / anti-tamper probes ----
  try { wrapMethod(Function.prototype, "toString", "Function.prototype.toString"); } catch (e) {}
  try { wrapMethod(window, "atob", "window.atob"); } catch (e) {}
  try { wrapMethod(window, "btoa", "window.btoa"); } catch (e) {}

  // ---- device motion / touch existence probes (best-effort: hook the event
  // constructors themselves; 'x in window' checks can't be intercepted) ----
  ["DeviceMotionEvent", "DeviceOrientationEvent"].forEach(function (ctorName) {
    try {
      var Orig = window[ctorName];
      if (!Orig) return;
      var Wrapped = function () {
        record(ctorName, "construct");
        return Orig.apply(this, arguments);
      };
      Wrapped.prototype = Orig.prototype;
      window[ctorName] = Wrapped;
    } catch (e) {}
  });

  // ---- snapshot API-hit log at the moment the sensor-bearing request fires ----
  function isSensorRequest(url) {
    return /microsummary|recaptcha|akam\//i.test(url);
  }

  var origXhrOpen = XMLHttpRequest.prototype.open;
  XMLHttpRequest.prototype.open = function (method, url) {
    this.__probeUrl = url;
    return origXhrOpen.apply(this, arguments);
  };
  var origXhrSend = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.send = function () {
    if (this.__probeUrl && isSensorRequest(this.__probeUrl) && !window.__apiHitsAtSensorRequest) {
      window.__apiHitsAtSensorRequest = window.__apiHits.slice();
      window.__sensorRequestUrl = this.__probeUrl;
    }
    return origXhrSend.apply(this, arguments);
  };

  var origFetch = window.fetch;
  if (origFetch) {
    window.fetch = function (input, init) {
      var url = typeof input === "string" ? input : (input && input.url) || "";
      if (isSensorRequest(url) && !window.__apiHitsAtSensorRequest) {
        window.__apiHitsAtSensorRequest = window.__apiHits.slice();
        window.__sensorRequestUrl = url;
      }
      return origFetch.apply(this, arguments);
    };
  }
})();
