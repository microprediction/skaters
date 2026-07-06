var __defProp = Object.defineProperty;
var __getOwnPropNames = Object.getOwnPropertyNames;
var __esm = (fn, res, err) => function __init() {
  if (err) throw err[0];
  try {
    return fn && (res = (0, fn[__getOwnPropNames(fn)[0]])(fn = 0)), res;
  } catch (e6) {
    throw err = [e6], e6;
  }
};
var __export = (target, all) => {
  for (var name2 in all)
    __defProp(target, name2, { get: all[name2], enumerable: true });
};

// node_modules/esbuild-plugin-polyfill-node/polyfills/__dirname.js
var init_dirname = __esm({
  "node_modules/esbuild-plugin-polyfill-node/polyfills/__dirname.js"() {
  }
});

// node_modules/@jspm/core/nodelibs/browser/process.js
var process_exports = {};
__export(process_exports, {
  _debugEnd: () => _debugEnd,
  _debugProcess: () => _debugProcess,
  _events: () => _events,
  _eventsCount: () => _eventsCount,
  _exiting: () => _exiting,
  _fatalExceptions: () => _fatalExceptions,
  _getActiveHandles: () => _getActiveHandles,
  _getActiveRequests: () => _getActiveRequests,
  _kill: () => _kill,
  _linkedBinding: () => _linkedBinding,
  _maxListeners: () => _maxListeners,
  _preload_modules: () => _preload_modules,
  _rawDebug: () => _rawDebug,
  _startProfilerIdleNotifier: () => _startProfilerIdleNotifier,
  _stopProfilerIdleNotifier: () => _stopProfilerIdleNotifier,
  _tickCallback: () => _tickCallback,
  abort: () => abort,
  addListener: () => addListener,
  allowedNodeEnvironmentFlags: () => allowedNodeEnvironmentFlags,
  arch: () => arch,
  argv: () => argv,
  argv0: () => argv0,
  assert: () => assert,
  binding: () => binding,
  browser: () => browser,
  chdir: () => chdir,
  config: () => config,
  cpuUsage: () => cpuUsage,
  cwd: () => cwd,
  debugPort: () => debugPort,
  default: () => process,
  dlopen: () => dlopen,
  domain: () => domain,
  emit: () => emit,
  emitWarning: () => emitWarning,
  env: () => env,
  execArgv: () => execArgv,
  execPath: () => execPath,
  exit: () => exit,
  features: () => features,
  hasUncaughtExceptionCaptureCallback: () => hasUncaughtExceptionCaptureCallback,
  hrtime: () => hrtime,
  kill: () => kill,
  listeners: () => listeners,
  memoryUsage: () => memoryUsage,
  moduleLoadList: () => moduleLoadList,
  nextTick: () => nextTick,
  off: () => off,
  on: () => on,
  once: () => once,
  openStdin: () => openStdin,
  pid: () => pid,
  platform: () => platform,
  ppid: () => ppid,
  prependListener: () => prependListener,
  prependOnceListener: () => prependOnceListener,
  reallyExit: () => reallyExit,
  release: () => release,
  removeAllListeners: () => removeAllListeners,
  removeListener: () => removeListener,
  resourceUsage: () => resourceUsage,
  setSourceMapsEnabled: () => setSourceMapsEnabled,
  setUncaughtExceptionCaptureCallback: () => setUncaughtExceptionCaptureCallback,
  stderr: () => stderr,
  stdin: () => stdin,
  stdout: () => stdout,
  title: () => title,
  umask: () => umask,
  uptime: () => uptime,
  version: () => version,
  versions: () => versions
});
function unimplemented(name2) {
  throw new Error("Node.js process " + name2 + " is not supported by JSPM core outside of Node.js");
}
function cleanUpNextTick() {
  if (!draining || !currentQueue)
    return;
  draining = false;
  if (currentQueue.length) {
    queue = currentQueue.concat(queue);
  } else {
    queueIndex = -1;
  }
  if (queue.length)
    drainQueue();
}
function drainQueue() {
  if (draining)
    return;
  var timeout = setTimeout(cleanUpNextTick, 0);
  draining = true;
  var len = queue.length;
  while (len) {
    currentQueue = queue;
    queue = [];
    while (++queueIndex < len) {
      if (currentQueue)
        currentQueue[queueIndex].run();
    }
    queueIndex = -1;
    len = queue.length;
  }
  currentQueue = null;
  draining = false;
  clearTimeout(timeout);
}
function nextTick(fun) {
  var args = new Array(arguments.length - 1);
  if (arguments.length > 1) {
    for (var i6 = 1; i6 < arguments.length; i6++)
      args[i6 - 1] = arguments[i6];
  }
  queue.push(new Item(fun, args));
  if (queue.length === 1 && !draining)
    setTimeout(drainQueue, 0);
}
function Item(fun, array) {
  this.fun = fun;
  this.array = array;
}
function noop() {
}
function _linkedBinding(name2) {
  unimplemented("_linkedBinding");
}
function dlopen(name2) {
  unimplemented("dlopen");
}
function _getActiveRequests() {
  return [];
}
function _getActiveHandles() {
  return [];
}
function assert(condition, message) {
  if (!condition) throw new Error(message || "assertion error");
}
function hasUncaughtExceptionCaptureCallback() {
  return false;
}
function uptime() {
  return _performance.now() / 1e3;
}
function hrtime(previousTimestamp) {
  var baseNow = Math.floor((Date.now() - _performance.now()) * 1e-3);
  var clocktime = _performance.now() * 1e-3;
  var seconds = Math.floor(clocktime) + baseNow;
  var nanoseconds = Math.floor(clocktime % 1 * 1e9);
  if (previousTimestamp) {
    seconds = seconds - previousTimestamp[0];
    nanoseconds = nanoseconds - previousTimestamp[1];
    if (nanoseconds < 0) {
      seconds--;
      nanoseconds += nanoPerSec;
    }
  }
  return [seconds, nanoseconds];
}
function on() {
  return process;
}
function listeners(name2) {
  return [];
}
var queue, draining, currentQueue, queueIndex, title, arch, platform, env, argv, execArgv, version, versions, emitWarning, binding, umask, cwd, chdir, release, browser, _rawDebug, moduleLoadList, domain, _exiting, config, reallyExit, _kill, cpuUsage, resourceUsage, memoryUsage, kill, exit, openStdin, allowedNodeEnvironmentFlags, features, _fatalExceptions, setUncaughtExceptionCaptureCallback, _tickCallback, _debugProcess, _debugEnd, _startProfilerIdleNotifier, _stopProfilerIdleNotifier, stdout, stderr, stdin, abort, pid, ppid, execPath, debugPort, argv0, _preload_modules, setSourceMapsEnabled, _performance, nowOffset, nanoPerSec, _maxListeners, _events, _eventsCount, addListener, once, off, removeListener, removeAllListeners, emit, prependListener, prependOnceListener, process;
var init_process = __esm({
  "node_modules/@jspm/core/nodelibs/browser/process.js"() {
    init_dirname();
    init_buffer2();
    init_process2();
    queue = [];
    draining = false;
    queueIndex = -1;
    Item.prototype.run = function() {
      this.fun.apply(null, this.array);
    };
    title = "browser";
    arch = "x64";
    platform = "browser";
    env = {
      PATH: "/usr/bin",
      LANG: typeof navigator !== "undefined" ? navigator.language + ".UTF-8" : void 0,
      PWD: "/",
      HOME: "/home",
      TMP: "/tmp"
    };
    argv = ["/usr/bin/node"];
    execArgv = [];
    version = "v16.8.0";
    versions = {};
    emitWarning = function(message, type) {
      console.warn((type ? type + ": " : "") + message);
    };
    binding = function(name2) {
      unimplemented("binding");
    };
    umask = function(mask) {
      return 0;
    };
    cwd = function() {
      return "/";
    };
    chdir = function(dir) {
    };
    release = {
      name: "node",
      sourceUrl: "",
      headersUrl: "",
      libUrl: ""
    };
    browser = true;
    _rawDebug = noop;
    moduleLoadList = [];
    domain = {};
    _exiting = false;
    config = {};
    reallyExit = noop;
    _kill = noop;
    cpuUsage = function() {
      return {};
    };
    resourceUsage = cpuUsage;
    memoryUsage = cpuUsage;
    kill = noop;
    exit = noop;
    openStdin = noop;
    allowedNodeEnvironmentFlags = {};
    features = {
      inspector: false,
      debug: false,
      uv: false,
      ipv6: false,
      tls_alpn: false,
      tls_sni: false,
      tls_ocsp: false,
      tls: false,
      cached_builtins: true
    };
    _fatalExceptions = noop;
    setUncaughtExceptionCaptureCallback = noop;
    _tickCallback = noop;
    _debugProcess = noop;
    _debugEnd = noop;
    _startProfilerIdleNotifier = noop;
    _stopProfilerIdleNotifier = noop;
    stdout = void 0;
    stderr = void 0;
    stdin = void 0;
    abort = noop;
    pid = 2;
    ppid = 1;
    execPath = "/bin/usr/node";
    debugPort = 9229;
    argv0 = "node";
    _preload_modules = [];
    setSourceMapsEnabled = noop;
    _performance = {
      now: typeof performance !== "undefined" ? performance.now.bind(performance) : void 0,
      timing: typeof performance !== "undefined" ? performance.timing : void 0
    };
    if (_performance.now === void 0) {
      nowOffset = Date.now();
      if (_performance.timing && _performance.timing.navigationStart) {
        nowOffset = _performance.timing.navigationStart;
      }
      _performance.now = () => Date.now() - nowOffset;
    }
    nanoPerSec = 1e9;
    hrtime.bigint = function(time) {
      var diff = hrtime(time);
      if (typeof BigInt === "undefined") {
        return diff[0] * nanoPerSec + diff[1];
      }
      return BigInt(diff[0] * nanoPerSec) + BigInt(diff[1]);
    };
    _maxListeners = 10;
    _events = {};
    _eventsCount = 0;
    addListener = on;
    once = on;
    off = on;
    removeListener = on;
    removeAllListeners = on;
    emit = noop;
    prependListener = on;
    prependOnceListener = on;
    process = {
      version,
      versions,
      arch,
      platform,
      browser,
      release,
      _rawDebug,
      moduleLoadList,
      binding,
      _linkedBinding,
      _events,
      _eventsCount,
      _maxListeners,
      on,
      addListener,
      once,
      off,
      removeListener,
      removeAllListeners,
      emit,
      prependListener,
      prependOnceListener,
      listeners,
      domain,
      _exiting,
      config,
      dlopen,
      uptime,
      _getActiveRequests,
      _getActiveHandles,
      reallyExit,
      _kill,
      cpuUsage,
      resourceUsage,
      memoryUsage,
      kill,
      exit,
      openStdin,
      allowedNodeEnvironmentFlags,
      assert,
      features,
      _fatalExceptions,
      setUncaughtExceptionCaptureCallback,
      hasUncaughtExceptionCaptureCallback,
      emitWarning,
      nextTick,
      _tickCallback,
      _debugProcess,
      _debugEnd,
      _startProfilerIdleNotifier,
      _stopProfilerIdleNotifier,
      stdout,
      stdin,
      stderr,
      abort,
      umask,
      chdir,
      cwd,
      env,
      title,
      argv,
      execArgv,
      pid,
      ppid,
      execPath,
      debugPort,
      hrtime,
      argv0,
      _preload_modules,
      setSourceMapsEnabled
    };
  }
});

// node_modules/esbuild-plugin-polyfill-node/polyfills/process.js
var init_process2 = __esm({
  "node_modules/esbuild-plugin-polyfill-node/polyfills/process.js"() {
    init_process();
  }
});

// node_modules/@jspm/core/nodelibs/browser/chunk-DtuTasat.js
function dew$2() {
  if (_dewExec$2) return exports$2;
  _dewExec$2 = true;
  exports$2.byteLength = byteLength;
  exports$2.toByteArray = toByteArray;
  exports$2.fromByteArray = fromByteArray;
  var lookup = [];
  var revLookup = [];
  var Arr = typeof Uint8Array !== "undefined" ? Uint8Array : Array;
  var code = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
  for (var i6 = 0, len = code.length; i6 < len; ++i6) {
    lookup[i6] = code[i6];
    revLookup[code.charCodeAt(i6)] = i6;
  }
  revLookup["-".charCodeAt(0)] = 62;
  revLookup["_".charCodeAt(0)] = 63;
  function getLens(b64) {
    var len2 = b64.length;
    if (len2 % 4 > 0) {
      throw new Error("Invalid string. Length must be a multiple of 4");
    }
    var validLen = b64.indexOf("=");
    if (validLen === -1) validLen = len2;
    var placeHoldersLen = validLen === len2 ? 0 : 4 - validLen % 4;
    return [validLen, placeHoldersLen];
  }
  function byteLength(b64) {
    var lens = getLens(b64);
    var validLen = lens[0];
    var placeHoldersLen = lens[1];
    return (validLen + placeHoldersLen) * 3 / 4 - placeHoldersLen;
  }
  function _byteLength(b64, validLen, placeHoldersLen) {
    return (validLen + placeHoldersLen) * 3 / 4 - placeHoldersLen;
  }
  function toByteArray(b64) {
    var tmp;
    var lens = getLens(b64);
    var validLen = lens[0];
    var placeHoldersLen = lens[1];
    var arr = new Arr(_byteLength(b64, validLen, placeHoldersLen));
    var curByte = 0;
    var len2 = placeHoldersLen > 0 ? validLen - 4 : validLen;
    var i7;
    for (i7 = 0; i7 < len2; i7 += 4) {
      tmp = revLookup[b64.charCodeAt(i7)] << 18 | revLookup[b64.charCodeAt(i7 + 1)] << 12 | revLookup[b64.charCodeAt(i7 + 2)] << 6 | revLookup[b64.charCodeAt(i7 + 3)];
      arr[curByte++] = tmp >> 16 & 255;
      arr[curByte++] = tmp >> 8 & 255;
      arr[curByte++] = tmp & 255;
    }
    if (placeHoldersLen === 2) {
      tmp = revLookup[b64.charCodeAt(i7)] << 2 | revLookup[b64.charCodeAt(i7 + 1)] >> 4;
      arr[curByte++] = tmp & 255;
    }
    if (placeHoldersLen === 1) {
      tmp = revLookup[b64.charCodeAt(i7)] << 10 | revLookup[b64.charCodeAt(i7 + 1)] << 4 | revLookup[b64.charCodeAt(i7 + 2)] >> 2;
      arr[curByte++] = tmp >> 8 & 255;
      arr[curByte++] = tmp & 255;
    }
    return arr;
  }
  function tripletToBase64(num) {
    return lookup[num >> 18 & 63] + lookup[num >> 12 & 63] + lookup[num >> 6 & 63] + lookup[num & 63];
  }
  function encodeChunk(uint8, start, end) {
    var tmp;
    var output = [];
    for (var i7 = start; i7 < end; i7 += 3) {
      tmp = (uint8[i7] << 16 & 16711680) + (uint8[i7 + 1] << 8 & 65280) + (uint8[i7 + 2] & 255);
      output.push(tripletToBase64(tmp));
    }
    return output.join("");
  }
  function fromByteArray(uint8) {
    var tmp;
    var len2 = uint8.length;
    var extraBytes = len2 % 3;
    var parts = [];
    var maxChunkLength = 16383;
    for (var i7 = 0, len22 = len2 - extraBytes; i7 < len22; i7 += maxChunkLength) {
      parts.push(encodeChunk(uint8, i7, i7 + maxChunkLength > len22 ? len22 : i7 + maxChunkLength));
    }
    if (extraBytes === 1) {
      tmp = uint8[len2 - 1];
      parts.push(lookup[tmp >> 2] + lookup[tmp << 4 & 63] + "==");
    } else if (extraBytes === 2) {
      tmp = (uint8[len2 - 2] << 8) + uint8[len2 - 1];
      parts.push(lookup[tmp >> 10] + lookup[tmp >> 4 & 63] + lookup[tmp << 2 & 63] + "=");
    }
    return parts.join("");
  }
  return exports$2;
}
function dew$1() {
  if (_dewExec$1) return exports$1;
  _dewExec$1 = true;
  exports$1.read = function(buffer2, offset, isLE, mLen, nBytes) {
    var e6, m5;
    var eLen = nBytes * 8 - mLen - 1;
    var eMax = (1 << eLen) - 1;
    var eBias = eMax >> 1;
    var nBits = -7;
    var i6 = isLE ? nBytes - 1 : 0;
    var d5 = isLE ? -1 : 1;
    var s6 = buffer2[offset + i6];
    i6 += d5;
    e6 = s6 & (1 << -nBits) - 1;
    s6 >>= -nBits;
    nBits += eLen;
    for (; nBits > 0; e6 = e6 * 256 + buffer2[offset + i6], i6 += d5, nBits -= 8) {
    }
    m5 = e6 & (1 << -nBits) - 1;
    e6 >>= -nBits;
    nBits += mLen;
    for (; nBits > 0; m5 = m5 * 256 + buffer2[offset + i6], i6 += d5, nBits -= 8) {
    }
    if (e6 === 0) {
      e6 = 1 - eBias;
    } else if (e6 === eMax) {
      return m5 ? NaN : (s6 ? -1 : 1) * Infinity;
    } else {
      m5 = m5 + Math.pow(2, mLen);
      e6 = e6 - eBias;
    }
    return (s6 ? -1 : 1) * m5 * Math.pow(2, e6 - mLen);
  };
  exports$1.write = function(buffer2, value, offset, isLE, mLen, nBytes) {
    var e6, m5, c6;
    var eLen = nBytes * 8 - mLen - 1;
    var eMax = (1 << eLen) - 1;
    var eBias = eMax >> 1;
    var rt = mLen === 23 ? Math.pow(2, -24) - Math.pow(2, -77) : 0;
    var i6 = isLE ? 0 : nBytes - 1;
    var d5 = isLE ? 1 : -1;
    var s6 = value < 0 || value === 0 && 1 / value < 0 ? 1 : 0;
    value = Math.abs(value);
    if (isNaN(value) || value === Infinity) {
      m5 = isNaN(value) ? 1 : 0;
      e6 = eMax;
    } else {
      e6 = Math.floor(Math.log(value) / Math.LN2);
      if (value * (c6 = Math.pow(2, -e6)) < 1) {
        e6--;
        c6 *= 2;
      }
      if (e6 + eBias >= 1) {
        value += rt / c6;
      } else {
        value += rt * Math.pow(2, 1 - eBias);
      }
      if (value * c6 >= 2) {
        e6++;
        c6 /= 2;
      }
      if (e6 + eBias >= eMax) {
        m5 = 0;
        e6 = eMax;
      } else if (e6 + eBias >= 1) {
        m5 = (value * c6 - 1) * Math.pow(2, mLen);
        e6 = e6 + eBias;
      } else {
        m5 = value * Math.pow(2, eBias - 1) * Math.pow(2, mLen);
        e6 = 0;
      }
    }
    for (; mLen >= 8; buffer2[offset + i6] = m5 & 255, i6 += d5, m5 /= 256, mLen -= 8) {
    }
    e6 = e6 << mLen | m5;
    eLen += mLen;
    for (; eLen > 0; buffer2[offset + i6] = e6 & 255, i6 += d5, e6 /= 256, eLen -= 8) {
    }
    buffer2[offset + i6 - d5] |= s6 * 128;
  };
  return exports$1;
}
function dew() {
  if (_dewExec) return exports;
  _dewExec = true;
  const base64 = dew$2();
  const ieee754 = dew$1();
  const customInspectSymbol = typeof Symbol === "function" && typeof Symbol["for"] === "function" ? Symbol["for"]("nodejs.util.inspect.custom") : null;
  exports.Buffer = Buffer3;
  exports.SlowBuffer = SlowBuffer;
  exports.INSPECT_MAX_BYTES = 50;
  const K_MAX_LENGTH = 2147483647;
  exports.kMaxLength = K_MAX_LENGTH;
  Buffer3.TYPED_ARRAY_SUPPORT = typedArraySupport();
  if (!Buffer3.TYPED_ARRAY_SUPPORT && typeof console !== "undefined" && typeof console.error === "function") {
    console.error("This browser lacks typed array (Uint8Array) support which is required by `buffer` v5.x. Use `buffer` v4.x if you require old browser support.");
  }
  function typedArraySupport() {
    try {
      const arr = new Uint8Array(1);
      const proto = {
        foo: function() {
          return 42;
        }
      };
      Object.setPrototypeOf(proto, Uint8Array.prototype);
      Object.setPrototypeOf(arr, proto);
      return arr.foo() === 42;
    } catch (e6) {
      return false;
    }
  }
  Object.defineProperty(Buffer3.prototype, "parent", {
    enumerable: true,
    get: function() {
      if (!Buffer3.isBuffer(this)) return void 0;
      return this.buffer;
    }
  });
  Object.defineProperty(Buffer3.prototype, "offset", {
    enumerable: true,
    get: function() {
      if (!Buffer3.isBuffer(this)) return void 0;
      return this.byteOffset;
    }
  });
  function createBuffer(length) {
    if (length > K_MAX_LENGTH) {
      throw new RangeError('The value "' + length + '" is invalid for option "size"');
    }
    const buf = new Uint8Array(length);
    Object.setPrototypeOf(buf, Buffer3.prototype);
    return buf;
  }
  function Buffer3(arg, encodingOrOffset, length) {
    if (typeof arg === "number") {
      if (typeof encodingOrOffset === "string") {
        throw new TypeError('The "string" argument must be of type string. Received type number');
      }
      return allocUnsafe(arg);
    }
    return from(arg, encodingOrOffset, length);
  }
  Buffer3.poolSize = 8192;
  function from(value, encodingOrOffset, length) {
    if (typeof value === "string") {
      return fromString(value, encodingOrOffset);
    }
    if (ArrayBuffer.isView(value)) {
      return fromArrayView(value);
    }
    if (value == null) {
      throw new TypeError("The first argument must be one of type string, Buffer, ArrayBuffer, Array, or Array-like Object. Received type " + typeof value);
    }
    if (isInstance(value, ArrayBuffer) || value && isInstance(value.buffer, ArrayBuffer)) {
      return fromArrayBuffer(value, encodingOrOffset, length);
    }
    if (typeof SharedArrayBuffer !== "undefined" && (isInstance(value, SharedArrayBuffer) || value && isInstance(value.buffer, SharedArrayBuffer))) {
      return fromArrayBuffer(value, encodingOrOffset, length);
    }
    if (typeof value === "number") {
      throw new TypeError('The "value" argument must not be of type number. Received type number');
    }
    const valueOf = value.valueOf && value.valueOf();
    if (valueOf != null && valueOf !== value) {
      return Buffer3.from(valueOf, encodingOrOffset, length);
    }
    const b5 = fromObject(value);
    if (b5) return b5;
    if (typeof Symbol !== "undefined" && Symbol.toPrimitive != null && typeof value[Symbol.toPrimitive] === "function") {
      return Buffer3.from(value[Symbol.toPrimitive]("string"), encodingOrOffset, length);
    }
    throw new TypeError("The first argument must be one of type string, Buffer, ArrayBuffer, Array, or Array-like Object. Received type " + typeof value);
  }
  Buffer3.from = function(value, encodingOrOffset, length) {
    return from(value, encodingOrOffset, length);
  };
  Object.setPrototypeOf(Buffer3.prototype, Uint8Array.prototype);
  Object.setPrototypeOf(Buffer3, Uint8Array);
  function assertSize(size) {
    if (typeof size !== "number") {
      throw new TypeError('"size" argument must be of type number');
    } else if (size < 0) {
      throw new RangeError('The value "' + size + '" is invalid for option "size"');
    }
  }
  function alloc(size, fill, encoding) {
    assertSize(size);
    if (size <= 0) {
      return createBuffer(size);
    }
    if (fill !== void 0) {
      return typeof encoding === "string" ? createBuffer(size).fill(fill, encoding) : createBuffer(size).fill(fill);
    }
    return createBuffer(size);
  }
  Buffer3.alloc = function(size, fill, encoding) {
    return alloc(size, fill, encoding);
  };
  function allocUnsafe(size) {
    assertSize(size);
    return createBuffer(size < 0 ? 0 : checked(size) | 0);
  }
  Buffer3.allocUnsafe = function(size) {
    return allocUnsafe(size);
  };
  Buffer3.allocUnsafeSlow = function(size) {
    return allocUnsafe(size);
  };
  function fromString(string, encoding) {
    if (typeof encoding !== "string" || encoding === "") {
      encoding = "utf8";
    }
    if (!Buffer3.isEncoding(encoding)) {
      throw new TypeError("Unknown encoding: " + encoding);
    }
    const length = byteLength(string, encoding) | 0;
    let buf = createBuffer(length);
    const actual = buf.write(string, encoding);
    if (actual !== length) {
      buf = buf.slice(0, actual);
    }
    return buf;
  }
  function fromArrayLike(array) {
    const length = array.length < 0 ? 0 : checked(array.length) | 0;
    const buf = createBuffer(length);
    for (let i6 = 0; i6 < length; i6 += 1) {
      buf[i6] = array[i6] & 255;
    }
    return buf;
  }
  function fromArrayView(arrayView) {
    if (isInstance(arrayView, Uint8Array)) {
      const copy = new Uint8Array(arrayView);
      return fromArrayBuffer(copy.buffer, copy.byteOffset, copy.byteLength);
    }
    return fromArrayLike(arrayView);
  }
  function fromArrayBuffer(array, byteOffset, length) {
    if (byteOffset < 0 || array.byteLength < byteOffset) {
      throw new RangeError('"offset" is outside of buffer bounds');
    }
    if (array.byteLength < byteOffset + (length || 0)) {
      throw new RangeError('"length" is outside of buffer bounds');
    }
    let buf;
    if (byteOffset === void 0 && length === void 0) {
      buf = new Uint8Array(array);
    } else if (length === void 0) {
      buf = new Uint8Array(array, byteOffset);
    } else {
      buf = new Uint8Array(array, byteOffset, length);
    }
    Object.setPrototypeOf(buf, Buffer3.prototype);
    return buf;
  }
  function fromObject(obj) {
    if (Buffer3.isBuffer(obj)) {
      const len = checked(obj.length) | 0;
      const buf = createBuffer(len);
      if (buf.length === 0) {
        return buf;
      }
      obj.copy(buf, 0, 0, len);
      return buf;
    }
    if (obj.length !== void 0) {
      if (typeof obj.length !== "number" || numberIsNaN(obj.length)) {
        return createBuffer(0);
      }
      return fromArrayLike(obj);
    }
    if (obj.type === "Buffer" && Array.isArray(obj.data)) {
      return fromArrayLike(obj.data);
    }
  }
  function checked(length) {
    if (length >= K_MAX_LENGTH) {
      throw new RangeError("Attempt to allocate Buffer larger than maximum size: 0x" + K_MAX_LENGTH.toString(16) + " bytes");
    }
    return length | 0;
  }
  function SlowBuffer(length) {
    if (+length != length) {
      length = 0;
    }
    return Buffer3.alloc(+length);
  }
  Buffer3.isBuffer = function isBuffer(b5) {
    return b5 != null && b5._isBuffer === true && b5 !== Buffer3.prototype;
  };
  Buffer3.compare = function compare(a6, b5) {
    if (isInstance(a6, Uint8Array)) a6 = Buffer3.from(a6, a6.offset, a6.byteLength);
    if (isInstance(b5, Uint8Array)) b5 = Buffer3.from(b5, b5.offset, b5.byteLength);
    if (!Buffer3.isBuffer(a6) || !Buffer3.isBuffer(b5)) {
      throw new TypeError('The "buf1", "buf2" arguments must be one of type Buffer or Uint8Array');
    }
    if (a6 === b5) return 0;
    let x4 = a6.length;
    let y6 = b5.length;
    for (let i6 = 0, len = Math.min(x4, y6); i6 < len; ++i6) {
      if (a6[i6] !== b5[i6]) {
        x4 = a6[i6];
        y6 = b5[i6];
        break;
      }
    }
    if (x4 < y6) return -1;
    if (y6 < x4) return 1;
    return 0;
  };
  Buffer3.isEncoding = function isEncoding(encoding) {
    switch (String(encoding).toLowerCase()) {
      case "hex":
      case "utf8":
      case "utf-8":
      case "ascii":
      case "latin1":
      case "binary":
      case "base64":
      case "ucs2":
      case "ucs-2":
      case "utf16le":
      case "utf-16le":
        return true;
      default:
        return false;
    }
  };
  Buffer3.concat = function concat(list, length) {
    if (!Array.isArray(list)) {
      throw new TypeError('"list" argument must be an Array of Buffers');
    }
    if (list.length === 0) {
      return Buffer3.alloc(0);
    }
    let i6;
    if (length === void 0) {
      length = 0;
      for (i6 = 0; i6 < list.length; ++i6) {
        length += list[i6].length;
      }
    }
    const buffer2 = Buffer3.allocUnsafe(length);
    let pos = 0;
    for (i6 = 0; i6 < list.length; ++i6) {
      let buf = list[i6];
      if (isInstance(buf, Uint8Array)) {
        if (pos + buf.length > buffer2.length) {
          if (!Buffer3.isBuffer(buf)) buf = Buffer3.from(buf);
          buf.copy(buffer2, pos);
        } else {
          Uint8Array.prototype.set.call(buffer2, buf, pos);
        }
      } else if (!Buffer3.isBuffer(buf)) {
        throw new TypeError('"list" argument must be an Array of Buffers');
      } else {
        buf.copy(buffer2, pos);
      }
      pos += buf.length;
    }
    return buffer2;
  };
  function byteLength(string, encoding) {
    if (Buffer3.isBuffer(string)) {
      return string.length;
    }
    if (ArrayBuffer.isView(string) || isInstance(string, ArrayBuffer)) {
      return string.byteLength;
    }
    if (typeof string !== "string") {
      throw new TypeError('The "string" argument must be one of type string, Buffer, or ArrayBuffer. Received type ' + typeof string);
    }
    const len = string.length;
    const mustMatch = arguments.length > 2 && arguments[2] === true;
    if (!mustMatch && len === 0) return 0;
    let loweredCase = false;
    for (; ; ) {
      switch (encoding) {
        case "ascii":
        case "latin1":
        case "binary":
          return len;
        case "utf8":
        case "utf-8":
          return utf8ToBytes(string).length;
        case "ucs2":
        case "ucs-2":
        case "utf16le":
        case "utf-16le":
          return len * 2;
        case "hex":
          return len >>> 1;
        case "base64":
          return base64ToBytes(string).length;
        default:
          if (loweredCase) {
            return mustMatch ? -1 : utf8ToBytes(string).length;
          }
          encoding = ("" + encoding).toLowerCase();
          loweredCase = true;
      }
    }
  }
  Buffer3.byteLength = byteLength;
  function slowToString(encoding, start, end) {
    let loweredCase = false;
    if (start === void 0 || start < 0) {
      start = 0;
    }
    if (start > this.length) {
      return "";
    }
    if (end === void 0 || end > this.length) {
      end = this.length;
    }
    if (end <= 0) {
      return "";
    }
    end >>>= 0;
    start >>>= 0;
    if (end <= start) {
      return "";
    }
    if (!encoding) encoding = "utf8";
    while (true) {
      switch (encoding) {
        case "hex":
          return hexSlice(this, start, end);
        case "utf8":
        case "utf-8":
          return utf8Slice(this, start, end);
        case "ascii":
          return asciiSlice(this, start, end);
        case "latin1":
        case "binary":
          return latin1Slice(this, start, end);
        case "base64":
          return base64Slice(this, start, end);
        case "ucs2":
        case "ucs-2":
        case "utf16le":
        case "utf-16le":
          return utf16leSlice(this, start, end);
        default:
          if (loweredCase) throw new TypeError("Unknown encoding: " + encoding);
          encoding = (encoding + "").toLowerCase();
          loweredCase = true;
      }
    }
  }
  Buffer3.prototype._isBuffer = true;
  function swap(b5, n6, m5) {
    const i6 = b5[n6];
    b5[n6] = b5[m5];
    b5[m5] = i6;
  }
  Buffer3.prototype.swap16 = function swap16() {
    const len = this.length;
    if (len % 2 !== 0) {
      throw new RangeError("Buffer size must be a multiple of 16-bits");
    }
    for (let i6 = 0; i6 < len; i6 += 2) {
      swap(this, i6, i6 + 1);
    }
    return this;
  };
  Buffer3.prototype.swap32 = function swap32() {
    const len = this.length;
    if (len % 4 !== 0) {
      throw new RangeError("Buffer size must be a multiple of 32-bits");
    }
    for (let i6 = 0; i6 < len; i6 += 4) {
      swap(this, i6, i6 + 3);
      swap(this, i6 + 1, i6 + 2);
    }
    return this;
  };
  Buffer3.prototype.swap64 = function swap64() {
    const len = this.length;
    if (len % 8 !== 0) {
      throw new RangeError("Buffer size must be a multiple of 64-bits");
    }
    for (let i6 = 0; i6 < len; i6 += 8) {
      swap(this, i6, i6 + 7);
      swap(this, i6 + 1, i6 + 6);
      swap(this, i6 + 2, i6 + 5);
      swap(this, i6 + 3, i6 + 4);
    }
    return this;
  };
  Buffer3.prototype.toString = function toString() {
    const length = this.length;
    if (length === 0) return "";
    if (arguments.length === 0) return utf8Slice(this, 0, length);
    return slowToString.apply(this, arguments);
  };
  Buffer3.prototype.toLocaleString = Buffer3.prototype.toString;
  Buffer3.prototype.equals = function equals(b5) {
    if (!Buffer3.isBuffer(b5)) throw new TypeError("Argument must be a Buffer");
    if (this === b5) return true;
    return Buffer3.compare(this, b5) === 0;
  };
  Buffer3.prototype.inspect = function inspect() {
    let str = "";
    const max = exports.INSPECT_MAX_BYTES;
    str = this.toString("hex", 0, max).replace(/(.{2})/g, "$1 ").trim();
    if (this.length > max) str += " ... ";
    return "<Buffer " + str + ">";
  };
  if (customInspectSymbol) {
    Buffer3.prototype[customInspectSymbol] = Buffer3.prototype.inspect;
  }
  Buffer3.prototype.compare = function compare(target, start, end, thisStart, thisEnd) {
    if (isInstance(target, Uint8Array)) {
      target = Buffer3.from(target, target.offset, target.byteLength);
    }
    if (!Buffer3.isBuffer(target)) {
      throw new TypeError('The "target" argument must be one of type Buffer or Uint8Array. Received type ' + typeof target);
    }
    if (start === void 0) {
      start = 0;
    }
    if (end === void 0) {
      end = target ? target.length : 0;
    }
    if (thisStart === void 0) {
      thisStart = 0;
    }
    if (thisEnd === void 0) {
      thisEnd = this.length;
    }
    if (start < 0 || end > target.length || thisStart < 0 || thisEnd > this.length) {
      throw new RangeError("out of range index");
    }
    if (thisStart >= thisEnd && start >= end) {
      return 0;
    }
    if (thisStart >= thisEnd) {
      return -1;
    }
    if (start >= end) {
      return 1;
    }
    start >>>= 0;
    end >>>= 0;
    thisStart >>>= 0;
    thisEnd >>>= 0;
    if (this === target) return 0;
    let x4 = thisEnd - thisStart;
    let y6 = end - start;
    const len = Math.min(x4, y6);
    const thisCopy = this.slice(thisStart, thisEnd);
    const targetCopy = target.slice(start, end);
    for (let i6 = 0; i6 < len; ++i6) {
      if (thisCopy[i6] !== targetCopy[i6]) {
        x4 = thisCopy[i6];
        y6 = targetCopy[i6];
        break;
      }
    }
    if (x4 < y6) return -1;
    if (y6 < x4) return 1;
    return 0;
  };
  function bidirectionalIndexOf(buffer2, val, byteOffset, encoding, dir) {
    if (buffer2.length === 0) return -1;
    if (typeof byteOffset === "string") {
      encoding = byteOffset;
      byteOffset = 0;
    } else if (byteOffset > 2147483647) {
      byteOffset = 2147483647;
    } else if (byteOffset < -2147483648) {
      byteOffset = -2147483648;
    }
    byteOffset = +byteOffset;
    if (numberIsNaN(byteOffset)) {
      byteOffset = dir ? 0 : buffer2.length - 1;
    }
    if (byteOffset < 0) byteOffset = buffer2.length + byteOffset;
    if (byteOffset >= buffer2.length) {
      if (dir) return -1;
      else byteOffset = buffer2.length - 1;
    } else if (byteOffset < 0) {
      if (dir) byteOffset = 0;
      else return -1;
    }
    if (typeof val === "string") {
      val = Buffer3.from(val, encoding);
    }
    if (Buffer3.isBuffer(val)) {
      if (val.length === 0) {
        return -1;
      }
      return arrayIndexOf(buffer2, val, byteOffset, encoding, dir);
    } else if (typeof val === "number") {
      val = val & 255;
      if (typeof Uint8Array.prototype.indexOf === "function") {
        if (dir) {
          return Uint8Array.prototype.indexOf.call(buffer2, val, byteOffset);
        } else {
          return Uint8Array.prototype.lastIndexOf.call(buffer2, val, byteOffset);
        }
      }
      return arrayIndexOf(buffer2, [val], byteOffset, encoding, dir);
    }
    throw new TypeError("val must be string, number or Buffer");
  }
  function arrayIndexOf(arr, val, byteOffset, encoding, dir) {
    let indexSize = 1;
    let arrLength = arr.length;
    let valLength = val.length;
    if (encoding !== void 0) {
      encoding = String(encoding).toLowerCase();
      if (encoding === "ucs2" || encoding === "ucs-2" || encoding === "utf16le" || encoding === "utf-16le") {
        if (arr.length < 2 || val.length < 2) {
          return -1;
        }
        indexSize = 2;
        arrLength /= 2;
        valLength /= 2;
        byteOffset /= 2;
      }
    }
    function read2(buf, i7) {
      if (indexSize === 1) {
        return buf[i7];
      } else {
        return buf.readUInt16BE(i7 * indexSize);
      }
    }
    let i6;
    if (dir) {
      let foundIndex = -1;
      for (i6 = byteOffset; i6 < arrLength; i6++) {
        if (read2(arr, i6) === read2(val, foundIndex === -1 ? 0 : i6 - foundIndex)) {
          if (foundIndex === -1) foundIndex = i6;
          if (i6 - foundIndex + 1 === valLength) return foundIndex * indexSize;
        } else {
          if (foundIndex !== -1) i6 -= i6 - foundIndex;
          foundIndex = -1;
        }
      }
    } else {
      if (byteOffset + valLength > arrLength) byteOffset = arrLength - valLength;
      for (i6 = byteOffset; i6 >= 0; i6--) {
        let found = true;
        for (let j4 = 0; j4 < valLength; j4++) {
          if (read2(arr, i6 + j4) !== read2(val, j4)) {
            found = false;
            break;
          }
        }
        if (found) return i6;
      }
    }
    return -1;
  }
  Buffer3.prototype.includes = function includes(val, byteOffset, encoding) {
    return this.indexOf(val, byteOffset, encoding) !== -1;
  };
  Buffer3.prototype.indexOf = function indexOf(val, byteOffset, encoding) {
    return bidirectionalIndexOf(this, val, byteOffset, encoding, true);
  };
  Buffer3.prototype.lastIndexOf = function lastIndexOf(val, byteOffset, encoding) {
    return bidirectionalIndexOf(this, val, byteOffset, encoding, false);
  };
  function hexWrite(buf, string, offset, length) {
    offset = Number(offset) || 0;
    const remaining = buf.length - offset;
    if (!length) {
      length = remaining;
    } else {
      length = Number(length);
      if (length > remaining) {
        length = remaining;
      }
    }
    const strLen = string.length;
    if (length > strLen / 2) {
      length = strLen / 2;
    }
    let i6;
    for (i6 = 0; i6 < length; ++i6) {
      const parsed = parseInt(string.substr(i6 * 2, 2), 16);
      if (numberIsNaN(parsed)) return i6;
      buf[offset + i6] = parsed;
    }
    return i6;
  }
  function utf8Write(buf, string, offset, length) {
    return blitBuffer(utf8ToBytes(string, buf.length - offset), buf, offset, length);
  }
  function asciiWrite(buf, string, offset, length) {
    return blitBuffer(asciiToBytes(string), buf, offset, length);
  }
  function base64Write(buf, string, offset, length) {
    return blitBuffer(base64ToBytes(string), buf, offset, length);
  }
  function ucs2Write(buf, string, offset, length) {
    return blitBuffer(utf16leToBytes(string, buf.length - offset), buf, offset, length);
  }
  Buffer3.prototype.write = function write2(string, offset, length, encoding) {
    if (offset === void 0) {
      encoding = "utf8";
      length = this.length;
      offset = 0;
    } else if (length === void 0 && typeof offset === "string") {
      encoding = offset;
      length = this.length;
      offset = 0;
    } else if (isFinite(offset)) {
      offset = offset >>> 0;
      if (isFinite(length)) {
        length = length >>> 0;
        if (encoding === void 0) encoding = "utf8";
      } else {
        encoding = length;
        length = void 0;
      }
    } else {
      throw new Error("Buffer.write(string, encoding, offset[, length]) is no longer supported");
    }
    const remaining = this.length - offset;
    if (length === void 0 || length > remaining) length = remaining;
    if (string.length > 0 && (length < 0 || offset < 0) || offset > this.length) {
      throw new RangeError("Attempt to write outside buffer bounds");
    }
    if (!encoding) encoding = "utf8";
    let loweredCase = false;
    for (; ; ) {
      switch (encoding) {
        case "hex":
          return hexWrite(this, string, offset, length);
        case "utf8":
        case "utf-8":
          return utf8Write(this, string, offset, length);
        case "ascii":
        case "latin1":
        case "binary":
          return asciiWrite(this, string, offset, length);
        case "base64":
          return base64Write(this, string, offset, length);
        case "ucs2":
        case "ucs-2":
        case "utf16le":
        case "utf-16le":
          return ucs2Write(this, string, offset, length);
        default:
          if (loweredCase) throw new TypeError("Unknown encoding: " + encoding);
          encoding = ("" + encoding).toLowerCase();
          loweredCase = true;
      }
    }
  };
  Buffer3.prototype.toJSON = function toJSON() {
    return {
      type: "Buffer",
      data: Array.prototype.slice.call(this._arr || this, 0)
    };
  };
  function base64Slice(buf, start, end) {
    if (start === 0 && end === buf.length) {
      return base64.fromByteArray(buf);
    } else {
      return base64.fromByteArray(buf.slice(start, end));
    }
  }
  function utf8Slice(buf, start, end) {
    end = Math.min(buf.length, end);
    const res = [];
    let i6 = start;
    while (i6 < end) {
      const firstByte = buf[i6];
      let codePoint = null;
      let bytesPerSequence = firstByte > 239 ? 4 : firstByte > 223 ? 3 : firstByte > 191 ? 2 : 1;
      if (i6 + bytesPerSequence <= end) {
        let secondByte, thirdByte, fourthByte, tempCodePoint;
        switch (bytesPerSequence) {
          case 1:
            if (firstByte < 128) {
              codePoint = firstByte;
            }
            break;
          case 2:
            secondByte = buf[i6 + 1];
            if ((secondByte & 192) === 128) {
              tempCodePoint = (firstByte & 31) << 6 | secondByte & 63;
              if (tempCodePoint > 127) {
                codePoint = tempCodePoint;
              }
            }
            break;
          case 3:
            secondByte = buf[i6 + 1];
            thirdByte = buf[i6 + 2];
            if ((secondByte & 192) === 128 && (thirdByte & 192) === 128) {
              tempCodePoint = (firstByte & 15) << 12 | (secondByte & 63) << 6 | thirdByte & 63;
              if (tempCodePoint > 2047 && (tempCodePoint < 55296 || tempCodePoint > 57343)) {
                codePoint = tempCodePoint;
              }
            }
            break;
          case 4:
            secondByte = buf[i6 + 1];
            thirdByte = buf[i6 + 2];
            fourthByte = buf[i6 + 3];
            if ((secondByte & 192) === 128 && (thirdByte & 192) === 128 && (fourthByte & 192) === 128) {
              tempCodePoint = (firstByte & 15) << 18 | (secondByte & 63) << 12 | (thirdByte & 63) << 6 | fourthByte & 63;
              if (tempCodePoint > 65535 && tempCodePoint < 1114112) {
                codePoint = tempCodePoint;
              }
            }
        }
      }
      if (codePoint === null) {
        codePoint = 65533;
        bytesPerSequence = 1;
      } else if (codePoint > 65535) {
        codePoint -= 65536;
        res.push(codePoint >>> 10 & 1023 | 55296);
        codePoint = 56320 | codePoint & 1023;
      }
      res.push(codePoint);
      i6 += bytesPerSequence;
    }
    return decodeCodePointsArray(res);
  }
  const MAX_ARGUMENTS_LENGTH = 4096;
  function decodeCodePointsArray(codePoints) {
    const len = codePoints.length;
    if (len <= MAX_ARGUMENTS_LENGTH) {
      return String.fromCharCode.apply(String, codePoints);
    }
    let res = "";
    let i6 = 0;
    while (i6 < len) {
      res += String.fromCharCode.apply(String, codePoints.slice(i6, i6 += MAX_ARGUMENTS_LENGTH));
    }
    return res;
  }
  function asciiSlice(buf, start, end) {
    let ret = "";
    end = Math.min(buf.length, end);
    for (let i6 = start; i6 < end; ++i6) {
      ret += String.fromCharCode(buf[i6] & 127);
    }
    return ret;
  }
  function latin1Slice(buf, start, end) {
    let ret = "";
    end = Math.min(buf.length, end);
    for (let i6 = start; i6 < end; ++i6) {
      ret += String.fromCharCode(buf[i6]);
    }
    return ret;
  }
  function hexSlice(buf, start, end) {
    const len = buf.length;
    if (!start || start < 0) start = 0;
    if (!end || end < 0 || end > len) end = len;
    let out = "";
    for (let i6 = start; i6 < end; ++i6) {
      out += hexSliceLookupTable[buf[i6]];
    }
    return out;
  }
  function utf16leSlice(buf, start, end) {
    const bytes = buf.slice(start, end);
    let res = "";
    for (let i6 = 0; i6 < bytes.length - 1; i6 += 2) {
      res += String.fromCharCode(bytes[i6] + bytes[i6 + 1] * 256);
    }
    return res;
  }
  Buffer3.prototype.slice = function slice(start, end) {
    const len = this.length;
    start = ~~start;
    end = end === void 0 ? len : ~~end;
    if (start < 0) {
      start += len;
      if (start < 0) start = 0;
    } else if (start > len) {
      start = len;
    }
    if (end < 0) {
      end += len;
      if (end < 0) end = 0;
    } else if (end > len) {
      end = len;
    }
    if (end < start) end = start;
    const newBuf = this.subarray(start, end);
    Object.setPrototypeOf(newBuf, Buffer3.prototype);
    return newBuf;
  };
  function checkOffset(offset, ext, length) {
    if (offset % 1 !== 0 || offset < 0) throw new RangeError("offset is not uint");
    if (offset + ext > length) throw new RangeError("Trying to access beyond buffer length");
  }
  Buffer3.prototype.readUintLE = Buffer3.prototype.readUIntLE = function readUIntLE(offset, byteLength2, noAssert) {
    offset = offset >>> 0;
    byteLength2 = byteLength2 >>> 0;
    if (!noAssert) checkOffset(offset, byteLength2, this.length);
    let val = this[offset];
    let mul = 1;
    let i6 = 0;
    while (++i6 < byteLength2 && (mul *= 256)) {
      val += this[offset + i6] * mul;
    }
    return val;
  };
  Buffer3.prototype.readUintBE = Buffer3.prototype.readUIntBE = function readUIntBE(offset, byteLength2, noAssert) {
    offset = offset >>> 0;
    byteLength2 = byteLength2 >>> 0;
    if (!noAssert) {
      checkOffset(offset, byteLength2, this.length);
    }
    let val = this[offset + --byteLength2];
    let mul = 1;
    while (byteLength2 > 0 && (mul *= 256)) {
      val += this[offset + --byteLength2] * mul;
    }
    return val;
  };
  Buffer3.prototype.readUint8 = Buffer3.prototype.readUInt8 = function readUInt8(offset, noAssert) {
    offset = offset >>> 0;
    if (!noAssert) checkOffset(offset, 1, this.length);
    return this[offset];
  };
  Buffer3.prototype.readUint16LE = Buffer3.prototype.readUInt16LE = function readUInt16LE(offset, noAssert) {
    offset = offset >>> 0;
    if (!noAssert) checkOffset(offset, 2, this.length);
    return this[offset] | this[offset + 1] << 8;
  };
  Buffer3.prototype.readUint16BE = Buffer3.prototype.readUInt16BE = function readUInt16BE(offset, noAssert) {
    offset = offset >>> 0;
    if (!noAssert) checkOffset(offset, 2, this.length);
    return this[offset] << 8 | this[offset + 1];
  };
  Buffer3.prototype.readUint32LE = Buffer3.prototype.readUInt32LE = function readUInt32LE(offset, noAssert) {
    offset = offset >>> 0;
    if (!noAssert) checkOffset(offset, 4, this.length);
    return (this[offset] | this[offset + 1] << 8 | this[offset + 2] << 16) + this[offset + 3] * 16777216;
  };
  Buffer3.prototype.readUint32BE = Buffer3.prototype.readUInt32BE = function readUInt32BE(offset, noAssert) {
    offset = offset >>> 0;
    if (!noAssert) checkOffset(offset, 4, this.length);
    return this[offset] * 16777216 + (this[offset + 1] << 16 | this[offset + 2] << 8 | this[offset + 3]);
  };
  Buffer3.prototype.readBigUInt64LE = defineBigIntMethod(function readBigUInt64LE(offset) {
    offset = offset >>> 0;
    validateNumber(offset, "offset");
    const first = this[offset];
    const last = this[offset + 7];
    if (first === void 0 || last === void 0) {
      boundsError(offset, this.length - 8);
    }
    const lo = first + this[++offset] * 2 ** 8 + this[++offset] * 2 ** 16 + this[++offset] * 2 ** 24;
    const hi = this[++offset] + this[++offset] * 2 ** 8 + this[++offset] * 2 ** 16 + last * 2 ** 24;
    return BigInt(lo) + (BigInt(hi) << BigInt(32));
  });
  Buffer3.prototype.readBigUInt64BE = defineBigIntMethod(function readBigUInt64BE(offset) {
    offset = offset >>> 0;
    validateNumber(offset, "offset");
    const first = this[offset];
    const last = this[offset + 7];
    if (first === void 0 || last === void 0) {
      boundsError(offset, this.length - 8);
    }
    const hi = first * 2 ** 24 + this[++offset] * 2 ** 16 + this[++offset] * 2 ** 8 + this[++offset];
    const lo = this[++offset] * 2 ** 24 + this[++offset] * 2 ** 16 + this[++offset] * 2 ** 8 + last;
    return (BigInt(hi) << BigInt(32)) + BigInt(lo);
  });
  Buffer3.prototype.readIntLE = function readIntLE(offset, byteLength2, noAssert) {
    offset = offset >>> 0;
    byteLength2 = byteLength2 >>> 0;
    if (!noAssert) checkOffset(offset, byteLength2, this.length);
    let val = this[offset];
    let mul = 1;
    let i6 = 0;
    while (++i6 < byteLength2 && (mul *= 256)) {
      val += this[offset + i6] * mul;
    }
    mul *= 128;
    if (val >= mul) val -= Math.pow(2, 8 * byteLength2);
    return val;
  };
  Buffer3.prototype.readIntBE = function readIntBE(offset, byteLength2, noAssert) {
    offset = offset >>> 0;
    byteLength2 = byteLength2 >>> 0;
    if (!noAssert) checkOffset(offset, byteLength2, this.length);
    let i6 = byteLength2;
    let mul = 1;
    let val = this[offset + --i6];
    while (i6 > 0 && (mul *= 256)) {
      val += this[offset + --i6] * mul;
    }
    mul *= 128;
    if (val >= mul) val -= Math.pow(2, 8 * byteLength2);
    return val;
  };
  Buffer3.prototype.readInt8 = function readInt8(offset, noAssert) {
    offset = offset >>> 0;
    if (!noAssert) checkOffset(offset, 1, this.length);
    if (!(this[offset] & 128)) return this[offset];
    return (255 - this[offset] + 1) * -1;
  };
  Buffer3.prototype.readInt16LE = function readInt16LE(offset, noAssert) {
    offset = offset >>> 0;
    if (!noAssert) checkOffset(offset, 2, this.length);
    const val = this[offset] | this[offset + 1] << 8;
    return val & 32768 ? val | 4294901760 : val;
  };
  Buffer3.prototype.readInt16BE = function readInt16BE(offset, noAssert) {
    offset = offset >>> 0;
    if (!noAssert) checkOffset(offset, 2, this.length);
    const val = this[offset + 1] | this[offset] << 8;
    return val & 32768 ? val | 4294901760 : val;
  };
  Buffer3.prototype.readInt32LE = function readInt32LE(offset, noAssert) {
    offset = offset >>> 0;
    if (!noAssert) checkOffset(offset, 4, this.length);
    return this[offset] | this[offset + 1] << 8 | this[offset + 2] << 16 | this[offset + 3] << 24;
  };
  Buffer3.prototype.readInt32BE = function readInt32BE(offset, noAssert) {
    offset = offset >>> 0;
    if (!noAssert) checkOffset(offset, 4, this.length);
    return this[offset] << 24 | this[offset + 1] << 16 | this[offset + 2] << 8 | this[offset + 3];
  };
  Buffer3.prototype.readBigInt64LE = defineBigIntMethod(function readBigInt64LE(offset) {
    offset = offset >>> 0;
    validateNumber(offset, "offset");
    const first = this[offset];
    const last = this[offset + 7];
    if (first === void 0 || last === void 0) {
      boundsError(offset, this.length - 8);
    }
    const val = this[offset + 4] + this[offset + 5] * 2 ** 8 + this[offset + 6] * 2 ** 16 + (last << 24);
    return (BigInt(val) << BigInt(32)) + BigInt(first + this[++offset] * 2 ** 8 + this[++offset] * 2 ** 16 + this[++offset] * 2 ** 24);
  });
  Buffer3.prototype.readBigInt64BE = defineBigIntMethod(function readBigInt64BE(offset) {
    offset = offset >>> 0;
    validateNumber(offset, "offset");
    const first = this[offset];
    const last = this[offset + 7];
    if (first === void 0 || last === void 0) {
      boundsError(offset, this.length - 8);
    }
    const val = (first << 24) + // Overflow
    this[++offset] * 2 ** 16 + this[++offset] * 2 ** 8 + this[++offset];
    return (BigInt(val) << BigInt(32)) + BigInt(this[++offset] * 2 ** 24 + this[++offset] * 2 ** 16 + this[++offset] * 2 ** 8 + last);
  });
  Buffer3.prototype.readFloatLE = function readFloatLE(offset, noAssert) {
    offset = offset >>> 0;
    if (!noAssert) checkOffset(offset, 4, this.length);
    return ieee754.read(this, offset, true, 23, 4);
  };
  Buffer3.prototype.readFloatBE = function readFloatBE(offset, noAssert) {
    offset = offset >>> 0;
    if (!noAssert) checkOffset(offset, 4, this.length);
    return ieee754.read(this, offset, false, 23, 4);
  };
  Buffer3.prototype.readDoubleLE = function readDoubleLE(offset, noAssert) {
    offset = offset >>> 0;
    if (!noAssert) checkOffset(offset, 8, this.length);
    return ieee754.read(this, offset, true, 52, 8);
  };
  Buffer3.prototype.readDoubleBE = function readDoubleBE(offset, noAssert) {
    offset = offset >>> 0;
    if (!noAssert) checkOffset(offset, 8, this.length);
    return ieee754.read(this, offset, false, 52, 8);
  };
  function checkInt(buf, value, offset, ext, max, min) {
    if (!Buffer3.isBuffer(buf)) throw new TypeError('"buffer" argument must be a Buffer instance');
    if (value > max || value < min) throw new RangeError('"value" argument is out of bounds');
    if (offset + ext > buf.length) throw new RangeError("Index out of range");
  }
  Buffer3.prototype.writeUintLE = Buffer3.prototype.writeUIntLE = function writeUIntLE(value, offset, byteLength2, noAssert) {
    value = +value;
    offset = offset >>> 0;
    byteLength2 = byteLength2 >>> 0;
    if (!noAssert) {
      const maxBytes = Math.pow(2, 8 * byteLength2) - 1;
      checkInt(this, value, offset, byteLength2, maxBytes, 0);
    }
    let mul = 1;
    let i6 = 0;
    this[offset] = value & 255;
    while (++i6 < byteLength2 && (mul *= 256)) {
      this[offset + i6] = value / mul & 255;
    }
    return offset + byteLength2;
  };
  Buffer3.prototype.writeUintBE = Buffer3.prototype.writeUIntBE = function writeUIntBE(value, offset, byteLength2, noAssert) {
    value = +value;
    offset = offset >>> 0;
    byteLength2 = byteLength2 >>> 0;
    if (!noAssert) {
      const maxBytes = Math.pow(2, 8 * byteLength2) - 1;
      checkInt(this, value, offset, byteLength2, maxBytes, 0);
    }
    let i6 = byteLength2 - 1;
    let mul = 1;
    this[offset + i6] = value & 255;
    while (--i6 >= 0 && (mul *= 256)) {
      this[offset + i6] = value / mul & 255;
    }
    return offset + byteLength2;
  };
  Buffer3.prototype.writeUint8 = Buffer3.prototype.writeUInt8 = function writeUInt8(value, offset, noAssert) {
    value = +value;
    offset = offset >>> 0;
    if (!noAssert) checkInt(this, value, offset, 1, 255, 0);
    this[offset] = value & 255;
    return offset + 1;
  };
  Buffer3.prototype.writeUint16LE = Buffer3.prototype.writeUInt16LE = function writeUInt16LE(value, offset, noAssert) {
    value = +value;
    offset = offset >>> 0;
    if (!noAssert) checkInt(this, value, offset, 2, 65535, 0);
    this[offset] = value & 255;
    this[offset + 1] = value >>> 8;
    return offset + 2;
  };
  Buffer3.prototype.writeUint16BE = Buffer3.prototype.writeUInt16BE = function writeUInt16BE(value, offset, noAssert) {
    value = +value;
    offset = offset >>> 0;
    if (!noAssert) checkInt(this, value, offset, 2, 65535, 0);
    this[offset] = value >>> 8;
    this[offset + 1] = value & 255;
    return offset + 2;
  };
  Buffer3.prototype.writeUint32LE = Buffer3.prototype.writeUInt32LE = function writeUInt32LE(value, offset, noAssert) {
    value = +value;
    offset = offset >>> 0;
    if (!noAssert) checkInt(this, value, offset, 4, 4294967295, 0);
    this[offset + 3] = value >>> 24;
    this[offset + 2] = value >>> 16;
    this[offset + 1] = value >>> 8;
    this[offset] = value & 255;
    return offset + 4;
  };
  Buffer3.prototype.writeUint32BE = Buffer3.prototype.writeUInt32BE = function writeUInt32BE(value, offset, noAssert) {
    value = +value;
    offset = offset >>> 0;
    if (!noAssert) checkInt(this, value, offset, 4, 4294967295, 0);
    this[offset] = value >>> 24;
    this[offset + 1] = value >>> 16;
    this[offset + 2] = value >>> 8;
    this[offset + 3] = value & 255;
    return offset + 4;
  };
  function wrtBigUInt64LE(buf, value, offset, min, max) {
    checkIntBI(value, min, max, buf, offset, 7);
    let lo = Number(value & BigInt(4294967295));
    buf[offset++] = lo;
    lo = lo >> 8;
    buf[offset++] = lo;
    lo = lo >> 8;
    buf[offset++] = lo;
    lo = lo >> 8;
    buf[offset++] = lo;
    let hi = Number(value >> BigInt(32) & BigInt(4294967295));
    buf[offset++] = hi;
    hi = hi >> 8;
    buf[offset++] = hi;
    hi = hi >> 8;
    buf[offset++] = hi;
    hi = hi >> 8;
    buf[offset++] = hi;
    return offset;
  }
  function wrtBigUInt64BE(buf, value, offset, min, max) {
    checkIntBI(value, min, max, buf, offset, 7);
    let lo = Number(value & BigInt(4294967295));
    buf[offset + 7] = lo;
    lo = lo >> 8;
    buf[offset + 6] = lo;
    lo = lo >> 8;
    buf[offset + 5] = lo;
    lo = lo >> 8;
    buf[offset + 4] = lo;
    let hi = Number(value >> BigInt(32) & BigInt(4294967295));
    buf[offset + 3] = hi;
    hi = hi >> 8;
    buf[offset + 2] = hi;
    hi = hi >> 8;
    buf[offset + 1] = hi;
    hi = hi >> 8;
    buf[offset] = hi;
    return offset + 8;
  }
  Buffer3.prototype.writeBigUInt64LE = defineBigIntMethod(function writeBigUInt64LE(value, offset = 0) {
    return wrtBigUInt64LE(this, value, offset, BigInt(0), BigInt("0xffffffffffffffff"));
  });
  Buffer3.prototype.writeBigUInt64BE = defineBigIntMethod(function writeBigUInt64BE(value, offset = 0) {
    return wrtBigUInt64BE(this, value, offset, BigInt(0), BigInt("0xffffffffffffffff"));
  });
  Buffer3.prototype.writeIntLE = function writeIntLE(value, offset, byteLength2, noAssert) {
    value = +value;
    offset = offset >>> 0;
    if (!noAssert) {
      const limit = Math.pow(2, 8 * byteLength2 - 1);
      checkInt(this, value, offset, byteLength2, limit - 1, -limit);
    }
    let i6 = 0;
    let mul = 1;
    let sub = 0;
    this[offset] = value & 255;
    while (++i6 < byteLength2 && (mul *= 256)) {
      if (value < 0 && sub === 0 && this[offset + i6 - 1] !== 0) {
        sub = 1;
      }
      this[offset + i6] = (value / mul >> 0) - sub & 255;
    }
    return offset + byteLength2;
  };
  Buffer3.prototype.writeIntBE = function writeIntBE(value, offset, byteLength2, noAssert) {
    value = +value;
    offset = offset >>> 0;
    if (!noAssert) {
      const limit = Math.pow(2, 8 * byteLength2 - 1);
      checkInt(this, value, offset, byteLength2, limit - 1, -limit);
    }
    let i6 = byteLength2 - 1;
    let mul = 1;
    let sub = 0;
    this[offset + i6] = value & 255;
    while (--i6 >= 0 && (mul *= 256)) {
      if (value < 0 && sub === 0 && this[offset + i6 + 1] !== 0) {
        sub = 1;
      }
      this[offset + i6] = (value / mul >> 0) - sub & 255;
    }
    return offset + byteLength2;
  };
  Buffer3.prototype.writeInt8 = function writeInt8(value, offset, noAssert) {
    value = +value;
    offset = offset >>> 0;
    if (!noAssert) checkInt(this, value, offset, 1, 127, -128);
    if (value < 0) value = 255 + value + 1;
    this[offset] = value & 255;
    return offset + 1;
  };
  Buffer3.prototype.writeInt16LE = function writeInt16LE(value, offset, noAssert) {
    value = +value;
    offset = offset >>> 0;
    if (!noAssert) checkInt(this, value, offset, 2, 32767, -32768);
    this[offset] = value & 255;
    this[offset + 1] = value >>> 8;
    return offset + 2;
  };
  Buffer3.prototype.writeInt16BE = function writeInt16BE(value, offset, noAssert) {
    value = +value;
    offset = offset >>> 0;
    if (!noAssert) checkInt(this, value, offset, 2, 32767, -32768);
    this[offset] = value >>> 8;
    this[offset + 1] = value & 255;
    return offset + 2;
  };
  Buffer3.prototype.writeInt32LE = function writeInt32LE(value, offset, noAssert) {
    value = +value;
    offset = offset >>> 0;
    if (!noAssert) checkInt(this, value, offset, 4, 2147483647, -2147483648);
    this[offset] = value & 255;
    this[offset + 1] = value >>> 8;
    this[offset + 2] = value >>> 16;
    this[offset + 3] = value >>> 24;
    return offset + 4;
  };
  Buffer3.prototype.writeInt32BE = function writeInt32BE(value, offset, noAssert) {
    value = +value;
    offset = offset >>> 0;
    if (!noAssert) checkInt(this, value, offset, 4, 2147483647, -2147483648);
    if (value < 0) value = 4294967295 + value + 1;
    this[offset] = value >>> 24;
    this[offset + 1] = value >>> 16;
    this[offset + 2] = value >>> 8;
    this[offset + 3] = value & 255;
    return offset + 4;
  };
  Buffer3.prototype.writeBigInt64LE = defineBigIntMethod(function writeBigInt64LE(value, offset = 0) {
    return wrtBigUInt64LE(this, value, offset, -BigInt("0x8000000000000000"), BigInt("0x7fffffffffffffff"));
  });
  Buffer3.prototype.writeBigInt64BE = defineBigIntMethod(function writeBigInt64BE(value, offset = 0) {
    return wrtBigUInt64BE(this, value, offset, -BigInt("0x8000000000000000"), BigInt("0x7fffffffffffffff"));
  });
  function checkIEEE754(buf, value, offset, ext, max, min) {
    if (offset + ext > buf.length) throw new RangeError("Index out of range");
    if (offset < 0) throw new RangeError("Index out of range");
  }
  function writeFloat(buf, value, offset, littleEndian, noAssert) {
    value = +value;
    offset = offset >>> 0;
    if (!noAssert) {
      checkIEEE754(buf, value, offset, 4);
    }
    ieee754.write(buf, value, offset, littleEndian, 23, 4);
    return offset + 4;
  }
  Buffer3.prototype.writeFloatLE = function writeFloatLE(value, offset, noAssert) {
    return writeFloat(this, value, offset, true, noAssert);
  };
  Buffer3.prototype.writeFloatBE = function writeFloatBE(value, offset, noAssert) {
    return writeFloat(this, value, offset, false, noAssert);
  };
  function writeDouble(buf, value, offset, littleEndian, noAssert) {
    value = +value;
    offset = offset >>> 0;
    if (!noAssert) {
      checkIEEE754(buf, value, offset, 8);
    }
    ieee754.write(buf, value, offset, littleEndian, 52, 8);
    return offset + 8;
  }
  Buffer3.prototype.writeDoubleLE = function writeDoubleLE(value, offset, noAssert) {
    return writeDouble(this, value, offset, true, noAssert);
  };
  Buffer3.prototype.writeDoubleBE = function writeDoubleBE(value, offset, noAssert) {
    return writeDouble(this, value, offset, false, noAssert);
  };
  Buffer3.prototype.copy = function copy(target, targetStart, start, end) {
    if (!Buffer3.isBuffer(target)) throw new TypeError("argument should be a Buffer");
    if (!start) start = 0;
    if (!end && end !== 0) end = this.length;
    if (targetStart >= target.length) targetStart = target.length;
    if (!targetStart) targetStart = 0;
    if (end > 0 && end < start) end = start;
    if (end === start) return 0;
    if (target.length === 0 || this.length === 0) return 0;
    if (targetStart < 0) {
      throw new RangeError("targetStart out of bounds");
    }
    if (start < 0 || start >= this.length) throw new RangeError("Index out of range");
    if (end < 0) throw new RangeError("sourceEnd out of bounds");
    if (end > this.length) end = this.length;
    if (target.length - targetStart < end - start) {
      end = target.length - targetStart + start;
    }
    const len = end - start;
    if (this === target && typeof Uint8Array.prototype.copyWithin === "function") {
      this.copyWithin(targetStart, start, end);
    } else {
      Uint8Array.prototype.set.call(target, this.subarray(start, end), targetStart);
    }
    return len;
  };
  Buffer3.prototype.fill = function fill(val, start, end, encoding) {
    if (typeof val === "string") {
      if (typeof start === "string") {
        encoding = start;
        start = 0;
        end = this.length;
      } else if (typeof end === "string") {
        encoding = end;
        end = this.length;
      }
      if (encoding !== void 0 && typeof encoding !== "string") {
        throw new TypeError("encoding must be a string");
      }
      if (typeof encoding === "string" && !Buffer3.isEncoding(encoding)) {
        throw new TypeError("Unknown encoding: " + encoding);
      }
      if (val.length === 1) {
        const code = val.charCodeAt(0);
        if (encoding === "utf8" && code < 128 || encoding === "latin1") {
          val = code;
        }
      }
    } else if (typeof val === "number") {
      val = val & 255;
    } else if (typeof val === "boolean") {
      val = Number(val);
    }
    if (start < 0 || this.length < start || this.length < end) {
      throw new RangeError("Out of range index");
    }
    if (end <= start) {
      return this;
    }
    start = start >>> 0;
    end = end === void 0 ? this.length : end >>> 0;
    if (!val) val = 0;
    let i6;
    if (typeof val === "number") {
      for (i6 = start; i6 < end; ++i6) {
        this[i6] = val;
      }
    } else {
      const bytes = Buffer3.isBuffer(val) ? val : Buffer3.from(val, encoding);
      const len = bytes.length;
      if (len === 0) {
        throw new TypeError('The value "' + val + '" is invalid for argument "value"');
      }
      for (i6 = 0; i6 < end - start; ++i6) {
        this[i6 + start] = bytes[i6 % len];
      }
    }
    return this;
  };
  const errors = {};
  function E4(sym, getMessage, Base) {
    errors[sym] = class NodeError extends Base {
      constructor() {
        super();
        Object.defineProperty(this, "message", {
          value: getMessage.apply(this, arguments),
          writable: true,
          configurable: true
        });
        this.name = `${this.name} [${sym}]`;
        this.stack;
        delete this.name;
      }
      get code() {
        return sym;
      }
      set code(value) {
        Object.defineProperty(this, "code", {
          configurable: true,
          enumerable: true,
          value,
          writable: true
        });
      }
      toString() {
        return `${this.name} [${sym}]: ${this.message}`;
      }
    };
  }
  E4("ERR_BUFFER_OUT_OF_BOUNDS", function(name2) {
    if (name2) {
      return `${name2} is outside of buffer bounds`;
    }
    return "Attempt to access memory outside buffer bounds";
  }, RangeError);
  E4("ERR_INVALID_ARG_TYPE", function(name2, actual) {
    return `The "${name2}" argument must be of type number. Received type ${typeof actual}`;
  }, TypeError);
  E4("ERR_OUT_OF_RANGE", function(str, range, input) {
    let msg = `The value of "${str}" is out of range.`;
    let received = input;
    if (Number.isInteger(input) && Math.abs(input) > 2 ** 32) {
      received = addNumericalSeparator(String(input));
    } else if (typeof input === "bigint") {
      received = String(input);
      if (input > BigInt(2) ** BigInt(32) || input < -(BigInt(2) ** BigInt(32))) {
        received = addNumericalSeparator(received);
      }
      received += "n";
    }
    msg += ` It must be ${range}. Received ${received}`;
    return msg;
  }, RangeError);
  function addNumericalSeparator(val) {
    let res = "";
    let i6 = val.length;
    const start = val[0] === "-" ? 1 : 0;
    for (; i6 >= start + 4; i6 -= 3) {
      res = `_${val.slice(i6 - 3, i6)}${res}`;
    }
    return `${val.slice(0, i6)}${res}`;
  }
  function checkBounds(buf, offset, byteLength2) {
    validateNumber(offset, "offset");
    if (buf[offset] === void 0 || buf[offset + byteLength2] === void 0) {
      boundsError(offset, buf.length - (byteLength2 + 1));
    }
  }
  function checkIntBI(value, min, max, buf, offset, byteLength2) {
    if (value > max || value < min) {
      const n6 = typeof min === "bigint" ? "n" : "";
      let range;
      {
        if (min === 0 || min === BigInt(0)) {
          range = `>= 0${n6} and < 2${n6} ** ${(byteLength2 + 1) * 8}${n6}`;
        } else {
          range = `>= -(2${n6} ** ${(byteLength2 + 1) * 8 - 1}${n6}) and < 2 ** ${(byteLength2 + 1) * 8 - 1}${n6}`;
        }
      }
      throw new errors.ERR_OUT_OF_RANGE("value", range, value);
    }
    checkBounds(buf, offset, byteLength2);
  }
  function validateNumber(value, name2) {
    if (typeof value !== "number") {
      throw new errors.ERR_INVALID_ARG_TYPE(name2, "number", value);
    }
  }
  function boundsError(value, length, type) {
    if (Math.floor(value) !== value) {
      validateNumber(value, type);
      throw new errors.ERR_OUT_OF_RANGE("offset", "an integer", value);
    }
    if (length < 0) {
      throw new errors.ERR_BUFFER_OUT_OF_BOUNDS();
    }
    throw new errors.ERR_OUT_OF_RANGE("offset", `>= ${0} and <= ${length}`, value);
  }
  const INVALID_BASE64_RE = /[^+/0-9A-Za-z-_]/g;
  function base64clean(str) {
    str = str.split("=")[0];
    str = str.trim().replace(INVALID_BASE64_RE, "");
    if (str.length < 2) return "";
    while (str.length % 4 !== 0) {
      str = str + "=";
    }
    return str;
  }
  function utf8ToBytes(string, units) {
    units = units || Infinity;
    let codePoint;
    const length = string.length;
    let leadSurrogate = null;
    const bytes = [];
    for (let i6 = 0; i6 < length; ++i6) {
      codePoint = string.charCodeAt(i6);
      if (codePoint > 55295 && codePoint < 57344) {
        if (!leadSurrogate) {
          if (codePoint > 56319) {
            if ((units -= 3) > -1) bytes.push(239, 191, 189);
            continue;
          } else if (i6 + 1 === length) {
            if ((units -= 3) > -1) bytes.push(239, 191, 189);
            continue;
          }
          leadSurrogate = codePoint;
          continue;
        }
        if (codePoint < 56320) {
          if ((units -= 3) > -1) bytes.push(239, 191, 189);
          leadSurrogate = codePoint;
          continue;
        }
        codePoint = (leadSurrogate - 55296 << 10 | codePoint - 56320) + 65536;
      } else if (leadSurrogate) {
        if ((units -= 3) > -1) bytes.push(239, 191, 189);
      }
      leadSurrogate = null;
      if (codePoint < 128) {
        if ((units -= 1) < 0) break;
        bytes.push(codePoint);
      } else if (codePoint < 2048) {
        if ((units -= 2) < 0) break;
        bytes.push(codePoint >> 6 | 192, codePoint & 63 | 128);
      } else if (codePoint < 65536) {
        if ((units -= 3) < 0) break;
        bytes.push(codePoint >> 12 | 224, codePoint >> 6 & 63 | 128, codePoint & 63 | 128);
      } else if (codePoint < 1114112) {
        if ((units -= 4) < 0) break;
        bytes.push(codePoint >> 18 | 240, codePoint >> 12 & 63 | 128, codePoint >> 6 & 63 | 128, codePoint & 63 | 128);
      } else {
        throw new Error("Invalid code point");
      }
    }
    return bytes;
  }
  function asciiToBytes(str) {
    const byteArray = [];
    for (let i6 = 0; i6 < str.length; ++i6) {
      byteArray.push(str.charCodeAt(i6) & 255);
    }
    return byteArray;
  }
  function utf16leToBytes(str, units) {
    let c6, hi, lo;
    const byteArray = [];
    for (let i6 = 0; i6 < str.length; ++i6) {
      if ((units -= 2) < 0) break;
      c6 = str.charCodeAt(i6);
      hi = c6 >> 8;
      lo = c6 % 256;
      byteArray.push(lo);
      byteArray.push(hi);
    }
    return byteArray;
  }
  function base64ToBytes(str) {
    return base64.toByteArray(base64clean(str));
  }
  function blitBuffer(src, dst, offset, length) {
    let i6;
    for (i6 = 0; i6 < length; ++i6) {
      if (i6 + offset >= dst.length || i6 >= src.length) break;
      dst[i6 + offset] = src[i6];
    }
    return i6;
  }
  function isInstance(obj, type) {
    return obj instanceof type || obj != null && obj.constructor != null && obj.constructor.name != null && obj.constructor.name === type.name;
  }
  function numberIsNaN(obj) {
    return obj !== obj;
  }
  const hexSliceLookupTable = (function() {
    const alphabet = "0123456789abcdef";
    const table = new Array(256);
    for (let i6 = 0; i6 < 16; ++i6) {
      const i16 = i6 * 16;
      for (let j4 = 0; j4 < 16; ++j4) {
        table[i16 + j4] = alphabet[i6] + alphabet[j4];
      }
    }
    return table;
  })();
  function defineBigIntMethod(fn) {
    return typeof BigInt === "undefined" ? BufferBigIntNotDefined : fn;
  }
  function BufferBigIntNotDefined() {
    throw new Error("BigInt not supported");
  }
  return exports;
}
var exports$2, _dewExec$2, exports$1, _dewExec$1, exports, _dewExec;
var init_chunk_DtuTasat = __esm({
  "node_modules/@jspm/core/nodelibs/browser/chunk-DtuTasat.js"() {
    init_dirname();
    init_buffer2();
    init_process2();
    exports$2 = {};
    _dewExec$2 = false;
    exports$1 = {};
    _dewExec$1 = false;
    exports = {};
    _dewExec = false;
  }
});

// node_modules/@jspm/core/nodelibs/browser/buffer.js
var exports2, Buffer2, INSPECT_MAX_BYTES, kMaxLength;
var init_buffer = __esm({
  "node_modules/@jspm/core/nodelibs/browser/buffer.js"() {
    init_dirname();
    init_buffer2();
    init_process2();
    init_chunk_DtuTasat();
    exports2 = dew();
    exports2["Buffer"];
    exports2["SlowBuffer"];
    exports2["INSPECT_MAX_BYTES"];
    exports2["kMaxLength"];
    Buffer2 = exports2.Buffer;
    INSPECT_MAX_BYTES = exports2.INSPECT_MAX_BYTES;
    kMaxLength = exports2.kMaxLength;
  }
});

// node_modules/esbuild-plugin-polyfill-node/polyfills/buffer.js
var init_buffer2 = __esm({
  "node_modules/esbuild-plugin-polyfill-node/polyfills/buffer.js"() {
    init_buffer();
  }
});

// node_modules/@jspm/core/nodelibs/browser/chunk-D3uu3VYh.js
function i$2() {
  throw new Error("setTimeout has not been defined");
}
function u$2() {
  throw new Error("clearTimeout has not been defined");
}
function c$2(e6) {
  if (t$3 === setTimeout) return setTimeout(e6, 0);
  if ((t$3 === i$2 || !t$3) && setTimeout) return t$3 = setTimeout, setTimeout(e6, 0);
  try {
    return t$3(e6, 0);
  } catch (n6) {
    try {
      return t$3.call(null, e6, 0);
    } catch (n7) {
      return t$3.call(this || r$2, e6, 0);
    }
  }
}
function h$1() {
  f$1 && l$2 && (f$1 = false, l$2.length ? s$1 = l$2.concat(s$1) : a$1 = -1, s$1.length && d$1());
}
function d$1() {
  if (!f$1) {
    var e6 = c$2(h$1);
    f$1 = true;
    for (var t6 = s$1.length; t6; ) {
      for (l$2 = s$1, s$1 = []; ++a$1 < t6; ) l$2 && l$2[a$1].run();
      a$1 = -1, t6 = s$1.length;
    }
    l$2 = null, f$1 = false, (function(e7) {
      if (n$2 === clearTimeout) return clearTimeout(e7);
      if ((n$2 === u$2 || !n$2) && clearTimeout) return n$2 = clearTimeout, clearTimeout(e7);
      try {
        n$2(e7);
      } catch (t7) {
        try {
          return n$2.call(null, e7);
        } catch (t8) {
          return n$2.call(this || r$2, e7);
        }
      }
    })(e6);
  }
}
function m$1(e6, t6) {
  (this || r$2).fun = e6, (this || r$2).array = t6;
}
function p$1() {
}
function c$1(e6) {
  return e6.call.bind(e6);
}
function O(e6, t6) {
  if ("object" != typeof e6) return false;
  try {
    return t6(e6), true;
  } catch (e7) {
    return false;
  }
}
function S(e6) {
  return l$1 && y ? void 0 !== b(e6) : B(e6) || k(e6) || E(e6) || D(e6) || U(e6) || P(e6) || x(e6) || I(e6) || M(e6) || z(e6) || F(e6);
}
function B(e6) {
  return l$1 && y ? "Uint8Array" === b(e6) : "[object Uint8Array]" === m(e6) || u$1(e6) && void 0 !== e6.buffer;
}
function k(e6) {
  return l$1 && y ? "Uint8ClampedArray" === b(e6) : "[object Uint8ClampedArray]" === m(e6);
}
function E(e6) {
  return l$1 && y ? "Uint16Array" === b(e6) : "[object Uint16Array]" === m(e6);
}
function D(e6) {
  return l$1 && y ? "Uint32Array" === b(e6) : "[object Uint32Array]" === m(e6);
}
function U(e6) {
  return l$1 && y ? "Int8Array" === b(e6) : "[object Int8Array]" === m(e6);
}
function P(e6) {
  return l$1 && y ? "Int16Array" === b(e6) : "[object Int16Array]" === m(e6);
}
function x(e6) {
  return l$1 && y ? "Int32Array" === b(e6) : "[object Int32Array]" === m(e6);
}
function I(e6) {
  return l$1 && y ? "Float32Array" === b(e6) : "[object Float32Array]" === m(e6);
}
function M(e6) {
  return l$1 && y ? "Float64Array" === b(e6) : "[object Float64Array]" === m(e6);
}
function z(e6) {
  return l$1 && y ? "BigInt64Array" === b(e6) : "[object BigInt64Array]" === m(e6);
}
function F(e6) {
  return l$1 && y ? "BigUint64Array" === b(e6) : "[object BigUint64Array]" === m(e6);
}
function T(e6) {
  return "[object Map]" === m(e6);
}
function N(e6) {
  return "[object Set]" === m(e6);
}
function W(e6) {
  return "[object WeakMap]" === m(e6);
}
function $(e6) {
  return "[object WeakSet]" === m(e6);
}
function C(e6) {
  return "[object ArrayBuffer]" === m(e6);
}
function V(e6) {
  return "undefined" != typeof ArrayBuffer && (C.working ? C(e6) : e6 instanceof ArrayBuffer);
}
function G(e6) {
  return "[object DataView]" === m(e6);
}
function R(e6) {
  return "undefined" != typeof DataView && (G.working ? G(e6) : e6 instanceof DataView);
}
function J(e6) {
  return "[object SharedArrayBuffer]" === m(e6);
}
function _(e6) {
  return "undefined" != typeof SharedArrayBuffer && (J.working ? J(e6) : e6 instanceof SharedArrayBuffer);
}
function H(e6) {
  return O(e6, h);
}
function Z(e6) {
  return O(e6, j);
}
function q(e6) {
  return O(e6, A);
}
function K(e6) {
  return s && O(e6, w);
}
function L(e6) {
  return p && O(e6, v);
}
function oe(e6, t6) {
  var r6 = { seen: [], stylize: fe };
  return arguments.length >= 3 && (r6.depth = arguments[2]), arguments.length >= 4 && (r6.colors = arguments[3]), ye(t6) ? r6.showHidden = t6 : t6 && X._extend(r6, t6), be(r6.showHidden) && (r6.showHidden = false), be(r6.depth) && (r6.depth = 2), be(r6.colors) && (r6.colors = false), be(r6.customInspect) && (r6.customInspect = true), r6.colors && (r6.stylize = ue), ae(r6, e6, r6.depth);
}
function ue(e6, t6) {
  var r6 = oe.styles[t6];
  return r6 ? "\x1B[" + oe.colors[r6][0] + "m" + e6 + "\x1B[" + oe.colors[r6][1] + "m" : e6;
}
function fe(e6, t6) {
  return e6;
}
function ae(e6, t6, r6) {
  if (e6.customInspect && t6 && we(t6.inspect) && t6.inspect !== X.inspect && (!t6.constructor || t6.constructor.prototype !== t6)) {
    var n6 = t6.inspect(r6, e6);
    return ge(n6) || (n6 = ae(e6, n6, r6)), n6;
  }
  var i6 = (function(e7, t7) {
    if (be(t7)) return e7.stylize("undefined", "undefined");
    if (ge(t7)) {
      var r7 = "'" + JSON.stringify(t7).replace(/^"|"$/g, "").replace(/'/g, "\\'").replace(/\\"/g, '"') + "'";
      return e7.stylize(r7, "string");
    }
    if (de(t7)) return e7.stylize("" + t7, "number");
    if (ye(t7)) return e7.stylize("" + t7, "boolean");
    if (le(t7)) return e7.stylize("null", "null");
  })(e6, t6);
  if (i6) return i6;
  var o6 = Object.keys(t6), u6 = (function(e7) {
    var t7 = {};
    return e7.forEach((function(e8, r7) {
      t7[e8] = true;
    })), t7;
  })(o6);
  if (e6.showHidden && (o6 = Object.getOwnPropertyNames(t6)), Ae(t6) && (o6.indexOf("message") >= 0 || o6.indexOf("description") >= 0)) return ce(t6);
  if (0 === o6.length) {
    if (we(t6)) {
      var f6 = t6.name ? ": " + t6.name : "";
      return e6.stylize("[Function" + f6 + "]", "special");
    }
    if (me(t6)) return e6.stylize(RegExp.prototype.toString.call(t6), "regexp");
    if (je(t6)) return e6.stylize(Date.prototype.toString.call(t6), "date");
    if (Ae(t6)) return ce(t6);
  }
  var a6, c6 = "", s6 = false, p6 = ["{", "}"];
  (pe(t6) && (s6 = true, p6 = ["[", "]"]), we(t6)) && (c6 = " [Function" + (t6.name ? ": " + t6.name : "") + "]");
  return me(t6) && (c6 = " " + RegExp.prototype.toString.call(t6)), je(t6) && (c6 = " " + Date.prototype.toUTCString.call(t6)), Ae(t6) && (c6 = " " + ce(t6)), 0 !== o6.length || s6 && 0 != t6.length ? r6 < 0 ? me(t6) ? e6.stylize(RegExp.prototype.toString.call(t6), "regexp") : e6.stylize("[Object]", "special") : (e6.seen.push(t6), a6 = s6 ? (function(e7, t7, r7, n7, i7) {
    for (var o7 = [], u7 = 0, f7 = t7.length; u7 < f7; ++u7) ke(t7, String(u7)) ? o7.push(se(e7, t7, r7, n7, String(u7), true)) : o7.push("");
    return i7.forEach((function(i8) {
      i8.match(/^\d+$/) || o7.push(se(e7, t7, r7, n7, i8, true));
    })), o7;
  })(e6, t6, r6, u6, o6) : o6.map((function(n7) {
    return se(e6, t6, r6, u6, n7, s6);
  })), e6.seen.pop(), (function(e7, t7, r7) {
    var n7 = 0;
    if (e7.reduce((function(e8, t8) {
      return n7++, t8.indexOf("\n") >= 0 && n7++, e8 + t8.replace(/\u001b\[\d\d?m/g, "").length + 1;
    }), 0) > 60) return r7[0] + ("" === t7 ? "" : t7 + "\n ") + " " + e7.join(",\n  ") + " " + r7[1];
    return r7[0] + t7 + " " + e7.join(", ") + " " + r7[1];
  })(a6, c6, p6)) : p6[0] + c6 + p6[1];
}
function ce(e6) {
  return "[" + Error.prototype.toString.call(e6) + "]";
}
function se(e6, t6, r6, n6, i6, o6) {
  var u6, f6, a6;
  if ((a6 = Object.getOwnPropertyDescriptor(t6, i6) || { value: t6[i6] }).get ? f6 = a6.set ? e6.stylize("[Getter/Setter]", "special") : e6.stylize("[Getter]", "special") : a6.set && (f6 = e6.stylize("[Setter]", "special")), ke(n6, i6) || (u6 = "[" + i6 + "]"), f6 || (e6.seen.indexOf(a6.value) < 0 ? (f6 = le(r6) ? ae(e6, a6.value, null) : ae(e6, a6.value, r6 - 1)).indexOf("\n") > -1 && (f6 = o6 ? f6.split("\n").map((function(e7) {
    return "  " + e7;
  })).join("\n").substr(2) : "\n" + f6.split("\n").map((function(e7) {
    return "   " + e7;
  })).join("\n")) : f6 = e6.stylize("[Circular]", "special")), be(u6)) {
    if (o6 && i6.match(/^\d+$/)) return f6;
    (u6 = JSON.stringify("" + i6)).match(/^"([a-zA-Z_][a-zA-Z_0-9]*)"$/) ? (u6 = u6.substr(1, u6.length - 2), u6 = e6.stylize(u6, "name")) : (u6 = u6.replace(/'/g, "\\'").replace(/\\"/g, '"').replace(/(^"|"$)/g, "'"), u6 = e6.stylize(u6, "string"));
  }
  return u6 + ": " + f6;
}
function pe(e6) {
  return Array.isArray(e6);
}
function ye(e6) {
  return "boolean" == typeof e6;
}
function le(e6) {
  return null === e6;
}
function de(e6) {
  return "number" == typeof e6;
}
function ge(e6) {
  return "string" == typeof e6;
}
function be(e6) {
  return void 0 === e6;
}
function me(e6) {
  return he(e6) && "[object RegExp]" === ve(e6);
}
function he(e6) {
  return "object" == typeof e6 && null !== e6;
}
function je(e6) {
  return he(e6) && "[object Date]" === ve(e6);
}
function Ae(e6) {
  return he(e6) && ("[object Error]" === ve(e6) || e6 instanceof Error);
}
function we(e6) {
  return "function" == typeof e6;
}
function ve(e6) {
  return Object.prototype.toString.call(e6);
}
function Oe(e6) {
  return e6 < 10 ? "0" + e6.toString(10) : e6.toString(10);
}
function Be() {
  var e6 = /* @__PURE__ */ new Date(), t6 = [Oe(e6.getHours()), Oe(e6.getMinutes()), Oe(e6.getSeconds())].join(":");
  return [e6.getDate(), Se[e6.getMonth()], t6].join(" ");
}
function ke(e6, t6) {
  return Object.prototype.hasOwnProperty.call(e6, t6);
}
function De(e6, t6) {
  if (!e6) {
    var r6 = new Error("Promise was rejected with a falsy value");
    r6.reason = e6, e6 = r6;
  }
  return t6(e6);
}
var e$2, t$3, n$2, r$2, o$3, l$2, s$1, f$1, a$1, T$1, t, e, o, n, r, l, t$1, o$1, n$1, e$1, r$1, c, u, i, t$2, i$1, o$2, u$1, f, a, s, p, y, l$1, d, g, b, m, h, j, A, w, v, Q, X, Y, ee, te, re, ne, ie, Se, Ee, promisify;
var init_chunk_D3uu3VYh = __esm({
  "node_modules/@jspm/core/nodelibs/browser/chunk-D3uu3VYh.js"() {
    init_dirname();
    init_buffer2();
    init_process2();
    r$2 = "undefined" != typeof globalThis ? globalThis : "undefined" != typeof self ? self : global;
    o$3 = e$2 = {};
    !(function() {
      try {
        t$3 = "function" == typeof setTimeout ? setTimeout : i$2;
      } catch (e6) {
        t$3 = i$2;
      }
      try {
        n$2 = "function" == typeof clearTimeout ? clearTimeout : u$2;
      } catch (e6) {
        n$2 = u$2;
      }
    })();
    s$1 = [];
    f$1 = false;
    a$1 = -1;
    o$3.nextTick = function(e6) {
      var t6 = new Array(arguments.length - 1);
      if (arguments.length > 1) for (var n6 = 1; n6 < arguments.length; n6++) t6[n6 - 1] = arguments[n6];
      s$1.push(new m$1(e6, t6)), 1 !== s$1.length || f$1 || c$2(d$1);
    }, m$1.prototype.run = function() {
      (this || r$2).fun.apply(null, (this || r$2).array);
    }, o$3.title = "browser", o$3.browser = true, o$3.env = {}, o$3.argv = [], o$3.version = "", o$3.versions = {}, o$3.on = p$1, o$3.addListener = p$1, o$3.once = p$1, o$3.off = p$1, o$3.removeListener = p$1, o$3.removeAllListeners = p$1, o$3.emit = p$1, o$3.prependListener = p$1, o$3.prependOnceListener = p$1, o$3.listeners = function(e6) {
      return [];
    }, o$3.binding = function(e6) {
      throw new Error("process.binding is not supported");
    }, o$3.cwd = function() {
      return "/";
    }, o$3.chdir = function(e6) {
      throw new Error("process.chdir is not supported");
    }, o$3.umask = function() {
      return 0;
    };
    T$1 = e$2;
    T$1.addListener;
    T$1.argv;
    T$1.binding;
    T$1.browser;
    T$1.chdir;
    T$1.cwd;
    T$1.emit;
    T$1.env;
    T$1.listeners;
    T$1.nextTick;
    T$1.off;
    T$1.on;
    T$1.once;
    T$1.prependListener;
    T$1.prependOnceListener;
    T$1.removeAllListeners;
    T$1.removeListener;
    T$1.title;
    T$1.umask;
    T$1.version;
    T$1.versions;
    t = "function" == typeof Symbol && "symbol" == typeof Symbol.toStringTag;
    e = Object.prototype.toString;
    o = function(o6) {
      return !(t && o6 && "object" == typeof o6 && Symbol.toStringTag in o6) && "[object Arguments]" === e.call(o6);
    };
    n = function(t6) {
      return !!o(t6) || null !== t6 && "object" == typeof t6 && "number" == typeof t6.length && t6.length >= 0 && "[object Array]" !== e.call(t6) && "[object Function]" === e.call(t6.callee);
    };
    r = (function() {
      return o(arguments);
    })();
    o.isLegacyArguments = n;
    l = r ? o : n;
    t$1 = Object.prototype.toString;
    o$1 = Function.prototype.toString;
    n$1 = /^\s*(?:function)?\*/;
    e$1 = "function" == typeof Symbol && "symbol" == typeof Symbol.toStringTag;
    r$1 = Object.getPrototypeOf;
    c = (function() {
      if (!e$1) return false;
      try {
        return Function("return function*() {}")();
      } catch (t6) {
      }
    })();
    u = c ? r$1(c) : {};
    i = function(c6) {
      return "function" == typeof c6 && (!!n$1.test(o$1.call(c6)) || (e$1 ? r$1(c6) === u : "[object GeneratorFunction]" === t$1.call(c6)));
    };
    t$2 = "function" == typeof Object.create ? function(t6, e6) {
      e6 && (t6.super_ = e6, t6.prototype = Object.create(e6.prototype, { constructor: { value: t6, enumerable: false, writable: true, configurable: true } }));
    } : function(t6, e6) {
      if (e6) {
        t6.super_ = e6;
        var o6 = function() {
        };
        o6.prototype = e6.prototype, t6.prototype = new o6(), t6.prototype.constructor = t6;
      }
    };
    i$1 = function(e6) {
      return e6 && "object" == typeof e6 && "function" == typeof e6.copy && "function" == typeof e6.fill && "function" == typeof e6.readUInt8;
    };
    o$2 = {};
    u$1 = i$1;
    f = l;
    a = i;
    s = "undefined" != typeof BigInt;
    p = "undefined" != typeof Symbol;
    y = p && void 0 !== Symbol.toStringTag;
    l$1 = "undefined" != typeof Uint8Array;
    d = "undefined" != typeof ArrayBuffer;
    if (l$1 && y) g = Object.getPrototypeOf(Uint8Array.prototype), b = c$1(Object.getOwnPropertyDescriptor(g, Symbol.toStringTag).get);
    m = c$1(Object.prototype.toString);
    h = c$1(Number.prototype.valueOf);
    j = c$1(String.prototype.valueOf);
    A = c$1(Boolean.prototype.valueOf);
    if (s) w = c$1(BigInt.prototype.valueOf);
    if (p) v = c$1(Symbol.prototype.valueOf);
    o$2.isArgumentsObject = f, o$2.isGeneratorFunction = a, o$2.isPromise = function(e6) {
      return "undefined" != typeof Promise && e6 instanceof Promise || null !== e6 && "object" == typeof e6 && "function" == typeof e6.then && "function" == typeof e6.catch;
    }, o$2.isArrayBufferView = function(e6) {
      return d && ArrayBuffer.isView ? ArrayBuffer.isView(e6) : S(e6) || R(e6);
    }, o$2.isTypedArray = S, o$2.isUint8Array = B, o$2.isUint8ClampedArray = k, o$2.isUint16Array = E, o$2.isUint32Array = D, o$2.isInt8Array = U, o$2.isInt16Array = P, o$2.isInt32Array = x, o$2.isFloat32Array = I, o$2.isFloat64Array = M, o$2.isBigInt64Array = z, o$2.isBigUint64Array = F, T.working = "undefined" != typeof Map && T(/* @__PURE__ */ new Map()), o$2.isMap = function(e6) {
      return "undefined" != typeof Map && (T.working ? T(e6) : e6 instanceof Map);
    }, N.working = "undefined" != typeof Set && N(/* @__PURE__ */ new Set()), o$2.isSet = function(e6) {
      return "undefined" != typeof Set && (N.working ? N(e6) : e6 instanceof Set);
    }, W.working = "undefined" != typeof WeakMap && W(/* @__PURE__ */ new WeakMap()), o$2.isWeakMap = function(e6) {
      return "undefined" != typeof WeakMap && (W.working ? W(e6) : e6 instanceof WeakMap);
    }, $.working = "undefined" != typeof WeakSet && $(/* @__PURE__ */ new WeakSet()), o$2.isWeakSet = function(e6) {
      return $(e6);
    }, C.working = "undefined" != typeof ArrayBuffer && C(new ArrayBuffer()), o$2.isArrayBuffer = V, G.working = "undefined" != typeof ArrayBuffer && "undefined" != typeof DataView && G(new DataView(new ArrayBuffer(1), 0, 1)), o$2.isDataView = R, J.working = "undefined" != typeof SharedArrayBuffer && J(new SharedArrayBuffer()), o$2.isSharedArrayBuffer = _, o$2.isAsyncFunction = function(e6) {
      return "[object AsyncFunction]" === m(e6);
    }, o$2.isMapIterator = function(e6) {
      return "[object Map Iterator]" === m(e6);
    }, o$2.isSetIterator = function(e6) {
      return "[object Set Iterator]" === m(e6);
    }, o$2.isGeneratorObject = function(e6) {
      return "[object Generator]" === m(e6);
    }, o$2.isWebAssemblyCompiledModule = function(e6) {
      return "[object WebAssembly.Module]" === m(e6);
    }, o$2.isNumberObject = H, o$2.isStringObject = Z, o$2.isBooleanObject = q, o$2.isBigIntObject = K, o$2.isSymbolObject = L, o$2.isBoxedPrimitive = function(e6) {
      return H(e6) || Z(e6) || q(e6) || K(e6) || L(e6);
    }, o$2.isAnyArrayBuffer = function(e6) {
      return l$1 && (V(e6) || _(e6));
    }, ["isProxy", "isExternal", "isModuleNamespaceObject"].forEach((function(e6) {
      Object.defineProperty(o$2, e6, { enumerable: false, value: function() {
        throw new Error(e6 + " is not supported in userland");
      } });
    }));
    Q = "undefined" != typeof globalThis ? globalThis : "undefined" != typeof self ? self : global;
    X = {};
    Y = T$1;
    ee = Object.getOwnPropertyDescriptors || function(e6) {
      for (var t6 = Object.keys(e6), r6 = {}, n6 = 0; n6 < t6.length; n6++) r6[t6[n6]] = Object.getOwnPropertyDescriptor(e6, t6[n6]);
      return r6;
    };
    te = /%[sdj%]/g;
    X.format = function(e6) {
      if (!ge(e6)) {
        for (var t6 = [], r6 = 0; r6 < arguments.length; r6++) t6.push(oe(arguments[r6]));
        return t6.join(" ");
      }
      r6 = 1;
      for (var n6 = arguments, i6 = n6.length, o6 = String(e6).replace(te, (function(e7) {
        if ("%%" === e7) return "%";
        if (r6 >= i6) return e7;
        switch (e7) {
          case "%s":
            return String(n6[r6++]);
          case "%d":
            return Number(n6[r6++]);
          case "%j":
            try {
              return JSON.stringify(n6[r6++]);
            } catch (e8) {
              return "[Circular]";
            }
          default:
            return e7;
        }
      })), u6 = n6[r6]; r6 < i6; u6 = n6[++r6]) le(u6) || !he(u6) ? o6 += " " + u6 : o6 += " " + oe(u6);
      return o6;
    }, X.deprecate = function(e6, t6) {
      if (void 0 !== Y && true === Y.noDeprecation) return e6;
      if (void 0 === Y) return function() {
        return X.deprecate(e6, t6).apply(this || Q, arguments);
      };
      var r6 = false;
      return function() {
        if (!r6) {
          if (Y.throwDeprecation) throw new Error(t6);
          Y.traceDeprecation ? console.trace(t6) : console.error(t6), r6 = true;
        }
        return e6.apply(this || Q, arguments);
      };
    };
    re = {};
    ne = /^$/;
    if (Y.env.NODE_DEBUG) {
      ie = Y.env.NODE_DEBUG;
      ie = ie.replace(/[|\\{}()[\]^$+?.]/g, "\\$&").replace(/\*/g, ".*").replace(/,/g, "$|^").toUpperCase(), ne = new RegExp("^" + ie + "$", "i");
    }
    X.debuglog = function(e6) {
      if (e6 = e6.toUpperCase(), !re[e6]) if (ne.test(e6)) {
        var t6 = Y.pid;
        re[e6] = function() {
          var r6 = X.format.apply(X, arguments);
          console.error("%s %d: %s", e6, t6, r6);
        };
      } else re[e6] = function() {
      };
      return re[e6];
    }, X.inspect = oe, oe.colors = { bold: [1, 22], italic: [3, 23], underline: [4, 24], inverse: [7, 27], white: [37, 39], grey: [90, 39], black: [30, 39], blue: [34, 39], cyan: [36, 39], green: [32, 39], magenta: [35, 39], red: [31, 39], yellow: [33, 39] }, oe.styles = { special: "cyan", number: "yellow", boolean: "yellow", undefined: "grey", null: "bold", string: "green", date: "magenta", regexp: "red" }, X.types = o$2, X.isArray = pe, X.isBoolean = ye, X.isNull = le, X.isNullOrUndefined = function(e6) {
      return null == e6;
    }, X.isNumber = de, X.isString = ge, X.isSymbol = function(e6) {
      return "symbol" == typeof e6;
    }, X.isUndefined = be, X.isRegExp = me, X.types.isRegExp = me, X.isObject = he, X.isDate = je, X.types.isDate = je, X.isError = Ae, X.types.isNativeError = Ae, X.isFunction = we, X.isPrimitive = function(e6) {
      return null === e6 || "boolean" == typeof e6 || "number" == typeof e6 || "string" == typeof e6 || "symbol" == typeof e6 || void 0 === e6;
    }, X.isBuffer = i$1;
    Se = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
    X.log = function() {
      console.log("%s - %s", Be(), X.format.apply(X, arguments));
    }, X.inherits = t$2, X._extend = function(e6, t6) {
      if (!t6 || !he(t6)) return e6;
      for (var r6 = Object.keys(t6), n6 = r6.length; n6--; ) e6[r6[n6]] = t6[r6[n6]];
      return e6;
    };
    Ee = "undefined" != typeof Symbol ? /* @__PURE__ */ Symbol("util.promisify.custom") : void 0;
    X.promisify = function(e6) {
      if ("function" != typeof e6) throw new TypeError('The "original" argument must be of type Function');
      if (Ee && e6[Ee]) {
        var t6;
        if ("function" != typeof (t6 = e6[Ee])) throw new TypeError('The "util.promisify.custom" argument must be of type Function');
        return Object.defineProperty(t6, Ee, { value: t6, enumerable: false, writable: false, configurable: true }), t6;
      }
      function t6() {
        for (var t7, r6, n6 = new Promise((function(e7, n7) {
          t7 = e7, r6 = n7;
        })), i6 = [], o6 = 0; o6 < arguments.length; o6++) i6.push(arguments[o6]);
        i6.push((function(e7, n7) {
          e7 ? r6(e7) : t7(n7);
        }));
        try {
          e6.apply(this || Q, i6);
        } catch (e7) {
          r6(e7);
        }
        return n6;
      }
      return Object.setPrototypeOf(t6, Object.getPrototypeOf(e6)), Ee && Object.defineProperty(t6, Ee, { value: t6, enumerable: false, writable: false, configurable: true }), Object.defineProperties(t6, ee(e6));
    }, X.promisify.custom = Ee, X.callbackify = function(e6) {
      if ("function" != typeof e6) throw new TypeError('The "original" argument must be of type Function');
      function t6() {
        for (var t7 = [], r6 = 0; r6 < arguments.length; r6++) t7.push(arguments[r6]);
        var n6 = t7.pop();
        if ("function" != typeof n6) throw new TypeError("The last argument must be of type Function");
        var i6 = this || Q, o6 = function() {
          return n6.apply(i6, arguments);
        };
        e6.apply(this || Q, t7).then((function(e7) {
          Y.nextTick(o6.bind(null, null, e7));
        }), (function(e7) {
          Y.nextTick(De.bind(null, e7, o6));
        }));
      }
      return Object.setPrototypeOf(t6, Object.getPrototypeOf(e6)), Object.defineProperties(t6, ee(e6)), t6;
    };
    X._extend;
    X.callbackify;
    X.debuglog;
    X.deprecate;
    X.format;
    X.inherits;
    X.inspect;
    X.isArray;
    X.isBoolean;
    X.isBuffer;
    X.isDate;
    X.isError;
    X.isFunction;
    X.isNull;
    X.isNullOrUndefined;
    X.isNumber;
    X.isObject;
    X.isPrimitive;
    X.isRegExp;
    X.isString;
    X.isSymbol;
    X.isUndefined;
    X.log;
    X.promisify;
    X._extend;
    X.callbackify;
    X.debuglog;
    X.deprecate;
    X.format;
    X.inherits;
    X.inspect;
    X.isArray;
    X.isBoolean;
    X.isBuffer;
    X.isDate;
    X.isError;
    X.isFunction;
    X.isNull;
    X.isNullOrUndefined;
    X.isNumber;
    X.isObject;
    X.isPrimitive;
    X.isRegExp;
    X.isString;
    X.isSymbol;
    X.isUndefined;
    X.log;
    promisify = X.promisify;
    X.types;
  }
});

// node_modules/@jspm/core/nodelibs/browser/chunk-CjPlbOtt.js
function e2(e6, r6) {
  if (null == e6) throw new TypeError("Cannot convert first argument to object");
  for (var t6 = Object(e6), n6 = 1; n6 < arguments.length; n6++) {
    var o6 = arguments[n6];
    if (null != o6) for (var a6 = Object.keys(Object(o6)), l6 = 0, i6 = a6.length; l6 < i6; l6++) {
      var c6 = a6[l6], b5 = Object.getOwnPropertyDescriptor(o6, c6);
      void 0 !== b5 && b5.enumerable && (t6[c6] = o6[c6]);
    }
  }
  return t6;
}
function i$5() {
  if (a$6) return c$4;
  function e6(t6) {
    return (e6 = "function" == typeof Symbol && "symbol" == typeof Symbol.iterator ? function(t7) {
      return typeof t7;
    } : function(t7) {
      return t7 && "function" == typeof Symbol && t7.constructor === Symbol && t7 !== Symbol.prototype ? "symbol" : typeof t7;
    })(t6);
  }
  function n6(t6, n7) {
    return !n7 || "object" !== e6(n7) && "function" != typeof n7 ? (function(t7) {
      if (void 0 === t7) throw new ReferenceError("this hasn't been initialised - super() hasn't been called");
      return t7;
    })(t6) : n7;
  }
  function r6(t6) {
    return (r6 = Object.setPrototypeOf ? Object.getPrototypeOf : function(t7) {
      return t7.__proto__ || Object.getPrototypeOf(t7);
    })(t6);
  }
  function o6(t6, e7) {
    return (o6 = Object.setPrototypeOf || function(t7, e8) {
      return t7.__proto__ = e8, t7;
    })(t6, e7);
  }
  a$6 = true;
  var i6, u6, l6 = {};
  function f6(t6, e7, c6) {
    c6 || (c6 = Error);
    var a6 = (function(c7) {
      function a7(o7, c8, i7) {
        var u7;
        return !(function(t7, e8) {
          if (!(t7 instanceof e8)) throw new TypeError("Cannot call a class as a function");
        })(this, a7), (u7 = n6(this, r6(a7).call(this, (function(t7, n7, r7) {
          return "string" == typeof e7 ? e7 : e7(t7, n7, r7);
        })(o7, c8, i7)))).code = t6, u7;
      }
      return !(function(t7, e8) {
        if ("function" != typeof e8 && null !== e8) throw new TypeError("Super expression must either be null or a function");
        t7.prototype = Object.create(e8 && e8.prototype, { constructor: { value: t7, writable: true, configurable: true } }), e8 && o6(t7, e8);
      })(a7, c7), a7;
    })(c6);
    l6[t6] = a6;
  }
  function s6(t6, e7) {
    if (Array.isArray(t6)) {
      var n7 = t6.length;
      return t6 = t6.map((function(t7) {
        return String(t7);
      })), n7 > 2 ? "one of ".concat(e7, " ").concat(t6.slice(0, n7 - 1).join(", "), ", or ") + t6[n7 - 1] : 2 === n7 ? "one of ".concat(e7, " ").concat(t6[0], " or ").concat(t6[1]) : "of ".concat(e7, " ").concat(t6[0]);
    }
    return "of ".concat(e7, " ").concat(String(t6));
  }
  return f6("ERR_AMBIGUOUS_ARGUMENT", 'The "%s" argument is ambiguous. %s', TypeError), f6("ERR_INVALID_ARG_TYPE", (function(t6, n7, r7) {
    var o7, c6, u7;
    if (void 0 === i6 && (i6 = tt()), i6("string" == typeof t6, "'name' must be a string"), "string" == typeof n7 && (c6 = "not ", n7.substr(0, c6.length) === c6) ? (o7 = "must not be", n7 = n7.replace(/^not /, "")) : o7 = "must be", (function(t7, e7, n8) {
      return (void 0 === n8 || n8 > t7.length) && (n8 = t7.length), t7.substring(n8 - e7.length, n8) === e7;
    })(t6, " argument")) u7 = "The ".concat(t6, " ").concat(o7, " ").concat(s6(n7, "type"));
    else {
      var l7 = (function(t7, e7, n8) {
        return "number" != typeof n8 && (n8 = 0), !(n8 + e7.length > t7.length) && -1 !== t7.indexOf(e7, n8);
      })(t6, ".") ? "property" : "argument";
      u7 = 'The "'.concat(t6, '" ').concat(l7, " ").concat(o7, " ").concat(s6(n7, "type"));
    }
    return u7 += ". Received type ".concat(e6(r7));
  }), TypeError), f6("ERR_INVALID_ARG_VALUE", (function(e7, n7) {
    var r7 = arguments.length > 2 && void 0 !== arguments[2] ? arguments[2] : "is invalid";
    void 0 === u6 && (u6 = X);
    var o7 = u6.inspect(n7);
    return o7.length > 128 && (o7 = "".concat(o7.slice(0, 128), "...")), "The argument '".concat(e7, "' ").concat(r7, ". Received ").concat(o7);
  }), TypeError), f6("ERR_INVALID_RETURN_VALUE", (function(t6, n7, r7) {
    var o7;
    return o7 = r7 && r7.constructor && r7.constructor.name ? "instance of ".concat(r7.constructor.name) : "type ".concat(e6(r7)), "Expected ".concat(t6, ' to be returned from the "').concat(n7, '"') + " function but got ".concat(o7, ".");
  }), TypeError), f6("ERR_MISSING_ARGS", (function() {
    for (var t6 = arguments.length, e7 = new Array(t6), n7 = 0; n7 < t6; n7++) e7[n7] = arguments[n7];
    void 0 === i6 && (i6 = tt()), i6(e7.length > 0, "At least one arg needs to be specified");
    var r7 = "The ", o7 = e7.length;
    switch (e7 = e7.map((function(t7) {
      return '"'.concat(t7, '"');
    })), o7) {
      case 1:
        r7 += "".concat(e7[0], " argument");
        break;
      case 2:
        r7 += "".concat(e7[0], " and ").concat(e7[1], " arguments");
        break;
      default:
        r7 += e7.slice(0, o7 - 1).join(", "), r7 += ", and ".concat(e7[o7 - 1], " arguments");
    }
    return "".concat(r7, " must be specified");
  }), TypeError), c$4.codes = l6, c$4;
}
function f$6() {
  if (l$6) return u$5;
  l$6 = true;
  var n6 = T$1;
  function r6(t6, e6, n7) {
    return e6 in t6 ? Object.defineProperty(t6, e6, { value: n7, enumerable: true, configurable: true, writable: true }) : t6[e6] = n7, t6;
  }
  function o6(t6, e6) {
    for (var n7 = 0; n7 < e6.length; n7++) {
      var r7 = e6[n7];
      r7.enumerable = r7.enumerable || false, r7.configurable = true, "value" in r7 && (r7.writable = true), Object.defineProperty(t6, r7.key, r7);
    }
  }
  function c6(t6, e6) {
    return !e6 || "object" !== y6(e6) && "function" != typeof e6 ? a6(t6) : e6;
  }
  function a6(t6) {
    if (void 0 === t6) throw new ReferenceError("this hasn't been initialised - super() hasn't been called");
    return t6;
  }
  function f6(t6) {
    var e6 = "function" == typeof Map ? /* @__PURE__ */ new Map() : void 0;
    return (f6 = function(t7) {
      if (null === t7 || (n7 = t7, -1 === Function.toString.call(n7).indexOf("[native code]"))) return t7;
      var n7;
      if ("function" != typeof t7) throw new TypeError("Super expression must either be null or a function");
      if (void 0 !== e6) {
        if (e6.has(t7)) return e6.get(t7);
        e6.set(t7, r7);
      }
      function r7() {
        return p6(t7, arguments, h6(this).constructor);
      }
      return r7.prototype = Object.create(t7.prototype, { constructor: { value: r7, enumerable: false, writable: true, configurable: true } }), g5(r7, t7);
    })(t6);
  }
  function s6() {
    if ("undefined" == typeof Reflect || !Reflect.construct) return false;
    if (Reflect.construct.sham) return false;
    if ("function" == typeof Proxy) return true;
    try {
      return Date.prototype.toString.call(Reflect.construct(Date, [], (function() {
      }))), true;
    } catch (t6) {
      return false;
    }
  }
  function p6(t6, e6, n7) {
    return (p6 = s6() ? Reflect.construct : function(t7, e7, n8) {
      var r7 = [null];
      r7.push.apply(r7, e7);
      var o7 = new (Function.bind.apply(t7, r7))();
      return n8 && g5(o7, n8.prototype), o7;
    }).apply(null, arguments);
  }
  function g5(t6, e6) {
    return (g5 = Object.setPrototypeOf || function(t7, e7) {
      return t7.__proto__ = e7, t7;
    })(t6, e6);
  }
  function h6(t6) {
    return (h6 = Object.setPrototypeOf ? Object.getPrototypeOf : function(t7) {
      return t7.__proto__ || Object.getPrototypeOf(t7);
    })(t6);
  }
  function y6(t6) {
    return (y6 = "function" == typeof Symbol && "symbol" == typeof Symbol.iterator ? function(t7) {
      return typeof t7;
    } : function(t7) {
      return t7 && "function" == typeof Symbol && t7.constructor === Symbol && t7 !== Symbol.prototype ? "symbol" : typeof t7;
    })(t6);
  }
  var b5 = X.inspect, v6 = i$5().codes.ERR_INVALID_ARG_TYPE;
  function d5(t6, e6, n7) {
    return (void 0 === n7 || n7 > t6.length) && (n7 = t6.length), t6.substring(n7 - e6.length, n7) === e6;
  }
  var m5 = "", E4 = "", w4 = "", S4 = "", j4 = { deepStrictEqual: "Expected values to be strictly deep-equal:", strictEqual: "Expected values to be strictly equal:", strictEqualObject: 'Expected "actual" to be reference-equal to "expected":', deepEqual: "Expected values to be loosely deep-equal:", equal: "Expected values to be loosely equal:", notDeepStrictEqual: 'Expected "actual" not to be strictly deep-equal to:', notStrictEqual: 'Expected "actual" to be strictly unequal to:', notStrictEqualObject: 'Expected "actual" not to be reference-equal to "expected":', notDeepEqual: 'Expected "actual" not to be loosely deep-equal to:', notEqual: 'Expected "actual" to be loosely unequal to:', notIdentical: "Values identical but not reference-equal:" };
  function O5(t6) {
    var e6 = Object.keys(t6), n7 = Object.create(Object.getPrototypeOf(t6));
    return e6.forEach((function(e7) {
      n7[e7] = t6[e7];
    })), Object.defineProperty(n7, "message", { value: t6.message }), n7;
  }
  function x4(t6) {
    return b5(t6, { compact: false, customInspect: false, depth: 1e3, maxArrayLength: 1 / 0, showHidden: false, breakLength: 1 / 0, showProxy: false, sorted: true, getters: true });
  }
  function q3(t6, e6, r7) {
    var o7 = "", c7 = "", a7 = 0, i6 = "", u6 = false, l6 = x4(t6), f7 = l6.split("\n"), s7 = x4(e6).split("\n"), p7 = 0, g6 = "";
    if ("strictEqual" === r7 && "object" === y6(t6) && "object" === y6(e6) && null !== t6 && null !== e6 && (r7 = "strictEqualObject"), 1 === f7.length && 1 === s7.length && f7[0] !== s7[0]) {
      var h7 = f7[0].length + s7[0].length;
      if (h7 <= 10) {
        if (!("object" === y6(t6) && null !== t6 || "object" === y6(e6) && null !== e6 || 0 === t6 && 0 === e6)) return "".concat(j4[r7], "\n\n") + "".concat(f7[0], " !== ").concat(s7[0], "\n");
      } else if ("strictEqualObject" !== r7) {
        if (h7 < (n6.stderr && n6.stderr.isTTY ? n6.stderr.columns : 80)) {
          for (; f7[0][p7] === s7[0][p7]; ) p7++;
          p7 > 2 && (g6 = "\n  ".concat((function(t7, e7) {
            if (e7 = Math.floor(e7), 0 == t7.length || 0 == e7) return "";
            var n7 = t7.length * e7;
            for (e7 = Math.floor(Math.log(e7) / Math.log(2)); e7; ) t7 += t7, e7--;
            return t7 += t7.substring(0, n7 - t7.length);
          })(" ", p7), "^"), p7 = 0);
        }
      }
    }
    for (var b6 = f7[f7.length - 1], v7 = s7[s7.length - 1]; b6 === v7 && (p7++ < 2 ? i6 = "\n  ".concat(b6).concat(i6) : o7 = b6, f7.pop(), s7.pop(), 0 !== f7.length && 0 !== s7.length); ) b6 = f7[f7.length - 1], v7 = s7[s7.length - 1];
    var O6 = Math.max(f7.length, s7.length);
    if (0 === O6) {
      var q4 = l6.split("\n");
      if (q4.length > 30) for (q4[26] = "".concat(m5, "...").concat(S4); q4.length > 27; ) q4.pop();
      return "".concat(j4.notIdentical, "\n\n").concat(q4.join("\n"), "\n");
    }
    p7 > 3 && (i6 = "\n".concat(m5, "...").concat(S4).concat(i6), u6 = true), "" !== o7 && (i6 = "\n  ".concat(o7).concat(i6), o7 = "");
    var R5 = 0, A4 = j4[r7] + "\n".concat(E4, "+ actual").concat(S4, " ").concat(w4, "- expected").concat(S4), k4 = " ".concat(m5, "...").concat(S4, " Lines skipped");
    for (p7 = 0; p7 < O6; p7++) {
      var _4 = p7 - a7;
      if (f7.length < p7 + 1) _4 > 1 && p7 > 2 && (_4 > 4 ? (c7 += "\n".concat(m5, "...").concat(S4), u6 = true) : _4 > 3 && (c7 += "\n  ".concat(s7[p7 - 2]), R5++), c7 += "\n  ".concat(s7[p7 - 1]), R5++), a7 = p7, o7 += "\n".concat(w4, "-").concat(S4, " ").concat(s7[p7]), R5++;
      else if (s7.length < p7 + 1) _4 > 1 && p7 > 2 && (_4 > 4 ? (c7 += "\n".concat(m5, "...").concat(S4), u6 = true) : _4 > 3 && (c7 += "\n  ".concat(f7[p7 - 2]), R5++), c7 += "\n  ".concat(f7[p7 - 1]), R5++), a7 = p7, c7 += "\n".concat(E4, "+").concat(S4, " ").concat(f7[p7]), R5++;
      else {
        var T4 = s7[p7], P4 = f7[p7], I4 = P4 !== T4 && (!d5(P4, ",") || P4.slice(0, -1) !== T4);
        I4 && d5(T4, ",") && T4.slice(0, -1) === P4 && (I4 = false, P4 += ","), I4 ? (_4 > 1 && p7 > 2 && (_4 > 4 ? (c7 += "\n".concat(m5, "...").concat(S4), u6 = true) : _4 > 3 && (c7 += "\n  ".concat(f7[p7 - 2]), R5++), c7 += "\n  ".concat(f7[p7 - 1]), R5++), a7 = p7, c7 += "\n".concat(E4, "+").concat(S4, " ").concat(P4), o7 += "\n".concat(w4, "-").concat(S4, " ").concat(T4), R5 += 2) : (c7 += o7, o7 = "", 1 !== _4 && 0 !== p7 || (c7 += "\n  ".concat(P4), R5++));
      }
      if (R5 > 20 && p7 < O6 - 2) return "".concat(A4).concat(k4, "\n").concat(c7, "\n").concat(m5, "...").concat(S4).concat(o7, "\n") + "".concat(m5, "...").concat(S4);
    }
    return "".concat(A4).concat(u6 ? k4 : "", "\n").concat(c7).concat(o7).concat(i6).concat(g6);
  }
  var R4 = (function(t6) {
    function e6(t7) {
      var r7;
      if (!(function(t8, e7) {
        if (!(t8 instanceof e7)) throw new TypeError("Cannot call a class as a function");
      })(this, e6), "object" !== y6(t7) || null === t7) throw new v6("options", "Object", t7);
      var o7 = t7.message, i7 = t7.operator, u7 = t7.stackStartFn, l6 = t7.actual, f7 = t7.expected, s7 = Error.stackTraceLimit;
      if (Error.stackTraceLimit = 0, null != o7) r7 = c6(this, h6(e6).call(this, String(o7)));
      else if (n6.stderr && n6.stderr.isTTY && (n6.stderr && n6.stderr.getColorDepth && 1 !== n6.stderr.getColorDepth() ? (m5 = "\x1B[34m", E4 = "\x1B[32m", S4 = "\x1B[39m", w4 = "\x1B[31m") : (m5 = "", E4 = "", S4 = "", w4 = "")), "object" === y6(l6) && null !== l6 && "object" === y6(f7) && null !== f7 && "stack" in l6 && l6 instanceof Error && "stack" in f7 && f7 instanceof Error && (l6 = O5(l6), f7 = O5(f7)), "deepStrictEqual" === i7 || "strictEqual" === i7) r7 = c6(this, h6(e6).call(this, q3(l6, f7, i7)));
      else if ("notDeepStrictEqual" === i7 || "notStrictEqual" === i7) {
        var p7 = j4[i7], g6 = x4(l6).split("\n");
        if ("notStrictEqual" === i7 && "object" === y6(l6) && null !== l6 && (p7 = j4.notStrictEqualObject), g6.length > 30) for (g6[26] = "".concat(m5, "...").concat(S4); g6.length > 27; ) g6.pop();
        r7 = 1 === g6.length ? c6(this, h6(e6).call(this, "".concat(p7, " ").concat(g6[0]))) : c6(this, h6(e6).call(this, "".concat(p7, "\n\n").concat(g6.join("\n"), "\n")));
      } else {
        var b6 = x4(l6), d6 = "", R5 = j4[i7];
        "notDeepEqual" === i7 || "notEqual" === i7 ? (b6 = "".concat(j4[i7], "\n\n").concat(b6)).length > 1024 && (b6 = "".concat(b6.slice(0, 1021), "...")) : (d6 = "".concat(x4(f7)), b6.length > 512 && (b6 = "".concat(b6.slice(0, 509), "...")), d6.length > 512 && (d6 = "".concat(d6.slice(0, 509), "...")), "deepEqual" === i7 || "equal" === i7 ? b6 = "".concat(R5, "\n\n").concat(b6, "\n\nshould equal\n\n") : d6 = " ".concat(i7, " ").concat(d6)), r7 = c6(this, h6(e6).call(this, "".concat(b6).concat(d6)));
      }
      return Error.stackTraceLimit = s7, r7.generatedMessage = !o7, Object.defineProperty(a6(r7), "name", { value: "AssertionError [ERR_ASSERTION]", enumerable: false, writable: true, configurable: true }), r7.code = "ERR_ASSERTION", r7.actual = l6, r7.expected = f7, r7.operator = i7, Error.captureStackTrace && Error.captureStackTrace(a6(r7), u7), r7.stack, r7.name = "AssertionError", c6(r7);
    }
    var i6, u6;
    return !(function(t7, e7) {
      if ("function" != typeof e7 && null !== e7) throw new TypeError("Super expression must either be null or a function");
      t7.prototype = Object.create(e7 && e7.prototype, { constructor: { value: t7, writable: true, configurable: true } }), e7 && g5(t7, e7);
    })(e6, t6), i6 = e6, (u6 = [{ key: "toString", value: function() {
      return "".concat(this.name, " [").concat(this.code, "]: ").concat(this.message);
    } }, { key: b5.custom, value: function(t7, e7) {
      return b5(this, (function(t8) {
        for (var e8 = 1; e8 < arguments.length; e8++) {
          var n7 = null != arguments[e8] ? arguments[e8] : {}, o7 = Object.keys(n7);
          "function" == typeof Object.getOwnPropertySymbols && (o7 = o7.concat(Object.getOwnPropertySymbols(n7).filter((function(t9) {
            return Object.getOwnPropertyDescriptor(n7, t9).enumerable;
          })))), o7.forEach((function(e9) {
            r6(t8, e9, n7[e9]);
          }));
        }
        return t8;
      })({}, e7, { customInspect: false, depth: 0 }));
    } }]) && o6(i6.prototype, u6), e6;
  })(f6(Error));
  return u$5 = R4;
}
function s$3(t6, e6) {
  return (function(t7) {
    if (Array.isArray(t7)) return t7;
  })(t6) || (function(t7, e7) {
    var n6 = [], r6 = true, o6 = false, c6 = void 0;
    try {
      for (var a6, i6 = t7[Symbol.iterator](); !(r6 = (a6 = i6.next()).done) && (n6.push(a6.value), !e7 || n6.length !== e7); r6 = true) ;
    } catch (t8) {
      o6 = true, c6 = t8;
    } finally {
      try {
        r6 || null == i6.return || i6.return();
      } finally {
        if (o6) throw c6;
      }
    }
    return n6;
  })(t6, e6) || (function() {
    throw new TypeError("Invalid attempt to destructure non-iterable instance");
  })();
}
function p$3(t6) {
  return (p$3 = "function" == typeof Symbol && "symbol" == typeof Symbol.iterator ? function(t7) {
    return typeof t7;
  } : function(t7) {
    return t7 && "function" == typeof Symbol && t7.constructor === Symbol && t7 !== Symbol.prototype ? "symbol" : typeof t7;
  })(t6);
}
function m$2(t6) {
  return t6.call.bind(t6);
}
function U2(t6) {
  if (0 === t6.length || t6.length > 10) return true;
  for (var e6 = 0; e6 < t6.length; e6++) {
    var n6 = t6.charCodeAt(e6);
    if (n6 < 48 || n6 > 57) return true;
  }
  return 10 === t6.length && t6 >= Math.pow(2, 32);
}
function G2(t6) {
  return Object.keys(t6).filter(U2).concat(v$1(t6).filter(Object.prototype.propertyIsEnumerable.bind(t6)));
}
function V2(t6, e6) {
  if (t6 === e6) return 0;
  for (var n6 = t6.length, r6 = e6.length, o6 = 0, c6 = Math.min(n6, r6); o6 < c6; ++o6) if (t6[o6] !== e6[o6]) {
    n6 = t6[o6], r6 = e6[o6];
    break;
  }
  return n6 < r6 ? -1 : r6 < n6 ? 1 : 0;
}
function B2(t6, e6, n6, r6) {
  if (t6 === e6) return 0 !== t6 || (!n6 || b$1(t6, e6));
  if (n6) {
    if ("object" !== p$3(t6)) return "number" == typeof t6 && d$12(t6) && d$12(e6);
    if ("object" !== p$3(e6) || null === t6 || null === e6) return false;
    if (Object.getPrototypeOf(t6) !== Object.getPrototypeOf(e6)) return false;
  } else {
    if (null === t6 || "object" !== p$3(t6)) return (null === e6 || "object" !== p$3(e6)) && t6 == e6;
    if (null === e6 || "object" !== p$3(e6)) return false;
  }
  var o6, c6, a6, i6, u6 = S2(t6);
  if (u6 !== S2(e6)) return false;
  if (Array.isArray(t6)) {
    if (t6.length !== e6.length) return false;
    var l6 = G2(t6), f6 = G2(e6);
    return l6.length === f6.length && C2(t6, e6, n6, r6, 1, l6);
  }
  if ("[object Object]" === u6 && (!R2(t6) && R2(e6) || !k2(t6) && k2(e6))) return false;
  if (q2(t6)) {
    if (!q2(e6) || Date.prototype.getTime.call(t6) !== Date.prototype.getTime.call(e6)) return false;
  } else if (A$1(t6)) {
    if (!A$1(e6) || (a6 = t6, i6 = e6, !(g$1 ? a6.source === i6.source && a6.flags === i6.flags : RegExp.prototype.toString.call(a6) === RegExp.prototype.toString.call(i6)))) return false;
  } else if (_2(t6) || t6 instanceof Error) {
    if (t6.message !== e6.message || t6.name !== e6.name) return false;
  } else {
    if (x2(t6)) {
      if (n6 || !L2(t6) && !M2(t6)) {
        if (!(function(t7, e7) {
          return t7.byteLength === e7.byteLength && 0 === V2(new Uint8Array(t7.buffer, t7.byteOffset, t7.byteLength), new Uint8Array(e7.buffer, e7.byteOffset, e7.byteLength));
        })(t6, e6)) return false;
      } else if (!(function(t7, e7) {
        if (t7.byteLength !== e7.byteLength) return false;
        for (var n7 = 0; n7 < t7.byteLength; n7++) if (t7[n7] !== e7[n7]) return false;
        return true;
      })(t6, e6)) return false;
      var s6 = G2(t6), h6 = G2(e6);
      return s6.length === h6.length && C2(t6, e6, n6, r6, 0, s6);
    }
    if (k2(t6)) return !(!k2(e6) || t6.size !== e6.size) && C2(t6, e6, n6, r6, 2);
    if (R2(t6)) return !(!R2(e6) || t6.size !== e6.size) && C2(t6, e6, n6, r6, 3);
    if (O2(t6)) {
      if (c6 = e6, (o6 = t6).byteLength !== c6.byteLength || 0 !== V2(new Uint8Array(o6), new Uint8Array(c6))) return false;
    } else if (T2(t6) && !(function(t7, e7) {
      return P$1(t7) ? P$1(e7) && b$1(Number.prototype.valueOf.call(t7), Number.prototype.valueOf.call(e7)) : I2(t7) ? I2(e7) && String.prototype.valueOf.call(t7) === String.prototype.valueOf.call(e7) : D2(t7) ? D2(e7) && Boolean.prototype.valueOf.call(t7) === Boolean.prototype.valueOf.call(e7) : F2(t7) ? F2(e7) && BigInt.prototype.valueOf.call(t7) === BigInt.prototype.valueOf.call(e7) : N$1(e7) && Symbol.prototype.valueOf.call(t7) === Symbol.prototype.valueOf.call(e7);
    })(t6, e6)) return false;
  }
  return C2(t6, e6, n6, r6, 0);
}
function z2(t6, e6) {
  return e6.filter((function(e7) {
    return w$1(t6, e7);
  }));
}
function C2(t6, e6, n6, r6, o6, c6) {
  if (5 === arguments.length) {
    c6 = Object.keys(t6);
    var a6 = Object.keys(e6);
    if (c6.length !== a6.length) return false;
  }
  for (var i6 = 0; i6 < c6.length; i6++) if (!E2(e6, c6[i6])) return false;
  if (n6 && 5 === arguments.length) {
    var u6 = v$1(t6);
    if (0 !== u6.length) {
      var l6 = 0;
      for (i6 = 0; i6 < u6.length; i6++) {
        var f6 = u6[i6];
        if (w$1(t6, f6)) {
          if (!w$1(e6, f6)) return false;
          c6.push(f6), l6++;
        } else if (w$1(e6, f6)) return false;
      }
      var s6 = v$1(e6);
      if (u6.length !== s6.length && z2(e6, s6).length !== l6) return false;
    } else {
      var p6 = v$1(e6);
      if (0 !== p6.length && 0 !== z2(e6, p6).length) return false;
    }
  }
  if (0 === c6.length && (0 === o6 || 1 === o6 && 0 === t6.length || 0 === t6.size)) return true;
  if (void 0 === r6) r6 = { val1: /* @__PURE__ */ new Map(), val2: /* @__PURE__ */ new Map(), position: 0 };
  else {
    var g5 = r6.val1.get(t6);
    if (void 0 !== g5) {
      var h6 = r6.val2.get(e6);
      if (void 0 !== h6) return g5 === h6;
    }
    r6.position++;
  }
  r6.val1.set(t6, r6.position), r6.val2.set(e6, r6.position);
  var y6 = Q2(t6, e6, n6, c6, r6, o6);
  return r6.val1.delete(t6), r6.val2.delete(e6), y6;
}
function Y2(t6, e6, n6, r6) {
  for (var o6 = h$12(t6), c6 = 0; c6 < o6.length; c6++) {
    var a6 = o6[c6];
    if (B2(e6, a6, n6, r6)) return t6.delete(a6), true;
  }
  return false;
}
function W2(t6) {
  switch (p$3(t6)) {
    case "undefined":
      return null;
    case "object":
      return;
    case "symbol":
      return false;
    case "string":
      t6 = +t6;
    case "number":
      if (d$12(t6)) return false;
  }
  return true;
}
function H2(t6, e6, n6) {
  var r6 = W2(n6);
  return null != r6 ? r6 : e6.has(r6) && !t6.has(r6);
}
function J2(t6, e6, n6, r6, o6) {
  var c6 = W2(n6);
  if (null != c6) return c6;
  var a6 = e6.get(c6);
  return !(void 0 === a6 && !e6.has(c6) || !B2(r6, a6, false, o6)) && (!t6.has(c6) && B2(r6, a6, false, o6));
}
function K2(t6, e6, n6, r6, o6, c6) {
  for (var a6 = h$12(t6), i6 = 0; i6 < a6.length; i6++) {
    var u6 = a6[i6];
    if (B2(n6, u6, o6, c6) && B2(r6, e6.get(u6), o6, c6)) return t6.delete(u6), true;
  }
  return false;
}
function Q2(t6, e6, n6, r6, o6, c6) {
  var a6 = 0;
  if (2 === c6) {
    if (!(function(t7, e7, n7, r7) {
      for (var o7 = null, c7 = h$12(t7), a7 = 0; a7 < c7.length; a7++) {
        var i7 = c7[a7];
        if ("object" === p$3(i7) && null !== i7) null === o7 && (o7 = /* @__PURE__ */ new Set()), o7.add(i7);
        else if (!e7.has(i7)) {
          if (n7) return false;
          if (!H2(t7, e7, i7)) return false;
          null === o7 && (o7 = /* @__PURE__ */ new Set()), o7.add(i7);
        }
      }
      if (null !== o7) {
        for (var u7 = h$12(e7), l7 = 0; l7 < u7.length; l7++) {
          var f6 = u7[l7];
          if ("object" === p$3(f6) && null !== f6) {
            if (!Y2(o7, f6, n7, r7)) return false;
          } else if (!n7 && !t7.has(f6) && !Y2(o7, f6, n7, r7)) return false;
        }
        return 0 === o7.size;
      }
      return true;
    })(t6, e6, n6, o6)) return false;
  } else if (3 === c6) {
    if (!(function(t7, e7, n7, r7) {
      for (var o7 = null, c7 = y$2(t7), a7 = 0; a7 < c7.length; a7++) {
        var i7 = s$3(c7[a7], 2), u7 = i7[0], l7 = i7[1];
        if ("object" === p$3(u7) && null !== u7) null === o7 && (o7 = /* @__PURE__ */ new Set()), o7.add(u7);
        else {
          var f6 = e7.get(u7);
          if (void 0 === f6 && !e7.has(u7) || !B2(l7, f6, n7, r7)) {
            if (n7) return false;
            if (!J2(t7, e7, u7, l7, r7)) return false;
            null === o7 && (o7 = /* @__PURE__ */ new Set()), o7.add(u7);
          }
        }
      }
      if (null !== o7) {
        for (var g5 = y$2(e7), h6 = 0; h6 < g5.length; h6++) {
          var b5 = s$3(g5[h6], 2), v6 = (u7 = b5[0], b5[1]);
          if ("object" === p$3(u7) && null !== u7) {
            if (!K2(o7, t7, u7, v6, n7, r7)) return false;
          } else if (!(n7 || t7.has(u7) && B2(t7.get(u7), v6, false, r7) || K2(o7, t7, u7, v6, false, r7))) return false;
        }
        return 0 === o7.size;
      }
      return true;
    })(t6, e6, n6, o6)) return false;
  } else if (1 === c6) for (; a6 < t6.length; a6++) {
    if (!E2(t6, a6)) {
      if (E2(e6, a6)) return false;
      for (var i6 = Object.keys(t6); a6 < i6.length; a6++) {
        var u6 = i6[a6];
        if (!E2(e6, u6) || !B2(t6[u6], e6[u6], n6, o6)) return false;
      }
      return i6.length === Object.keys(e6).length;
    }
    if (!E2(e6, a6) || !B2(t6[a6], e6[a6], n6, o6)) return false;
  }
  for (a6 = 0; a6 < r6.length; a6++) {
    var l6 = r6[a6];
    if (!B2(t6[l6], e6[l6], n6, o6)) return false;
  }
  return true;
}
function tt() {
  if ($$1) return Z2;
  $$1 = true;
  var o6 = T$1;
  function c6(t6) {
    return (c6 = "function" == typeof Symbol && "symbol" == typeof Symbol.iterator ? function(t7) {
      return typeof t7;
    } : function(t7) {
      return t7 && "function" == typeof Symbol && t7.constructor === Symbol && t7 !== Symbol.prototype ? "symbol" : typeof t7;
    })(t6);
  }
  var a6, u6, l6 = i$5().codes, s6 = l6.ERR_AMBIGUOUS_ARGUMENT, p6 = l6.ERR_INVALID_ARG_TYPE, g5 = l6.ERR_INVALID_ARG_VALUE, h6 = l6.ERR_INVALID_RETURN_VALUE, y6 = l6.ERR_MISSING_ARGS, b5 = f$6(), v6 = X.inspect, d5 = X.types, m$13 = d5.isPromise, E4 = d5.isRegExp, w4 = Object.assign ? Object.assign : r2.assign, S4 = Object.is ? Object.is : m2;
  function j4() {
    a6 = X2.isDeepEqual, u6 = X2.isDeepStrictEqual;
  }
  var O5 = false, x4 = Z2 = k4, q3 = {};
  function R4(t6) {
    if (t6.message instanceof Error) throw t6.message;
    throw new b5(t6);
  }
  function A4(t6, e6, n6, r6) {
    if (!n6) {
      var o7 = false;
      if (0 === e6) o7 = true, r6 = "No value argument passed to `assert.ok()`";
      else if (r6 instanceof Error) throw r6;
      var c7 = new b5({ actual: n6, expected: true, message: r6, operator: "==", stackStartFn: t6 });
      throw c7.generatedMessage = o7, c7;
    }
  }
  function k4() {
    for (var t6 = arguments.length, e6 = new Array(t6), n6 = 0; n6 < t6; n6++) e6[n6] = arguments[n6];
    A4.apply(void 0, [k4, e6.length].concat(e6));
  }
  x4.fail = function t6(e6, n6, r6, c7, a7) {
    var i6, u7 = arguments.length;
    if (0 === u7) i6 = "Failed";
    else if (1 === u7) r6 = e6, e6 = void 0;
    else {
      if (false === O5) {
        O5 = true;
        var l7 = o6.emitWarning ? o6.emitWarning : console.warn.bind(console);
        l7("assert.fail() with more than one argument is deprecated. Please use assert.strictEqual() instead or only pass a message.", "DeprecationWarning", "DEP0094");
      }
      2 === u7 && (c7 = "!=");
    }
    if (r6 instanceof Error) throw r6;
    var f6 = { actual: e6, expected: n6, operator: void 0 === c7 ? "fail" : c7, stackStartFn: a7 || t6 };
    void 0 !== r6 && (f6.message = r6);
    var s7 = new b5(f6);
    throw i6 && (s7.message = i6, s7.generatedMessage = true), s7;
  }, x4.AssertionError = b5, x4.ok = k4, x4.equal = function t6(e6, n6, r6) {
    if (arguments.length < 2) throw new y6("actual", "expected");
    e6 != n6 && R4({ actual: e6, expected: n6, message: r6, operator: "==", stackStartFn: t6 });
  }, x4.notEqual = function t6(e6, n6, r6) {
    if (arguments.length < 2) throw new y6("actual", "expected");
    e6 == n6 && R4({ actual: e6, expected: n6, message: r6, operator: "!=", stackStartFn: t6 });
  }, x4.deepEqual = function t6(e6, n6, r6) {
    if (arguments.length < 2) throw new y6("actual", "expected");
    void 0 === a6 && j4(), a6(e6, n6) || R4({ actual: e6, expected: n6, message: r6, operator: "deepEqual", stackStartFn: t6 });
  }, x4.notDeepEqual = function t6(e6, n6, r6) {
    if (arguments.length < 2) throw new y6("actual", "expected");
    void 0 === a6 && j4(), a6(e6, n6) && R4({ actual: e6, expected: n6, message: r6, operator: "notDeepEqual", stackStartFn: t6 });
  }, x4.deepStrictEqual = function t6(e6, n6, r6) {
    if (arguments.length < 2) throw new y6("actual", "expected");
    void 0 === a6 && j4(), u6(e6, n6) || R4({ actual: e6, expected: n6, message: r6, operator: "deepStrictEqual", stackStartFn: t6 });
  }, x4.notDeepStrictEqual = function t6(e6, n6, r6) {
    if (arguments.length < 2) throw new y6("actual", "expected");
    void 0 === a6 && j4();
    u6(e6, n6) && R4({ actual: e6, expected: n6, message: r6, operator: "notDeepStrictEqual", stackStartFn: t6 });
  }, x4.strictEqual = function t6(e6, n6, r6) {
    if (arguments.length < 2) throw new y6("actual", "expected");
    S4(e6, n6) || R4({ actual: e6, expected: n6, message: r6, operator: "strictEqual", stackStartFn: t6 });
  }, x4.notStrictEqual = function t6(e6, n6, r6) {
    if (arguments.length < 2) throw new y6("actual", "expected");
    S4(e6, n6) && R4({ actual: e6, expected: n6, message: r6, operator: "notStrictEqual", stackStartFn: t6 });
  };
  var _4 = function t6(e6, n6, r6) {
    var o7 = this;
    !(function(t7, e7) {
      if (!(t7 instanceof e7)) throw new TypeError("Cannot call a class as a function");
    })(this, t6), n6.forEach((function(t7) {
      t7 in e6 && (void 0 !== r6 && "string" == typeof r6[t7] && E4(e6[t7]) && e6[t7].test(r6[t7]) ? o7[t7] = r6[t7] : o7[t7] = e6[t7]);
    }));
  };
  function T4(t6, e6, n6, r6, o7, c7) {
    if (!(n6 in t6) || !u6(t6[n6], e6[n6])) {
      if (!r6) {
        var a7 = new _4(t6, o7), i6 = new _4(e6, o7, t6), l7 = new b5({ actual: a7, expected: i6, operator: "deepStrictEqual", stackStartFn: c7 });
        throw l7.actual = t6, l7.expected = e6, l7.operator = c7.name, l7;
      }
      R4({ actual: t6, expected: e6, message: r6, operator: c7.name, stackStartFn: c7 });
    }
  }
  function P4(t6, e6, n6, r6) {
    if ("function" != typeof e6) {
      if (E4(e6)) return e6.test(t6);
      if (2 === arguments.length) throw new p6("expected", ["Function", "RegExp"], e6);
      if ("object" !== c6(t6) || null === t6) {
        var o7 = new b5({ actual: t6, expected: e6, message: n6, operator: "deepStrictEqual", stackStartFn: r6 });
        throw o7.operator = r6.name, o7;
      }
      var i6 = Object.keys(e6);
      if (e6 instanceof Error) i6.push("name", "message");
      else if (0 === i6.length) throw new g5("error", e6, "may not be an empty object");
      return void 0 === a6 && j4(), i6.forEach((function(o8) {
        "string" == typeof t6[o8] && E4(e6[o8]) && e6[o8].test(t6[o8]) || T4(t6, e6, o8, n6, i6, r6);
      })), true;
    }
    return void 0 !== e6.prototype && t6 instanceof e6 || !Error.isPrototypeOf(e6) && true === e6.call({}, t6);
  }
  function I4(t6) {
    if ("function" != typeof t6) throw new p6("fn", "Function", t6);
    try {
      t6();
    } catch (t7) {
      return t7;
    }
    return q3;
  }
  function D4(t6) {
    return m$13(t6) || null !== t6 && "object" === c6(t6) && "function" == typeof t6.then && "function" == typeof t6.catch;
  }
  function F4(t6) {
    return Promise.resolve().then((function() {
      var e6;
      if ("function" == typeof t6) {
        if (!D4(e6 = t6())) throw new h6("instance of Promise", "promiseFn", e6);
      } else {
        if (!D4(t6)) throw new p6("promiseFn", ["Function", "Promise"], t6);
        e6 = t6;
      }
      return Promise.resolve().then((function() {
        return e6;
      })).then((function() {
        return q3;
      })).catch((function(t7) {
        return t7;
      }));
    }));
  }
  function N4(t6, e6, n6, r6) {
    if ("string" == typeof n6) {
      if (4 === arguments.length) throw new p6("error", ["Object", "Error", "Function", "RegExp"], n6);
      if ("object" === c6(e6) && null !== e6) {
        if (e6.message === n6) throw new s6("error/message", 'The error message "'.concat(e6.message, '" is identical to the message.'));
      } else if (e6 === n6) throw new s6("error/message", 'The error "'.concat(e6, '" is identical to the message.'));
      r6 = n6, n6 = void 0;
    } else if (null != n6 && "object" !== c6(n6) && "function" != typeof n6) throw new p6("error", ["Object", "Error", "Function", "RegExp"], n6);
    if (e6 === q3) {
      var o7 = "";
      n6 && n6.name && (o7 += " (".concat(n6.name, ")")), o7 += r6 ? ": ".concat(r6) : ".";
      var a7 = "rejects" === t6.name ? "rejection" : "exception";
      R4({ actual: void 0, expected: n6, operator: t6.name, message: "Missing expected ".concat(a7).concat(o7), stackStartFn: t6 });
    }
    if (n6 && !P4(e6, n6, r6, t6)) throw e6;
  }
  function L4(t6, e6, n6, r6) {
    if (e6 !== q3) {
      if ("string" == typeof n6 && (r6 = n6, n6 = void 0), !n6 || P4(e6, n6)) {
        var o7 = r6 ? ": ".concat(r6) : ".", c7 = "doesNotReject" === t6.name ? "rejection" : "exception";
        R4({ actual: e6, expected: n6, operator: t6.name, message: "Got unwanted ".concat(c7).concat(o7, "\n") + 'Actual message: "'.concat(e6 && e6.message, '"'), stackStartFn: t6 });
      }
      throw e6;
    }
  }
  function M4() {
    for (var t6 = arguments.length, e6 = new Array(t6), n6 = 0; n6 < t6; n6++) e6[n6] = arguments[n6];
    A4.apply(void 0, [M4, e6.length].concat(e6));
  }
  return x4.throws = function t6(e6) {
    for (var n6 = arguments.length, r6 = new Array(n6 > 1 ? n6 - 1 : 0), o7 = 1; o7 < n6; o7++) r6[o7 - 1] = arguments[o7];
    N4.apply(void 0, [t6, I4(e6)].concat(r6));
  }, x4.rejects = function t6(e6) {
    for (var n6 = arguments.length, r6 = new Array(n6 > 1 ? n6 - 1 : 0), o7 = 1; o7 < n6; o7++) r6[o7 - 1] = arguments[o7];
    return F4(e6).then((function(e7) {
      return N4.apply(void 0, [t6, e7].concat(r6));
    }));
  }, x4.doesNotThrow = function t6(e6) {
    for (var n6 = arguments.length, r6 = new Array(n6 > 1 ? n6 - 1 : 0), o7 = 1; o7 < n6; o7++) r6[o7 - 1] = arguments[o7];
    L4.apply(void 0, [t6, I4(e6)].concat(r6));
  }, x4.doesNotReject = function t6(e6) {
    for (var n6 = arguments.length, r6 = new Array(n6 > 1 ? n6 - 1 : 0), o7 = 1; o7 < n6; o7++) r6[o7 - 1] = arguments[o7];
    return F4(e6).then((function(e7) {
      return L4.apply(void 0, [t6, e7].concat(r6));
    }));
  }, x4.ifError = function t6(e6) {
    if (null != e6) {
      var n6 = "ifError got unwanted exception: ";
      "object" === c6(e6) && "string" == typeof e6.message ? 0 === e6.message.length && e6.constructor ? n6 += e6.constructor.name : n6 += e6.message : n6 += v6(e6);
      var r6 = new b5({ actual: e6, expected: null, operator: "ifError", message: n6, stackStartFn: t6 }), o7 = e6.stack;
      if ("string" == typeof o7) {
        var a7 = o7.split("\n");
        a7.shift();
        for (var i6 = r6.stack.split("\n"), u7 = 0; u7 < a7.length; u7++) {
          var l7 = i6.indexOf(a7[u7]);
          if (-1 !== l7) {
            i6 = i6.slice(0, l7);
            break;
          }
        }
        r6.stack = "".concat(i6.join("\n"), "\n").concat(a7.join("\n"));
      }
      throw r6;
    }
  }, x4.strict = w4(M4, x4, { equal: x4.strictEqual, deepEqual: x4.deepStrictEqual, notEqual: x4.notStrictEqual, notDeepEqual: x4.notDeepStrictEqual }), x4.strict.strict = x4.strict, Z2;
}
var r2, t2, e$12, r$12, n2, o2, c2, l2, i2, a2, u2, f2, p2, s2, y2, b2, g2, h2, $2, j2, w2, r$22, e$22, o$12, n$12, a$12, c$12, l$12, u$12, f$12, t$12, f$2, e$3, l$22, t$22, n$22, o$22, r$3, e$4, o$32, t$32, n$3, y$1, a$2, i$12, d2, f$3, u$22, A2, l$3, v2, P2, c$22, t$4, p$12, o$4, i$22, a$3, l$4, r$4, n$4, i$3, o$5, c$3, f$4, u$3, s$12, a$4, l$5, p$2, m2, N2, e$5, i$4, n$5, t$5, u$4, a$5, m$12, o$6, s$2, f$5, c$4, a$6, u$5, l$6, g$1, h$12, y$2, b$1, v$1, d$12, E2, w$1, S2, j$1, O2, x2, q2, R2, A$1, k2, _2, T2, P$1, I2, D2, F2, N$1, L2, M2, X2, Z2, $$1, et;
var init_chunk_CjPlbOtt = __esm({
  "node_modules/@jspm/core/nodelibs/browser/chunk-CjPlbOtt.js"() {
    init_dirname();
    init_buffer2();
    init_process2();
    init_chunk_D3uu3VYh();
    r2 = { assign: e2, polyfill: function() {
      Object.assign || Object.defineProperty(Object, "assign", { enumerable: false, configurable: true, writable: true, value: e2 });
    } };
    e$12 = Object.prototype.toString;
    r$12 = function(t6) {
      var r6 = e$12.call(t6), n6 = "[object Arguments]" === r6;
      return n6 || (n6 = "[object Array]" !== r6 && null !== t6 && "object" == typeof t6 && "number" == typeof t6.length && t6.length >= 0 && "[object Function]" === e$12.call(t6.callee)), n6;
    };
    if (!Object.keys) {
      n2 = Object.prototype.hasOwnProperty, o2 = Object.prototype.toString, c2 = r$12, l2 = Object.prototype.propertyIsEnumerable, i2 = !l2.call({ toString: null }, "toString"), a2 = l2.call((function() {
      }), "prototype"), u2 = ["toString", "toLocaleString", "valueOf", "hasOwnProperty", "isPrototypeOf", "propertyIsEnumerable", "constructor"], f2 = function(t6) {
        var e6 = t6.constructor;
        return e6 && e6.prototype === t6;
      }, p2 = { $applicationCache: true, $console: true, $external: true, $frame: true, $frameElement: true, $frames: true, $innerHeight: true, $innerWidth: true, $onmozfullscreenchange: true, $onmozfullscreenerror: true, $outerHeight: true, $outerWidth: true, $pageXOffset: true, $pageYOffset: true, $parent: true, $scrollLeft: true, $scrollTop: true, $scrollX: true, $scrollY: true, $self: true, $webkitIndexedDB: true, $webkitStorageInfo: true, $window: true }, s2 = (function() {
        if ("undefined" == typeof window) return false;
        for (var t6 in window) try {
          if (!p2["$" + t6] && n2.call(window, t6) && null !== window[t6] && "object" == typeof window[t6]) try {
            f2(window[t6]);
          } catch (t7) {
            return true;
          }
        } catch (t7) {
          return true;
        }
        return false;
      })();
      t2 = function(t6) {
        var e6 = null !== t6 && "object" == typeof t6, r6 = "[object Function]" === o2.call(t6), l6 = c2(t6), p6 = e6 && "[object String]" === o2.call(t6), y6 = [];
        if (!e6 && !r6 && !l6) throw new TypeError("Object.keys called on a non-object");
        var b5 = a2 && r6;
        if (p6 && t6.length > 0 && !n2.call(t6, 0)) for (var g5 = 0; g5 < t6.length; ++g5) y6.push(String(g5));
        if (l6 && t6.length > 0) for (var h6 = 0; h6 < t6.length; ++h6) y6.push(String(h6));
        else for (var $3 in t6) b5 && "prototype" === $3 || !n2.call(t6, $3) || y6.push(String($3));
        if (i2) for (var j4 = (function(t7) {
          if ("undefined" == typeof window || !s2) return f2(t7);
          try {
            return f2(t7);
          } catch (t8) {
            return false;
          }
        })(t6), w4 = 0; w4 < u2.length; ++w4) j4 && "constructor" === u2[w4] || !n2.call(t6, u2[w4]) || y6.push(u2[w4]);
        return y6;
      };
    }
    y2 = t2;
    b2 = Array.prototype.slice;
    g2 = r$12;
    h2 = Object.keys;
    $2 = h2 ? function(t6) {
      return h2(t6);
    } : y2;
    j2 = Object.keys;
    $2.shim = function() {
      Object.keys ? (function() {
        var t6 = Object.keys(arguments);
        return t6 && t6.length === arguments.length;
      })(1, 2) || (Object.keys = function(t6) {
        return g2(t6) ? j2(b2.call(t6)) : j2(t6);
      }) : Object.keys = $2;
      return Object.keys || $2;
    };
    w2 = $2;
    r$22 = w2;
    e$22 = "function" == typeof Symbol && "symbol" == typeof /* @__PURE__ */ Symbol("foo");
    o$12 = Object.prototype.toString;
    n$12 = Array.prototype.concat;
    a$12 = Object.defineProperty;
    c$12 = a$12 && (function() {
      var t6 = {};
      try {
        for (var r6 in a$12(t6, "x", { enumerable: false, value: t6 }), t6) return false;
        return t6.x === t6;
      } catch (t7) {
        return false;
      }
    })();
    l$12 = function(t6, r6, e6, n6) {
      var l6;
      (!(r6 in t6) || "function" == typeof (l6 = n6) && "[object Function]" === o$12.call(l6) && n6()) && (c$12 ? a$12(t6, r6, { configurable: true, enumerable: false, value: e6, writable: true }) : t6[r6] = e6);
    };
    u$12 = function(t6, o6) {
      var a6 = arguments.length > 2 ? arguments[2] : {}, c6 = r$22(o6);
      e$22 && (c6 = n$12.call(c6, Object.getOwnPropertySymbols(o6)));
      for (var u6 = 0; u6 < c6.length; u6 += 1) l$12(t6, c6[u6], o6[c6[u6]], a6[c6[u6]]);
    };
    u$12.supportsDescriptors = !!c$12;
    f$12 = u$12;
    t$12 = function() {
      if ("function" != typeof Symbol || "function" != typeof Object.getOwnPropertySymbols) return false;
      if ("symbol" == typeof Symbol.iterator) return true;
      var t6 = {}, e6 = /* @__PURE__ */ Symbol("test"), r6 = Object(e6);
      if ("string" == typeof e6) return false;
      if ("[object Symbol]" !== Object.prototype.toString.call(e6)) return false;
      if ("[object Symbol]" !== Object.prototype.toString.call(r6)) return false;
      for (e6 in t6[e6] = 42, t6) return false;
      if ("function" == typeof Object.keys && 0 !== Object.keys(t6).length) return false;
      if ("function" == typeof Object.getOwnPropertyNames && 0 !== Object.getOwnPropertyNames(t6).length) return false;
      var o6 = Object.getOwnPropertySymbols(t6);
      if (1 !== o6.length || o6[0] !== e6) return false;
      if (!Object.prototype.propertyIsEnumerable.call(t6, e6)) return false;
      if ("function" == typeof Object.getOwnPropertyDescriptor) {
        var n6 = Object.getOwnPropertyDescriptor(t6, e6);
        if (42 !== n6.value || true !== n6.enumerable) return false;
      }
      return true;
    };
    f$2 = ("undefined" != typeof globalThis ? globalThis : "undefined" != typeof self ? self : global).Symbol;
    e$3 = t$12;
    l$22 = function() {
      return "function" == typeof f$2 && ("function" == typeof Symbol && ("symbol" == typeof f$2("foo") && ("symbol" == typeof /* @__PURE__ */ Symbol("bar") && e$3())));
    };
    t$22 = "Function.prototype.bind called on incompatible ";
    n$22 = Array.prototype.slice;
    o$22 = Object.prototype.toString;
    r$3 = function(r6) {
      var e6 = this;
      if ("function" != typeof e6 || "[object Function]" !== o$22.call(e6)) throw new TypeError(t$22 + e6);
      for (var p6, i6 = n$22.call(arguments, 1), c6 = function() {
        if (this instanceof p6) {
          var t6 = e6.apply(this, i6.concat(n$22.call(arguments)));
          return Object(t6) === t6 ? t6 : this;
        }
        return e6.apply(r6, i6.concat(n$22.call(arguments)));
      }, a6 = Math.max(0, e6.length - i6.length), l6 = [], u6 = 0; u6 < a6; u6++) l6.push("$" + u6);
      if (p6 = Function("binder", "return function (" + l6.join(",") + "){ return binder.apply(this,arguments); }")(c6), e6.prototype) {
        var y6 = function() {
        };
        y6.prototype = e6.prototype, p6.prototype = new y6(), y6.prototype = null;
      }
      return p6;
    };
    e$4 = Function.prototype.bind || r$3;
    o$32 = TypeError;
    t$32 = Object.getOwnPropertyDescriptor;
    if (t$32) try {
      t$32({}, "");
    } catch (r6) {
      t$32 = null;
    }
    n$3 = function() {
      throw new o$32();
    };
    y$1 = t$32 ? (function() {
      try {
        return arguments.callee, n$3;
      } catch (r6) {
        try {
          return t$32(arguments, "callee").get;
        } catch (r7) {
          return n$3;
        }
      }
    })() : n$3;
    a$2 = l$22();
    i$12 = Object.getPrototypeOf || function(r6) {
      return r6.__proto__;
    };
    d2 = "undefined" == typeof Uint8Array ? void 0 : i$12(Uint8Array);
    f$3 = { "%Array%": Array, "%ArrayBuffer%": "undefined" == typeof ArrayBuffer ? void 0 : ArrayBuffer, "%ArrayBufferPrototype%": "undefined" == typeof ArrayBuffer ? void 0 : ArrayBuffer.prototype, "%ArrayIteratorPrototype%": a$2 ? i$12([][Symbol.iterator]()) : void 0, "%ArrayPrototype%": Array.prototype, "%ArrayProto_entries%": Array.prototype.entries, "%ArrayProto_forEach%": Array.prototype.forEach, "%ArrayProto_keys%": Array.prototype.keys, "%ArrayProto_values%": Array.prototype.values, "%AsyncFromSyncIteratorPrototype%": void 0, "%AsyncFunction%": void 0, "%AsyncFunctionPrototype%": void 0, "%AsyncGenerator%": void 0, "%AsyncGeneratorFunction%": void 0, "%AsyncGeneratorPrototype%": void 0, "%AsyncIteratorPrototype%": void 0, "%Atomics%": "undefined" == typeof Atomics ? void 0 : Atomics, "%Boolean%": Boolean, "%BooleanPrototype%": Boolean.prototype, "%DataView%": "undefined" == typeof DataView ? void 0 : DataView, "%DataViewPrototype%": "undefined" == typeof DataView ? void 0 : DataView.prototype, "%Date%": Date, "%DatePrototype%": Date.prototype, "%decodeURI%": decodeURI, "%decodeURIComponent%": decodeURIComponent, "%encodeURI%": encodeURI, "%encodeURIComponent%": encodeURIComponent, "%Error%": Error, "%ErrorPrototype%": Error.prototype, "%eval%": eval, "%EvalError%": EvalError, "%EvalErrorPrototype%": EvalError.prototype, "%Float32Array%": "undefined" == typeof Float32Array ? void 0 : Float32Array, "%Float32ArrayPrototype%": "undefined" == typeof Float32Array ? void 0 : Float32Array.prototype, "%Float64Array%": "undefined" == typeof Float64Array ? void 0 : Float64Array, "%Float64ArrayPrototype%": "undefined" == typeof Float64Array ? void 0 : Float64Array.prototype, "%Function%": Function, "%FunctionPrototype%": Function.prototype, "%Generator%": void 0, "%GeneratorFunction%": void 0, "%GeneratorPrototype%": void 0, "%Int8Array%": "undefined" == typeof Int8Array ? void 0 : Int8Array, "%Int8ArrayPrototype%": "undefined" == typeof Int8Array ? void 0 : Int8Array.prototype, "%Int16Array%": "undefined" == typeof Int16Array ? void 0 : Int16Array, "%Int16ArrayPrototype%": "undefined" == typeof Int16Array ? void 0 : Int8Array.prototype, "%Int32Array%": "undefined" == typeof Int32Array ? void 0 : Int32Array, "%Int32ArrayPrototype%": "undefined" == typeof Int32Array ? void 0 : Int32Array.prototype, "%isFinite%": isFinite, "%isNaN%": isNaN, "%IteratorPrototype%": a$2 ? i$12(i$12([][Symbol.iterator]())) : void 0, "%JSON%": "object" == typeof JSON ? JSON : void 0, "%JSONParse%": "object" == typeof JSON ? JSON.parse : void 0, "%Map%": "undefined" == typeof Map ? void 0 : Map, "%MapIteratorPrototype%": "undefined" != typeof Map && a$2 ? i$12((/* @__PURE__ */ new Map())[Symbol.iterator]()) : void 0, "%MapPrototype%": "undefined" == typeof Map ? void 0 : Map.prototype, "%Math%": Math, "%Number%": Number, "%NumberPrototype%": Number.prototype, "%Object%": Object, "%ObjectPrototype%": Object.prototype, "%ObjProto_toString%": Object.prototype.toString, "%ObjProto_valueOf%": Object.prototype.valueOf, "%parseFloat%": parseFloat, "%parseInt%": parseInt, "%Promise%": "undefined" == typeof Promise ? void 0 : Promise, "%PromisePrototype%": "undefined" == typeof Promise ? void 0 : Promise.prototype, "%PromiseProto_then%": "undefined" == typeof Promise ? void 0 : Promise.prototype.then, "%Promise_all%": "undefined" == typeof Promise ? void 0 : Promise.all, "%Promise_reject%": "undefined" == typeof Promise ? void 0 : Promise.reject, "%Promise_resolve%": "undefined" == typeof Promise ? void 0 : Promise.resolve, "%Proxy%": "undefined" == typeof Proxy ? void 0 : Proxy, "%RangeError%": RangeError, "%RangeErrorPrototype%": RangeError.prototype, "%ReferenceError%": ReferenceError, "%ReferenceErrorPrototype%": ReferenceError.prototype, "%Reflect%": "undefined" == typeof Reflect ? void 0 : Reflect, "%RegExp%": RegExp, "%RegExpPrototype%": RegExp.prototype, "%Set%": "undefined" == typeof Set ? void 0 : Set, "%SetIteratorPrototype%": "undefined" != typeof Set && a$2 ? i$12((/* @__PURE__ */ new Set())[Symbol.iterator]()) : void 0, "%SetPrototype%": "undefined" == typeof Set ? void 0 : Set.prototype, "%SharedArrayBuffer%": "undefined" == typeof SharedArrayBuffer ? void 0 : SharedArrayBuffer, "%SharedArrayBufferPrototype%": "undefined" == typeof SharedArrayBuffer ? void 0 : SharedArrayBuffer.prototype, "%String%": String, "%StringIteratorPrototype%": a$2 ? i$12(""[Symbol.iterator]()) : void 0, "%StringPrototype%": String.prototype, "%Symbol%": a$2 ? Symbol : void 0, "%SymbolPrototype%": a$2 ? Symbol.prototype : void 0, "%SyntaxError%": SyntaxError, "%SyntaxErrorPrototype%": SyntaxError.prototype, "%ThrowTypeError%": y$1, "%TypedArray%": d2, "%TypedArrayPrototype%": d2 ? d2.prototype : void 0, "%TypeError%": o$32, "%TypeErrorPrototype%": o$32.prototype, "%Uint8Array%": "undefined" == typeof Uint8Array ? void 0 : Uint8Array, "%Uint8ArrayPrototype%": "undefined" == typeof Uint8Array ? void 0 : Uint8Array.prototype, "%Uint8ClampedArray%": "undefined" == typeof Uint8ClampedArray ? void 0 : Uint8ClampedArray, "%Uint8ClampedArrayPrototype%": "undefined" == typeof Uint8ClampedArray ? void 0 : Uint8ClampedArray.prototype, "%Uint16Array%": "undefined" == typeof Uint16Array ? void 0 : Uint16Array, "%Uint16ArrayPrototype%": "undefined" == typeof Uint16Array ? void 0 : Uint16Array.prototype, "%Uint32Array%": "undefined" == typeof Uint32Array ? void 0 : Uint32Array, "%Uint32ArrayPrototype%": "undefined" == typeof Uint32Array ? void 0 : Uint32Array.prototype, "%URIError%": URIError, "%URIErrorPrototype%": URIError.prototype, "%WeakMap%": "undefined" == typeof WeakMap ? void 0 : WeakMap, "%WeakMapPrototype%": "undefined" == typeof WeakMap ? void 0 : WeakMap.prototype, "%WeakSet%": "undefined" == typeof WeakSet ? void 0 : WeakSet, "%WeakSetPrototype%": "undefined" == typeof WeakSet ? void 0 : WeakSet.prototype };
    u$22 = e$4.call(Function.call, String.prototype.replace);
    A2 = /[^%.[\]]+|\[(?:(-?\d+(?:\.\d+)?)|(["'])((?:(?!\2)[^\\]|\\.)*?)\2)\]|(?=(?:\.|\[\])(?:\.|\[\]|%$))/g;
    l$3 = /\\(\\)?/g;
    v2 = function(r6) {
      var e6 = [];
      return u$22(r6, A2, (function(r7, o6, t6, n6) {
        e6[e6.length] = t6 ? u$22(n6, l$3, "$1") : o6 || r7;
      })), e6;
    };
    P2 = function(r6, e6) {
      if (!(r6 in f$3)) throw new SyntaxError("intrinsic " + r6 + " does not exist!");
      if (void 0 === f$3[r6] && !e6) throw new o$32("intrinsic " + r6 + " exists, but is not available. Please file an issue!");
      return f$3[r6];
    };
    c$22 = function(r6, e6) {
      if (0 === r6.length) throw new TypeError("intrinsic name must be a non-empty string");
      if (arguments.length > 1 && "boolean" != typeof e6) throw new TypeError('"allowMissing" argument must be a boolean');
      for (var n6 = v2(r6), y6 = P2("%" + (n6.length > 0 ? n6[0] : "") + "%", e6), a6 = 1; a6 < n6.length; a6 += 1) if (null != y6) if (t$32 && a6 + 1 >= n6.length) {
        var i6 = t$32(y6, n6[a6]);
        if (!(n6[a6] in y6)) throw new o$32("base intrinsic for " + r6 + " exists, but the property is not available.");
        y6 = i6 ? i6.get || i6.value : y6[n6[a6]];
      } else y6 = y6[n6[a6]];
      return y6;
    };
    p$12 = e$4;
    o$4 = c$22("%Function%");
    i$22 = o$4.apply;
    a$3 = o$4.call;
    (t$4 = function() {
      return p$12.apply(a$3, arguments);
    }).apply = function() {
      return p$12.apply(i$22, arguments);
    };
    l$4 = t$4;
    i$3 = function(t6) {
      return t6 != t6;
    };
    o$5 = (r$4 = function(t6, e6) {
      return 0 === t6 && 0 === e6 ? 1 / t6 == 1 / e6 : t6 === e6 || !(!i$3(t6) || !i$3(e6));
    }, r$4);
    c$3 = (n$4 = function() {
      return "function" == typeof Object.is ? Object.is : o$5;
    }, n$4);
    f$4 = f$12;
    u$3 = f$12;
    s$12 = r$4;
    a$4 = n$4;
    l$5 = function() {
      var t6 = c$3();
      return f$4(Object, { is: t6 }, { is: function() {
        return Object.is !== t6;
      } }), t6;
    };
    p$2 = l$4(a$4(), Object);
    u$3(p$2, { getPolyfill: a$4, implementation: s$12, shim: l$5 });
    m2 = p$2;
    N2 = function(r6) {
      return r6 != r6;
    };
    i$4 = N2;
    n$5 = (e$5 = function() {
      return Number.isNaN && Number.isNaN(NaN) && !Number.isNaN("a") ? Number.isNaN : i$4;
    }, f$12);
    t$5 = e$5;
    u$4 = f$12;
    a$5 = N2;
    m$12 = e$5;
    o$6 = function() {
      var r6 = t$5();
      return n$5(Number, { isNaN: r6 }, { isNaN: function() {
        return Number.isNaN !== r6;
      } }), r6;
    };
    s$2 = m$12();
    u$4(s$2, { getPolyfill: m$12, implementation: a$5, shim: o$6 });
    f$5 = s$2;
    c$4 = {};
    a$6 = false;
    u$5 = {};
    l$6 = false;
    g$1 = void 0 !== /a/g.flags;
    h$12 = function(t6) {
      var e6 = [];
      return t6.forEach((function(t7) {
        return e6.push(t7);
      })), e6;
    };
    y$2 = function(t6) {
      var e6 = [];
      return t6.forEach((function(t7, n6) {
        return e6.push([n6, t7]);
      })), e6;
    };
    b$1 = Object.is ? Object.is : m2;
    v$1 = Object.getOwnPropertySymbols ? Object.getOwnPropertySymbols : function() {
      return [];
    };
    d$12 = Number.isNaN ? Number.isNaN : f$5;
    E2 = m$2(Object.prototype.hasOwnProperty);
    w$1 = m$2(Object.prototype.propertyIsEnumerable);
    S2 = m$2(Object.prototype.toString);
    j$1 = X.types;
    O2 = j$1.isAnyArrayBuffer;
    x2 = j$1.isArrayBufferView;
    q2 = j$1.isDate;
    R2 = j$1.isMap;
    A$1 = j$1.isRegExp;
    k2 = j$1.isSet;
    _2 = j$1.isNativeError;
    T2 = j$1.isBoxedPrimitive;
    P$1 = j$1.isNumberObject;
    I2 = j$1.isStringObject;
    D2 = j$1.isBooleanObject;
    F2 = j$1.isBigIntObject;
    N$1 = j$1.isSymbolObject;
    L2 = j$1.isFloat32Array;
    M2 = j$1.isFloat64Array;
    X2 = { isDeepEqual: function(t6, e6) {
      return B2(t6, e6, false);
    }, isDeepStrictEqual: function(t6, e6) {
      return B2(t6, e6, true);
    } };
    Z2 = {};
    $$1 = false;
    et = tt();
    et.AssertionError;
    et.deepEqual;
    et.deepStrictEqual;
    et.doesNotReject;
    et.doesNotThrow;
    et.equal;
    et.fail;
    et.ifError;
    et.notDeepEqual;
    et.notDeepStrictEqual;
    et.notEqual;
    et.notStrictEqual;
    et.ok;
    et.rejects;
    et.strict;
    et.strictEqual;
    et.throws;
    et.AssertionError;
    et.deepEqual;
    et.deepStrictEqual;
    et.doesNotReject;
    et.doesNotThrow;
    et.equal;
    et.fail;
    et.ifError;
    et.notDeepEqual;
    et.notDeepStrictEqual;
    et.notEqual;
    et.notStrictEqual;
    et.ok;
    et.rejects;
    et.strict;
    et.strictEqual;
    et.throws;
    et.AssertionError;
    et.deepEqual;
    et.deepStrictEqual;
    et.doesNotReject;
    et.doesNotThrow;
    et.equal;
    et.fail;
    et.ifError;
    et.notDeepEqual;
    et.notDeepStrictEqual;
    et.notEqual;
    et.notStrictEqual;
    et.ok;
    et.rejects;
    et.strict;
    et.strictEqual;
    et.throws;
  }
});

// node_modules/@jspm/core/nodelibs/browser/chunk-CbQqNoLO.js
var promisify2;
var init_chunk_CbQqNoLO = __esm({
  "node_modules/@jspm/core/nodelibs/browser/chunk-CbQqNoLO.js"() {
    init_dirname();
    init_buffer2();
    init_process2();
    init_chunk_D3uu3VYh();
    X._extend;
    X.callbackify;
    X.debuglog;
    X.deprecate;
    X.format;
    X.inherits;
    X.inspect;
    X.isArray;
    X.isBoolean;
    X.isBuffer;
    X.isDate;
    X.isError;
    X.isFunction;
    X.isNull;
    X.isNullOrUndefined;
    X.isNumber;
    X.isObject;
    X.isPrimitive;
    X.isRegExp;
    X.isString;
    X.isSymbol;
    X.isUndefined;
    X.log;
    promisify2 = X.promisify;
    X.types;
    X.TextEncoder = globalThis.TextEncoder;
    X.TextDecoder = globalThis.TextDecoder;
  }
});

// node_modules/@jspm/core/nodelibs/browser/chunk-b0rmRow7.js
function dew2() {
  if (_dewExec2) return exports3;
  _dewExec2 = true;
  var process4 = exports3 = {};
  var cachedSetTimeout;
  var cachedClearTimeout;
  function defaultSetTimout() {
    throw new Error("setTimeout has not been defined");
  }
  function defaultClearTimeout() {
    throw new Error("clearTimeout has not been defined");
  }
  (function() {
    try {
      if (typeof setTimeout === "function") {
        cachedSetTimeout = setTimeout;
      } else {
        cachedSetTimeout = defaultSetTimout;
      }
    } catch (e6) {
      cachedSetTimeout = defaultSetTimout;
    }
    try {
      if (typeof clearTimeout === "function") {
        cachedClearTimeout = clearTimeout;
      } else {
        cachedClearTimeout = defaultClearTimeout;
      }
    } catch (e6) {
      cachedClearTimeout = defaultClearTimeout;
    }
  })();
  function runTimeout(fun) {
    if (cachedSetTimeout === setTimeout) {
      return setTimeout(fun, 0);
    }
    if ((cachedSetTimeout === defaultSetTimout || !cachedSetTimeout) && setTimeout) {
      cachedSetTimeout = setTimeout;
      return setTimeout(fun, 0);
    }
    try {
      return cachedSetTimeout(fun, 0);
    } catch (e6) {
      try {
        return cachedSetTimeout.call(null, fun, 0);
      } catch (e7) {
        return cachedSetTimeout.call(this || _global, fun, 0);
      }
    }
  }
  function runClearTimeout(marker) {
    if (cachedClearTimeout === clearTimeout) {
      return clearTimeout(marker);
    }
    if ((cachedClearTimeout === defaultClearTimeout || !cachedClearTimeout) && clearTimeout) {
      cachedClearTimeout = clearTimeout;
      return clearTimeout(marker);
    }
    try {
      return cachedClearTimeout(marker);
    } catch (e6) {
      try {
        return cachedClearTimeout.call(null, marker);
      } catch (e7) {
        return cachedClearTimeout.call(this || _global, marker);
      }
    }
  }
  var queue3 = [];
  var draining3 = false;
  var currentQueue3;
  var queueIndex3 = -1;
  function cleanUpNextTick3() {
    if (!draining3 || !currentQueue3) {
      return;
    }
    draining3 = false;
    if (currentQueue3.length) {
      queue3 = currentQueue3.concat(queue3);
    } else {
      queueIndex3 = -1;
    }
    if (queue3.length) {
      drainQueue3();
    }
  }
  function drainQueue3() {
    if (draining3) {
      return;
    }
    var timeout = runTimeout(cleanUpNextTick3);
    draining3 = true;
    var len = queue3.length;
    while (len) {
      currentQueue3 = queue3;
      queue3 = [];
      while (++queueIndex3 < len) {
        if (currentQueue3) {
          currentQueue3[queueIndex3].run();
        }
      }
      queueIndex3 = -1;
      len = queue3.length;
    }
    currentQueue3 = null;
    draining3 = false;
    runClearTimeout(timeout);
  }
  process4.nextTick = function(fun) {
    var args = new Array(arguments.length - 1);
    if (arguments.length > 1) {
      for (var i6 = 1; i6 < arguments.length; i6++) {
        args[i6 - 1] = arguments[i6];
      }
    }
    queue3.push(new Item3(fun, args));
    if (queue3.length === 1 && !draining3) {
      runTimeout(drainQueue3);
    }
  };
  function Item3(fun, array) {
    (this || _global).fun = fun;
    (this || _global).array = array;
  }
  Item3.prototype.run = function() {
    (this || _global).fun.apply(null, (this || _global).array);
  };
  process4.title = "browser";
  process4.browser = true;
  process4.env = {};
  process4.argv = [];
  process4.version = "";
  process4.versions = {};
  function noop3() {
  }
  process4.on = noop3;
  process4.addListener = noop3;
  process4.once = noop3;
  process4.off = noop3;
  process4.removeListener = noop3;
  process4.removeAllListeners = noop3;
  process4.emit = noop3;
  process4.prependListener = noop3;
  process4.prependOnceListener = noop3;
  process4.listeners = function(name2) {
    return [];
  };
  process4.binding = function(name2) {
    throw new Error("process.binding is not supported");
  };
  process4.cwd = function() {
    return "/";
  };
  process4.chdir = function(dir) {
    throw new Error("process.chdir is not supported");
  };
  process4.umask = function() {
    return 0;
  };
  return exports3;
}
var exports3, _dewExec2, _global, process2;
var init_chunk_b0rmRow7 = __esm({
  "node_modules/@jspm/core/nodelibs/browser/chunk-b0rmRow7.js"() {
    init_dirname();
    init_buffer2();
    init_process2();
    exports3 = {};
    _dewExec2 = false;
    _global = typeof globalThis !== "undefined" ? globalThis : typeof self !== "undefined" ? self : global;
    process2 = dew2();
    process2.platform = "browser";
    process2.addListener;
    process2.argv;
    process2.binding;
    process2.browser;
    process2.chdir;
    process2.cwd;
    process2.emit;
    process2.env;
    process2.listeners;
    process2.nextTick;
    process2.off;
    process2.on;
    process2.once;
    process2.prependListener;
    process2.prependOnceListener;
    process2.removeAllListeners;
    process2.removeListener;
    process2.title;
    process2.umask;
    process2.version;
    process2.versions;
  }
});

// node_modules/@jspm/core/nodelibs/browser/chunk-DHWh-hmB.js
function dew$12() {
  if (_dewExec$12) return exports$12;
  _dewExec$12 = true;
  var process$1 = process2;
  function assertPath(path2) {
    if (typeof path2 !== "string") {
      throw new TypeError("Path must be a string. Received " + JSON.stringify(path2));
    }
  }
  function normalizeStringPosix(path2, allowAboveRoot) {
    var res = "";
    var lastSegmentLength = 0;
    var lastSlash = -1;
    var dots = 0;
    var code;
    for (var i6 = 0; i6 <= path2.length; ++i6) {
      if (i6 < path2.length) code = path2.charCodeAt(i6);
      else if (code === 47) break;
      else code = 47;
      if (code === 47) {
        if (lastSlash === i6 - 1 || dots === 1) ;
        else if (lastSlash !== i6 - 1 && dots === 2) {
          if (res.length < 2 || lastSegmentLength !== 2 || res.charCodeAt(res.length - 1) !== 46 || res.charCodeAt(res.length - 2) !== 46) {
            if (res.length > 2) {
              var lastSlashIndex = res.lastIndexOf("/");
              if (lastSlashIndex !== res.length - 1) {
                if (lastSlashIndex === -1) {
                  res = "";
                  lastSegmentLength = 0;
                } else {
                  res = res.slice(0, lastSlashIndex);
                  lastSegmentLength = res.length - 1 - res.lastIndexOf("/");
                }
                lastSlash = i6;
                dots = 0;
                continue;
              }
            } else if (res.length === 2 || res.length === 1) {
              res = "";
              lastSegmentLength = 0;
              lastSlash = i6;
              dots = 0;
              continue;
            }
          }
          if (allowAboveRoot) {
            if (res.length > 0) res += "/..";
            else res = "..";
            lastSegmentLength = 2;
          }
        } else {
          if (res.length > 0) res += "/" + path2.slice(lastSlash + 1, i6);
          else res = path2.slice(lastSlash + 1, i6);
          lastSegmentLength = i6 - lastSlash - 1;
        }
        lastSlash = i6;
        dots = 0;
      } else if (code === 46 && dots !== -1) {
        ++dots;
      } else {
        dots = -1;
      }
    }
    return res;
  }
  function _format(sep, pathObject) {
    var dir = pathObject.dir || pathObject.root;
    var base = pathObject.base || (pathObject.name || "") + (pathObject.ext || "");
    if (!dir) {
      return base;
    }
    if (dir === pathObject.root) {
      return dir + base;
    }
    return dir + sep + base;
  }
  var posix = {
    // path.resolve([from ...], to)
    resolve: function resolve2() {
      var resolvedPath = "";
      var resolvedAbsolute = false;
      var cwd3;
      for (var i6 = arguments.length - 1; i6 >= -1 && !resolvedAbsolute; i6--) {
        var path2;
        if (i6 >= 0) path2 = arguments[i6];
        else {
          if (cwd3 === void 0) cwd3 = process$1.cwd();
          path2 = cwd3;
        }
        assertPath(path2);
        if (path2.length === 0) {
          continue;
        }
        resolvedPath = path2 + "/" + resolvedPath;
        resolvedAbsolute = path2.charCodeAt(0) === 47;
      }
      resolvedPath = normalizeStringPosix(resolvedPath, !resolvedAbsolute);
      if (resolvedAbsolute) {
        if (resolvedPath.length > 0) return "/" + resolvedPath;
        else return "/";
      } else if (resolvedPath.length > 0) {
        return resolvedPath;
      } else {
        return ".";
      }
    },
    normalize: function normalize(path2) {
      assertPath(path2);
      if (path2.length === 0) return ".";
      var isAbsolute = path2.charCodeAt(0) === 47;
      var trailingSeparator = path2.charCodeAt(path2.length - 1) === 47;
      path2 = normalizeStringPosix(path2, !isAbsolute);
      if (path2.length === 0 && !isAbsolute) path2 = ".";
      if (path2.length > 0 && trailingSeparator) path2 += "/";
      if (isAbsolute) return "/" + path2;
      return path2;
    },
    isAbsolute: function isAbsolute(path2) {
      assertPath(path2);
      return path2.length > 0 && path2.charCodeAt(0) === 47;
    },
    join: function join() {
      if (arguments.length === 0) return ".";
      var joined;
      for (var i6 = 0; i6 < arguments.length; ++i6) {
        var arg = arguments[i6];
        assertPath(arg);
        if (arg.length > 0) {
          if (joined === void 0) joined = arg;
          else joined += "/" + arg;
        }
      }
      if (joined === void 0) return ".";
      return posix.normalize(joined);
    },
    relative: function relative(from, to) {
      assertPath(from);
      assertPath(to);
      if (from === to) return "";
      from = posix.resolve(from);
      to = posix.resolve(to);
      if (from === to) return "";
      var fromStart = 1;
      for (; fromStart < from.length; ++fromStart) {
        if (from.charCodeAt(fromStart) !== 47) break;
      }
      var fromEnd = from.length;
      var fromLen = fromEnd - fromStart;
      var toStart = 1;
      for (; toStart < to.length; ++toStart) {
        if (to.charCodeAt(toStart) !== 47) break;
      }
      var toEnd = to.length;
      var toLen = toEnd - toStart;
      var length = fromLen < toLen ? fromLen : toLen;
      var lastCommonSep = -1;
      var i6 = 0;
      for (; i6 <= length; ++i6) {
        if (i6 === length) {
          if (toLen > length) {
            if (to.charCodeAt(toStart + i6) === 47) {
              return to.slice(toStart + i6 + 1);
            } else if (i6 === 0) {
              return to.slice(toStart + i6);
            }
          } else if (fromLen > length) {
            if (from.charCodeAt(fromStart + i6) === 47) {
              lastCommonSep = i6;
            } else if (i6 === 0) {
              lastCommonSep = 0;
            }
          }
          break;
        }
        var fromCode = from.charCodeAt(fromStart + i6);
        var toCode = to.charCodeAt(toStart + i6);
        if (fromCode !== toCode) break;
        else if (fromCode === 47) lastCommonSep = i6;
      }
      var out = "";
      for (i6 = fromStart + lastCommonSep + 1; i6 <= fromEnd; ++i6) {
        if (i6 === fromEnd || from.charCodeAt(i6) === 47) {
          if (out.length === 0) out += "..";
          else out += "/..";
        }
      }
      if (out.length > 0) return out + to.slice(toStart + lastCommonSep);
      else {
        toStart += lastCommonSep;
        if (to.charCodeAt(toStart) === 47) ++toStart;
        return to.slice(toStart);
      }
    },
    _makeLong: function _makeLong(path2) {
      return path2;
    },
    dirname: function dirname(path2) {
      assertPath(path2);
      if (path2.length === 0) return ".";
      var code = path2.charCodeAt(0);
      var hasRoot = code === 47;
      var end = -1;
      var matchedSlash = true;
      for (var i6 = path2.length - 1; i6 >= 1; --i6) {
        code = path2.charCodeAt(i6);
        if (code === 47) {
          if (!matchedSlash) {
            end = i6;
            break;
          }
        } else {
          matchedSlash = false;
        }
      }
      if (end === -1) return hasRoot ? "/" : ".";
      if (hasRoot && end === 1) return "//";
      return path2.slice(0, end);
    },
    basename: function basename(path2, ext) {
      if (ext !== void 0 && typeof ext !== "string") throw new TypeError('"ext" argument must be a string');
      assertPath(path2);
      var start = 0;
      var end = -1;
      var matchedSlash = true;
      var i6;
      if (ext !== void 0 && ext.length > 0 && ext.length <= path2.length) {
        if (ext.length === path2.length && ext === path2) return "";
        var extIdx = ext.length - 1;
        var firstNonSlashEnd = -1;
        for (i6 = path2.length - 1; i6 >= 0; --i6) {
          var code = path2.charCodeAt(i6);
          if (code === 47) {
            if (!matchedSlash) {
              start = i6 + 1;
              break;
            }
          } else {
            if (firstNonSlashEnd === -1) {
              matchedSlash = false;
              firstNonSlashEnd = i6 + 1;
            }
            if (extIdx >= 0) {
              if (code === ext.charCodeAt(extIdx)) {
                if (--extIdx === -1) {
                  end = i6;
                }
              } else {
                extIdx = -1;
                end = firstNonSlashEnd;
              }
            }
          }
        }
        if (start === end) end = firstNonSlashEnd;
        else if (end === -1) end = path2.length;
        return path2.slice(start, end);
      } else {
        for (i6 = path2.length - 1; i6 >= 0; --i6) {
          if (path2.charCodeAt(i6) === 47) {
            if (!matchedSlash) {
              start = i6 + 1;
              break;
            }
          } else if (end === -1) {
            matchedSlash = false;
            end = i6 + 1;
          }
        }
        if (end === -1) return "";
        return path2.slice(start, end);
      }
    },
    extname: function extname(path2) {
      assertPath(path2);
      var startDot = -1;
      var startPart = 0;
      var end = -1;
      var matchedSlash = true;
      var preDotState = 0;
      for (var i6 = path2.length - 1; i6 >= 0; --i6) {
        var code = path2.charCodeAt(i6);
        if (code === 47) {
          if (!matchedSlash) {
            startPart = i6 + 1;
            break;
          }
          continue;
        }
        if (end === -1) {
          matchedSlash = false;
          end = i6 + 1;
        }
        if (code === 46) {
          if (startDot === -1) startDot = i6;
          else if (preDotState !== 1) preDotState = 1;
        } else if (startDot !== -1) {
          preDotState = -1;
        }
      }
      if (startDot === -1 || end === -1 || // We saw a non-dot character immediately before the dot
      preDotState === 0 || // The (right-most) trimmed path component is exactly '..'
      preDotState === 1 && startDot === end - 1 && startDot === startPart + 1) {
        return "";
      }
      return path2.slice(startDot, end);
    },
    format: function format2(pathObject) {
      if (pathObject === null || typeof pathObject !== "object") {
        throw new TypeError('The "pathObject" argument must be of type Object. Received type ' + typeof pathObject);
      }
      return _format("/", pathObject);
    },
    parse: function parse2(path2) {
      assertPath(path2);
      var ret = {
        root: "",
        dir: "",
        base: "",
        ext: "",
        name: ""
      };
      if (path2.length === 0) return ret;
      var code = path2.charCodeAt(0);
      var isAbsolute = code === 47;
      var start;
      if (isAbsolute) {
        ret.root = "/";
        start = 1;
      } else {
        start = 0;
      }
      var startDot = -1;
      var startPart = 0;
      var end = -1;
      var matchedSlash = true;
      var i6 = path2.length - 1;
      var preDotState = 0;
      for (; i6 >= start; --i6) {
        code = path2.charCodeAt(i6);
        if (code === 47) {
          if (!matchedSlash) {
            startPart = i6 + 1;
            break;
          }
          continue;
        }
        if (end === -1) {
          matchedSlash = false;
          end = i6 + 1;
        }
        if (code === 46) {
          if (startDot === -1) startDot = i6;
          else if (preDotState !== 1) preDotState = 1;
        } else if (startDot !== -1) {
          preDotState = -1;
        }
      }
      if (startDot === -1 || end === -1 || // We saw a non-dot character immediately before the dot
      preDotState === 0 || // The (right-most) trimmed path component is exactly '..'
      preDotState === 1 && startDot === end - 1 && startDot === startPart + 1) {
        if (end !== -1) {
          if (startPart === 0 && isAbsolute) ret.base = ret.name = path2.slice(1, end);
          else ret.base = ret.name = path2.slice(startPart, end);
        }
      } else {
        if (startPart === 0 && isAbsolute) {
          ret.name = path2.slice(1, startDot);
          ret.base = path2.slice(1, end);
        } else {
          ret.name = path2.slice(startPart, startDot);
          ret.base = path2.slice(startPart, end);
        }
        ret.ext = path2.slice(startDot, end);
      }
      if (startPart > 0) ret.dir = path2.slice(0, startPart - 1);
      else if (isAbsolute) ret.dir = "/";
      return ret;
    },
    sep: "/",
    delimiter: ":",
    win32: null,
    posix: null
  };
  posix.posix = posix;
  exports$12 = posix;
  return exports$12;
}
function i$13(t6) {
  throw new RangeError(r$23[t6]);
}
function f$13(t6, o6) {
  const n6 = t6.split("@");
  let r6 = "";
  n6.length > 1 && (r6 = n6[0] + "@", t6 = n6[1]);
  const c6 = (function(t7, o7) {
    const n7 = [];
    let e6 = t7.length;
    for (; e6--; ) n7[e6] = o7(t7[e6]);
    return n7;
  })((t6 = t6.replace(e$23, ".")).split("."), o6).join(".");
  return r6 + c6;
}
function l$13(t6) {
  const o6 = [];
  let n6 = 0;
  const e6 = t6.length;
  for (; n6 < e6; ) {
    const r6 = t6.charCodeAt(n6++);
    if (r6 >= 55296 && r6 <= 56319 && n6 < e6) {
      const e7 = t6.charCodeAt(n6++);
      56320 == (64512 & e7) ? o6.push(((1023 & r6) << 10) + (1023 & e7) + 65536) : (o6.push(r6), n6--);
    } else o6.push(r6);
  }
  return o6;
}
function e$13(e6, n6) {
  return Object.prototype.hasOwnProperty.call(e6, n6);
}
function r3() {
  this.protocol = null, this.slashes = null, this.auth = null, this.host = null, this.port = null, this.hostname = null, this.hash = null, this.search = null, this.query = null, this.pathname = null, this.path = null, this.href = null;
}
function O3(t6, s6, h6) {
  if (t6 && a3.isObject(t6) && t6 instanceof r3) return t6;
  var e6 = new r3();
  return e6.parse(t6, s6, h6), e6;
}
function dew3() {
  if (_dewExec3) return exports4;
  _dewExec3 = true;
  var process4 = T$1;
  function assertPath(path2) {
    if (typeof path2 !== "string") {
      throw new TypeError("Path must be a string. Received " + JSON.stringify(path2));
    }
  }
  function normalizeStringPosix(path2, allowAboveRoot) {
    var res = "";
    var lastSegmentLength = 0;
    var lastSlash = -1;
    var dots = 0;
    var code;
    for (var i6 = 0; i6 <= path2.length; ++i6) {
      if (i6 < path2.length) code = path2.charCodeAt(i6);
      else if (code === 47) break;
      else code = 47;
      if (code === 47) {
        if (lastSlash === i6 - 1 || dots === 1) ;
        else if (lastSlash !== i6 - 1 && dots === 2) {
          if (res.length < 2 || lastSegmentLength !== 2 || res.charCodeAt(res.length - 1) !== 46 || res.charCodeAt(res.length - 2) !== 46) {
            if (res.length > 2) {
              var lastSlashIndex = res.lastIndexOf("/");
              if (lastSlashIndex !== res.length - 1) {
                if (lastSlashIndex === -1) {
                  res = "";
                  lastSegmentLength = 0;
                } else {
                  res = res.slice(0, lastSlashIndex);
                  lastSegmentLength = res.length - 1 - res.lastIndexOf("/");
                }
                lastSlash = i6;
                dots = 0;
                continue;
              }
            } else if (res.length === 2 || res.length === 1) {
              res = "";
              lastSegmentLength = 0;
              lastSlash = i6;
              dots = 0;
              continue;
            }
          }
          if (allowAboveRoot) {
            if (res.length > 0) res += "/..";
            else res = "..";
            lastSegmentLength = 2;
          }
        } else {
          if (res.length > 0) res += "/" + path2.slice(lastSlash + 1, i6);
          else res = path2.slice(lastSlash + 1, i6);
          lastSegmentLength = i6 - lastSlash - 1;
        }
        lastSlash = i6;
        dots = 0;
      } else if (code === 46 && dots !== -1) {
        ++dots;
      } else {
        dots = -1;
      }
    }
    return res;
  }
  function _format(sep, pathObject) {
    var dir = pathObject.dir || pathObject.root;
    var base = pathObject.base || (pathObject.name || "") + (pathObject.ext || "");
    if (!dir) {
      return base;
    }
    if (dir === pathObject.root) {
      return dir + base;
    }
    return dir + sep + base;
  }
  var posix = {
    // path.resolve([from ...], to)
    resolve: function resolve2() {
      var resolvedPath = "";
      var resolvedAbsolute = false;
      var cwd3;
      for (var i6 = arguments.length - 1; i6 >= -1 && !resolvedAbsolute; i6--) {
        var path2;
        if (i6 >= 0) path2 = arguments[i6];
        else {
          if (cwd3 === void 0) cwd3 = process4.cwd();
          path2 = cwd3;
        }
        assertPath(path2);
        if (path2.length === 0) {
          continue;
        }
        resolvedPath = path2 + "/" + resolvedPath;
        resolvedAbsolute = path2.charCodeAt(0) === 47;
      }
      resolvedPath = normalizeStringPosix(resolvedPath, !resolvedAbsolute);
      if (resolvedAbsolute) {
        if (resolvedPath.length > 0) return "/" + resolvedPath;
        else return "/";
      } else if (resolvedPath.length > 0) {
        return resolvedPath;
      } else {
        return ".";
      }
    },
    normalize: function normalize(path2) {
      assertPath(path2);
      if (path2.length === 0) return ".";
      var isAbsolute = path2.charCodeAt(0) === 47;
      var trailingSeparator = path2.charCodeAt(path2.length - 1) === 47;
      path2 = normalizeStringPosix(path2, !isAbsolute);
      if (path2.length === 0 && !isAbsolute) path2 = ".";
      if (path2.length > 0 && trailingSeparator) path2 += "/";
      if (isAbsolute) return "/" + path2;
      return path2;
    },
    isAbsolute: function isAbsolute(path2) {
      assertPath(path2);
      return path2.length > 0 && path2.charCodeAt(0) === 47;
    },
    join: function join() {
      if (arguments.length === 0) return ".";
      var joined;
      for (var i6 = 0; i6 < arguments.length; ++i6) {
        var arg = arguments[i6];
        assertPath(arg);
        if (arg.length > 0) {
          if (joined === void 0) joined = arg;
          else joined += "/" + arg;
        }
      }
      if (joined === void 0) return ".";
      return posix.normalize(joined);
    },
    relative: function relative(from, to) {
      assertPath(from);
      assertPath(to);
      if (from === to) return "";
      from = posix.resolve(from);
      to = posix.resolve(to);
      if (from === to) return "";
      var fromStart = 1;
      for (; fromStart < from.length; ++fromStart) {
        if (from.charCodeAt(fromStart) !== 47) break;
      }
      var fromEnd = from.length;
      var fromLen = fromEnd - fromStart;
      var toStart = 1;
      for (; toStart < to.length; ++toStart) {
        if (to.charCodeAt(toStart) !== 47) break;
      }
      var toEnd = to.length;
      var toLen = toEnd - toStart;
      var length = fromLen < toLen ? fromLen : toLen;
      var lastCommonSep = -1;
      var i6 = 0;
      for (; i6 <= length; ++i6) {
        if (i6 === length) {
          if (toLen > length) {
            if (to.charCodeAt(toStart + i6) === 47) {
              return to.slice(toStart + i6 + 1);
            } else if (i6 === 0) {
              return to.slice(toStart + i6);
            }
          } else if (fromLen > length) {
            if (from.charCodeAt(fromStart + i6) === 47) {
              lastCommonSep = i6;
            } else if (i6 === 0) {
              lastCommonSep = 0;
            }
          }
          break;
        }
        var fromCode = from.charCodeAt(fromStart + i6);
        var toCode = to.charCodeAt(toStart + i6);
        if (fromCode !== toCode) break;
        else if (fromCode === 47) lastCommonSep = i6;
      }
      var out = "";
      for (i6 = fromStart + lastCommonSep + 1; i6 <= fromEnd; ++i6) {
        if (i6 === fromEnd || from.charCodeAt(i6) === 47) {
          if (out.length === 0) out += "..";
          else out += "/..";
        }
      }
      if (out.length > 0) return out + to.slice(toStart + lastCommonSep);
      else {
        toStart += lastCommonSep;
        if (to.charCodeAt(toStart) === 47) ++toStart;
        return to.slice(toStart);
      }
    },
    _makeLong: function _makeLong(path2) {
      return path2;
    },
    dirname: function dirname(path2) {
      assertPath(path2);
      if (path2.length === 0) return ".";
      var code = path2.charCodeAt(0);
      var hasRoot = code === 47;
      var end = -1;
      var matchedSlash = true;
      for (var i6 = path2.length - 1; i6 >= 1; --i6) {
        code = path2.charCodeAt(i6);
        if (code === 47) {
          if (!matchedSlash) {
            end = i6;
            break;
          }
        } else {
          matchedSlash = false;
        }
      }
      if (end === -1) return hasRoot ? "/" : ".";
      if (hasRoot && end === 1) return "//";
      return path2.slice(0, end);
    },
    basename: function basename(path2, ext) {
      if (ext !== void 0 && typeof ext !== "string") throw new TypeError('"ext" argument must be a string');
      assertPath(path2);
      var start = 0;
      var end = -1;
      var matchedSlash = true;
      var i6;
      if (ext !== void 0 && ext.length > 0 && ext.length <= path2.length) {
        if (ext.length === path2.length && ext === path2) return "";
        var extIdx = ext.length - 1;
        var firstNonSlashEnd = -1;
        for (i6 = path2.length - 1; i6 >= 0; --i6) {
          var code = path2.charCodeAt(i6);
          if (code === 47) {
            if (!matchedSlash) {
              start = i6 + 1;
              break;
            }
          } else {
            if (firstNonSlashEnd === -1) {
              matchedSlash = false;
              firstNonSlashEnd = i6 + 1;
            }
            if (extIdx >= 0) {
              if (code === ext.charCodeAt(extIdx)) {
                if (--extIdx === -1) {
                  end = i6;
                }
              } else {
                extIdx = -1;
                end = firstNonSlashEnd;
              }
            }
          }
        }
        if (start === end) end = firstNonSlashEnd;
        else if (end === -1) end = path2.length;
        return path2.slice(start, end);
      } else {
        for (i6 = path2.length - 1; i6 >= 0; --i6) {
          if (path2.charCodeAt(i6) === 47) {
            if (!matchedSlash) {
              start = i6 + 1;
              break;
            }
          } else if (end === -1) {
            matchedSlash = false;
            end = i6 + 1;
          }
        }
        if (end === -1) return "";
        return path2.slice(start, end);
      }
    },
    extname: function extname(path2) {
      assertPath(path2);
      var startDot = -1;
      var startPart = 0;
      var end = -1;
      var matchedSlash = true;
      var preDotState = 0;
      for (var i6 = path2.length - 1; i6 >= 0; --i6) {
        var code = path2.charCodeAt(i6);
        if (code === 47) {
          if (!matchedSlash) {
            startPart = i6 + 1;
            break;
          }
          continue;
        }
        if (end === -1) {
          matchedSlash = false;
          end = i6 + 1;
        }
        if (code === 46) {
          if (startDot === -1) startDot = i6;
          else if (preDotState !== 1) preDotState = 1;
        } else if (startDot !== -1) {
          preDotState = -1;
        }
      }
      if (startDot === -1 || end === -1 || // We saw a non-dot character immediately before the dot
      preDotState === 0 || // The (right-most) trimmed path component is exactly '..'
      preDotState === 1 && startDot === end - 1 && startDot === startPart + 1) {
        return "";
      }
      return path2.slice(startDot, end);
    },
    format: function format2(pathObject) {
      if (pathObject === null || typeof pathObject !== "object") {
        throw new TypeError('The "pathObject" argument must be of type Object. Received type ' + typeof pathObject);
      }
      return _format("/", pathObject);
    },
    parse: function parse2(path2) {
      assertPath(path2);
      var ret = {
        root: "",
        dir: "",
        base: "",
        ext: "",
        name: ""
      };
      if (path2.length === 0) return ret;
      var code = path2.charCodeAt(0);
      var isAbsolute = code === 47;
      var start;
      if (isAbsolute) {
        ret.root = "/";
        start = 1;
      } else {
        start = 0;
      }
      var startDot = -1;
      var startPart = 0;
      var end = -1;
      var matchedSlash = true;
      var i6 = path2.length - 1;
      var preDotState = 0;
      for (; i6 >= start; --i6) {
        code = path2.charCodeAt(i6);
        if (code === 47) {
          if (!matchedSlash) {
            startPart = i6 + 1;
            break;
          }
          continue;
        }
        if (end === -1) {
          matchedSlash = false;
          end = i6 + 1;
        }
        if (code === 46) {
          if (startDot === -1) startDot = i6;
          else if (preDotState !== 1) preDotState = 1;
        } else if (startDot !== -1) {
          preDotState = -1;
        }
      }
      if (startDot === -1 || end === -1 || // We saw a non-dot character immediately before the dot
      preDotState === 0 || // The (right-most) trimmed path component is exactly '..'
      preDotState === 1 && startDot === end - 1 && startDot === startPart + 1) {
        if (end !== -1) {
          if (startPart === 0 && isAbsolute) ret.base = ret.name = path2.slice(1, end);
          else ret.base = ret.name = path2.slice(startPart, end);
        }
      } else {
        if (startPart === 0 && isAbsolute) {
          ret.name = path2.slice(1, startDot);
          ret.base = path2.slice(1, end);
        } else {
          ret.name = path2.slice(startPart, startDot);
          ret.base = path2.slice(startPart, end);
        }
        ret.ext = path2.slice(startDot, end);
      }
      if (startPart > 0) ret.dir = path2.slice(0, startPart - 1);
      else if (isAbsolute) ret.dir = "/";
      return ret;
    },
    sep: "/",
    delimiter: ":",
    win32: null,
    posix: null
  };
  posix.posix = posix;
  exports4 = posix;
  return exports4;
}
function fileURLToPath$1(path2) {
  if (typeof path2 === "string") path2 = new URL(path2);
  else if (!(path2 instanceof URL)) {
    throw new Deno.errors.InvalidData(
      "invalid argument path , must be a string or URL"
    );
  }
  if (path2.protocol !== "file:") {
    throw new Deno.errors.InvalidData("invalid url scheme");
  }
  return isWindows$1 ? getPathFromURLWin$1(path2) : getPathFromURLPosix$1(path2);
}
function getPathFromURLWin$1(url) {
  const hostname = url.hostname;
  let pathname = url.pathname;
  for (let n6 = 0; n6 < pathname.length; n6++) {
    if (pathname[n6] === "%") {
      const third = pathname.codePointAt(n6 + 2) || 32;
      if (pathname[n6 + 1] === "2" && third === 102 || // 2f 2F /
      pathname[n6 + 1] === "5" && third === 99) {
        throw new Deno.errors.InvalidData(
          "must not include encoded \\ or / characters"
        );
      }
    }
  }
  pathname = pathname.replace(forwardSlashRegEx$1, "\\");
  pathname = decodeURIComponent(pathname);
  if (hostname !== "") {
    return `\\\\${hostname}${pathname}`;
  } else {
    const letter = pathname.codePointAt(1) | 32;
    const sep = pathname[2];
    if (letter < CHAR_LOWERCASE_A$1 || letter > CHAR_LOWERCASE_Z$1 || // a..z A..Z
    sep !== ":") {
      throw new Deno.errors.InvalidData("file url path must be absolute");
    }
    return pathname.slice(1);
  }
}
function getPathFromURLPosix$1(url) {
  if (url.hostname !== "") {
    throw new Deno.errors.InvalidData("invalid file url hostname");
  }
  const pathname = url.pathname;
  for (let n6 = 0; n6 < pathname.length; n6++) {
    if (pathname[n6] === "%") {
      const third = pathname.codePointAt(n6 + 2) || 32;
      if (pathname[n6 + 1] === "2" && third === 102) {
        throw new Deno.errors.InvalidData(
          "must not include encoded / characters"
        );
      }
    }
  }
  return decodeURIComponent(pathname);
}
function pathToFileURL$1(filepath) {
  let resolved = path.resolve(filepath);
  const filePathLast = filepath.charCodeAt(filepath.length - 1);
  if ((filePathLast === CHAR_FORWARD_SLASH$1 || isWindows$1 && filePathLast === CHAR_BACKWARD_SLASH$1) && resolved[resolved.length - 1] !== path.sep) {
    resolved += "/";
  }
  const outURL = new URL("file://");
  if (resolved.includes("%")) resolved = resolved.replace(percentRegEx$1, "%25");
  if (!isWindows$1 && resolved.includes("\\")) {
    resolved = resolved.replace(backslashRegEx$1, "%5C");
  }
  if (resolved.includes("\n")) resolved = resolved.replace(newlineRegEx$1, "%0A");
  if (resolved.includes("\r")) {
    resolved = resolved.replace(carriageReturnRegEx$1, "%0D");
  }
  if (resolved.includes("	")) resolved = resolved.replace(tabRegEx$1, "%09");
  outURL.pathname = resolved;
  return outURL;
}
function fileURLToPath(path2) {
  if (typeof path2 === "string") path2 = new URL(path2);
  else if (!(path2 instanceof URL)) {
    throw new Deno.errors.InvalidData(
      "invalid argument path , must be a string or URL"
    );
  }
  if (path2.protocol !== "file:") {
    throw new Deno.errors.InvalidData("invalid url scheme");
  }
  return isWindows ? getPathFromURLWin(path2) : getPathFromURLPosix(path2);
}
function getPathFromURLWin(url) {
  const hostname = url.hostname;
  let pathname = url.pathname;
  for (let n6 = 0; n6 < pathname.length; n6++) {
    if (pathname[n6] === "%") {
      const third = pathname.codePointAt(n6 + 2) || 32;
      if (pathname[n6 + 1] === "2" && third === 102 || // 2f 2F /
      pathname[n6 + 1] === "5" && third === 99) {
        throw new Deno.errors.InvalidData(
          "must not include encoded \\ or / characters"
        );
      }
    }
  }
  pathname = pathname.replace(forwardSlashRegEx, "\\");
  pathname = decodeURIComponent(pathname);
  if (hostname !== "") {
    return `\\\\${hostname}${pathname}`;
  } else {
    const letter = pathname.codePointAt(1) | 32;
    const sep = pathname[2];
    if (letter < CHAR_LOWERCASE_A || letter > CHAR_LOWERCASE_Z || // a..z A..Z
    sep !== ":") {
      throw new Deno.errors.InvalidData("file url path must be absolute");
    }
    return pathname.slice(1);
  }
}
function getPathFromURLPosix(url) {
  if (url.hostname !== "") {
    throw new Deno.errors.InvalidData("invalid file url hostname");
  }
  const pathname = url.pathname;
  for (let n6 = 0; n6 < pathname.length; n6++) {
    if (pathname[n6] === "%") {
      const third = pathname.codePointAt(n6 + 2) || 32;
      if (pathname[n6 + 1] === "2" && third === 102) {
        throw new Deno.errors.InvalidData(
          "must not include encoded / characters"
        );
      }
    }
  }
  return decodeURIComponent(pathname);
}
function pathToFileURL(filepath) {
  let resolved = exports$22.resolve(filepath);
  const filePathLast = filepath.charCodeAt(filepath.length - 1);
  if ((filePathLast === CHAR_FORWARD_SLASH || isWindows && filePathLast === CHAR_BACKWARD_SLASH) && resolved[resolved.length - 1] !== exports$22.sep) {
    resolved += "/";
  }
  const outURL = new URL("file://");
  if (resolved.includes("%")) resolved = resolved.replace(percentRegEx, "%25");
  if (!isWindows && resolved.includes("\\")) {
    resolved = resolved.replace(backslashRegEx, "%5C");
  }
  if (resolved.includes("\n")) resolved = resolved.replace(newlineRegEx, "%0A");
  if (resolved.includes("\r")) {
    resolved = resolved.replace(carriageReturnRegEx, "%0D");
  }
  if (resolved.includes("	")) resolved = resolved.replace(tabRegEx, "%09");
  outURL.pathname = resolved;
  return outURL;
}
var exports$12, _dewExec$12, exports$22, t$13, o$23, n$23, e$23, r$23, c$13, s3, u$13, a$13, d3, h$13, p$13, n$13, r$13, t3, o$13, h3, e3, a3, o3, n3, i3, l3, p3, c3, u3, f3, m3, v3, g3, y3, b3, exports4, _dewExec3, path, processPlatform$1, CHAR_BACKWARD_SLASH$1, CHAR_FORWARD_SLASH$1, CHAR_LOWERCASE_A$1, CHAR_LOWERCASE_Z$1, isWindows$1, forwardSlashRegEx$1, percentRegEx$1, backslashRegEx$1, newlineRegEx$1, carriageReturnRegEx$1, tabRegEx$1, processPlatform, CHAR_BACKWARD_SLASH, CHAR_FORWARD_SLASH, CHAR_LOWERCASE_A, CHAR_LOWERCASE_Z, isWindows, forwardSlashRegEx, percentRegEx, backslashRegEx, newlineRegEx, carriageReturnRegEx, tabRegEx;
var init_chunk_DHWh_hmB = __esm({
  "node_modules/@jspm/core/nodelibs/browser/chunk-DHWh-hmB.js"() {
    init_dirname();
    init_buffer2();
    init_process2();
    init_chunk_D3uu3VYh();
    init_chunk_b0rmRow7();
    exports$12 = {};
    _dewExec$12 = false;
    exports$22 = dew$12();
    t$13 = 2147483647;
    o$23 = /^xn--/;
    n$23 = /[^\0-\x7E]/;
    e$23 = /[\x2E\u3002\uFF0E\uFF61]/g;
    r$23 = { overflow: "Overflow: input needs wider integers to process", "not-basic": "Illegal input >= 0x80 (not a basic code point)", "invalid-input": "Invalid input" };
    c$13 = Math.floor;
    s3 = String.fromCharCode;
    u$13 = function(t6, o6) {
      return t6 + 22 + 75 * (t6 < 26) - ((0 != o6) << 5);
    };
    a$13 = function(t6, o6, n6) {
      let e6 = 0;
      for (t6 = n6 ? c$13(t6 / 700) : t6 >> 1, t6 += c$13(t6 / o6); t6 > 455; e6 += 36) t6 = c$13(t6 / 35);
      return c$13(e6 + 36 * t6 / (t6 + 38));
    };
    d3 = function(o6) {
      const n6 = [], e6 = o6.length;
      let r6 = 0, s6 = 128, f6 = 72, l6 = o6.lastIndexOf("-");
      l6 < 0 && (l6 = 0);
      for (let t6 = 0; t6 < l6; ++t6) o6.charCodeAt(t6) >= 128 && i$13("not-basic"), n6.push(o6.charCodeAt(t6));
      for (let d5 = l6 > 0 ? l6 + 1 : 0; d5 < e6; ) {
        let l7 = r6;
        for (let n7 = 1, s7 = 36; ; s7 += 36) {
          d5 >= e6 && i$13("invalid-input");
          const l8 = (u6 = o6.charCodeAt(d5++)) - 48 < 10 ? u6 - 22 : u6 - 65 < 26 ? u6 - 65 : u6 - 97 < 26 ? u6 - 97 : 36;
          (l8 >= 36 || l8 > c$13((t$13 - r6) / n7)) && i$13("overflow"), r6 += l8 * n7;
          const a6 = s7 <= f6 ? 1 : s7 >= f6 + 26 ? 26 : s7 - f6;
          if (l8 < a6) break;
          const h7 = 36 - a6;
          n7 > c$13(t$13 / h7) && i$13("overflow"), n7 *= h7;
        }
        const h6 = n6.length + 1;
        f6 = a$13(r6 - l7, h6, 0 == l7), c$13(r6 / h6) > t$13 - s6 && i$13("overflow"), s6 += c$13(r6 / h6), r6 %= h6, n6.splice(r6++, 0, s6);
      }
      var u6;
      return String.fromCodePoint(...n6);
    };
    h$13 = function(o6) {
      const n6 = [];
      let e6 = (o6 = l$13(o6)).length, r6 = 128, f6 = 0, d5 = 72;
      for (const t6 of o6) t6 < 128 && n6.push(s3(t6));
      let h6 = n6.length, p6 = h6;
      for (h6 && n6.push("-"); p6 < e6; ) {
        let e7 = t$13;
        for (const t6 of o6) t6 >= r6 && t6 < e7 && (e7 = t6);
        const l6 = p6 + 1;
        e7 - r6 > c$13((t$13 - f6) / l6) && i$13("overflow"), f6 += (e7 - r6) * l6, r6 = e7;
        for (const e8 of o6) if (e8 < r6 && ++f6 > t$13 && i$13("overflow"), e8 == r6) {
          let t6 = f6;
          for (let o7 = 36; ; o7 += 36) {
            const e9 = o7 <= d5 ? 1 : o7 >= d5 + 26 ? 26 : o7 - d5;
            if (t6 < e9) break;
            const r7 = t6 - e9, i6 = 36 - e9;
            n6.push(s3(u$13(e9 + r7 % i6, 0))), t6 = c$13(r7 / i6);
          }
          n6.push(s3(u$13(t6, 0))), d5 = a$13(f6, l6, p6 == h6), f6 = 0, ++p6;
        }
        ++f6, ++r6;
      }
      return n6.join("");
    };
    p$13 = { version: "2.1.0", ucs2: { decode: l$13, encode: (t6) => String.fromCodePoint(...t6) }, decode: d3, encode: h$13, toASCII: function(t6) {
      return f$13(t6, (function(t7) {
        return n$23.test(t7) ? "xn--" + h$13(t7) : t7;
      }));
    }, toUnicode: function(t6) {
      return f$13(t6, (function(t7) {
        return o$23.test(t7) ? d3(t7.slice(4).toLowerCase()) : t7;
      }));
    } };
    n$13 = function(n6, r6, t6, o6) {
      r6 = r6 || "&", t6 = t6 || "=";
      var a6 = {};
      if ("string" != typeof n6 || 0 === n6.length) return a6;
      var u6 = /\+/g;
      n6 = n6.split(r6);
      var c6 = 1e3;
      o6 && "number" == typeof o6.maxKeys && (c6 = o6.maxKeys);
      var i6 = n6.length;
      c6 > 0 && i6 > c6 && (i6 = c6);
      for (var s6 = 0; s6 < i6; ++s6) {
        var p6, f6, d5, y6, m5 = n6[s6].replace(u6, "%20"), l6 = m5.indexOf(t6);
        l6 >= 0 ? (p6 = m5.substr(0, l6), f6 = m5.substr(l6 + 1)) : (p6 = m5, f6 = ""), d5 = decodeURIComponent(p6), y6 = decodeURIComponent(f6), e$13(a6, d5) ? Array.isArray(a6[d5]) ? a6[d5].push(y6) : a6[d5] = [a6[d5], y6] : a6[d5] = y6;
      }
      return a6;
    };
    r$13 = function(e6) {
      switch (typeof e6) {
        case "string":
          return e6;
        case "boolean":
          return e6 ? "true" : "false";
        case "number":
          return isFinite(e6) ? e6 : "";
        default:
          return "";
      }
    };
    t3 = function(e6, n6, t6, o6) {
      return n6 = n6 || "&", t6 = t6 || "=", null === e6 && (e6 = void 0), "object" == typeof e6 ? Object.keys(e6).map((function(o7) {
        var a6 = encodeURIComponent(r$13(o7)) + t6;
        return Array.isArray(e6[o7]) ? e6[o7].map((function(e7) {
          return a6 + encodeURIComponent(r$13(e7));
        })).join(n6) : a6 + encodeURIComponent(r$13(e6[o7]));
      })).join(n6) : o6 ? encodeURIComponent(r$13(o6)) + t6 + encodeURIComponent(r$13(e6)) : "";
    };
    o$13 = {};
    o$13.decode = o$13.parse = n$13, o$13.encode = o$13.stringify = t3;
    o$13.decode;
    o$13.encode;
    o$13.parse;
    o$13.stringify;
    h3 = {};
    e3 = p$13;
    a3 = { isString: function(t6) {
      return "string" == typeof t6;
    }, isObject: function(t6) {
      return "object" == typeof t6 && null !== t6;
    }, isNull: function(t6) {
      return null === t6;
    }, isNullOrUndefined: function(t6) {
      return null == t6;
    } };
    h3.parse = O3, h3.resolve = function(t6, s6) {
      return O3(t6, false, true).resolve(s6);
    }, h3.resolveObject = function(t6, s6) {
      return t6 ? O3(t6, false, true).resolveObject(s6) : s6;
    }, h3.format = function(t6) {
      a3.isString(t6) && (t6 = O3(t6));
      return t6 instanceof r3 ? t6.format() : r3.prototype.format.call(t6);
    }, h3.Url = r3;
    o3 = /^([a-z0-9.+-]+:)/i;
    n3 = /:[0-9]*$/;
    i3 = /^(\/\/?(?!\/)[^\?\s]*)(\?[^\s]*)?$/;
    l3 = ["{", "}", "|", "\\", "^", "`"].concat(["<", ">", '"', "`", " ", "\r", "\n", "	"]);
    p3 = ["'"].concat(l3);
    c3 = ["%", "/", "?", ";", "#"].concat(p3);
    u3 = ["/", "?", "#"];
    f3 = /^[+a-z0-9A-Z_-]{0,63}$/;
    m3 = /^([+a-z0-9A-Z_-]{0,63})(.*)$/;
    v3 = { javascript: true, "javascript:": true };
    g3 = { javascript: true, "javascript:": true };
    y3 = { http: true, https: true, ftp: true, gopher: true, file: true, "http:": true, "https:": true, "ftp:": true, "gopher:": true, "file:": true };
    b3 = o$13;
    r3.prototype.parse = function(t6, s6, h6) {
      if (!a3.isString(t6)) throw new TypeError("Parameter 'url' must be a string, not " + typeof t6);
      var r6 = t6.indexOf("?"), n6 = -1 !== r6 && r6 < t6.indexOf("#") ? "?" : "#", l6 = t6.split(n6);
      l6[0] = l6[0].replace(/\\/g, "/");
      var O5 = t6 = l6.join(n6);
      if (O5 = O5.trim(), !h6 && 1 === t6.split("#").length) {
        var d5 = i3.exec(O5);
        if (d5) return this.path = O5, this.href = O5, this.pathname = d5[1], d5[2] ? (this.search = d5[2], this.query = s6 ? b3.parse(this.search.substr(1)) : this.search.substr(1)) : s6 && (this.search = "", this.query = {}), this;
      }
      var j4 = o3.exec(O5);
      if (j4) {
        var q3 = (j4 = j4[0]).toLowerCase();
        this.protocol = q3, O5 = O5.substr(j4.length);
      }
      if (h6 || j4 || O5.match(/^\/\/[^@\/]+@[^@\/]+/)) {
        var x4 = "//" === O5.substr(0, 2);
        !x4 || j4 && g3[j4] || (O5 = O5.substr(2), this.slashes = true);
      }
      if (!g3[j4] && (x4 || j4 && !y3[j4])) {
        for (var A4, C4, I4 = -1, w4 = 0; w4 < u3.length; w4++) {
          -1 !== (N4 = O5.indexOf(u3[w4])) && (-1 === I4 || N4 < I4) && (I4 = N4);
        }
        -1 !== (C4 = -1 === I4 ? O5.lastIndexOf("@") : O5.lastIndexOf("@", I4)) && (A4 = O5.slice(0, C4), O5 = O5.slice(C4 + 1), this.auth = decodeURIComponent(A4)), I4 = -1;
        for (w4 = 0; w4 < c3.length; w4++) {
          var N4;
          -1 !== (N4 = O5.indexOf(c3[w4])) && (-1 === I4 || N4 < I4) && (I4 = N4);
        }
        -1 === I4 && (I4 = O5.length), this.host = O5.slice(0, I4), O5 = O5.slice(I4), this.parseHost(), this.hostname = this.hostname || "";
        var U4 = "[" === this.hostname[0] && "]" === this.hostname[this.hostname.length - 1];
        if (!U4) for (var k4 = this.hostname.split(/\./), S4 = (w4 = 0, k4.length); w4 < S4; w4++) {
          var R4 = k4[w4];
          if (R4 && !R4.match(f3)) {
            for (var $3 = "", z4 = 0, H3 = R4.length; z4 < H3; z4++) R4.charCodeAt(z4) > 127 ? $3 += "x" : $3 += R4[z4];
            if (!$3.match(f3)) {
              var L4 = k4.slice(0, w4), Z3 = k4.slice(w4 + 1), _4 = R4.match(m3);
              _4 && (L4.push(_4[1]), Z3.unshift(_4[2])), Z3.length && (O5 = "/" + Z3.join(".") + O5), this.hostname = L4.join(".");
              break;
            }
          }
        }
        this.hostname.length > 255 ? this.hostname = "" : this.hostname = this.hostname.toLowerCase(), U4 || (this.hostname = e3.toASCII(this.hostname));
        var E4 = this.port ? ":" + this.port : "", P4 = this.hostname || "";
        this.host = P4 + E4, this.href += this.host, U4 && (this.hostname = this.hostname.substr(1, this.hostname.length - 2), "/" !== O5[0] && (O5 = "/" + O5));
      }
      if (!v3[q3]) for (w4 = 0, S4 = p3.length; w4 < S4; w4++) {
        var T4 = p3[w4];
        if (-1 !== O5.indexOf(T4)) {
          var B4 = encodeURIComponent(T4);
          B4 === T4 && (B4 = escape(T4)), O5 = O5.split(T4).join(B4);
        }
      }
      var D4 = O5.indexOf("#");
      -1 !== D4 && (this.hash = O5.substr(D4), O5 = O5.slice(0, D4));
      var F4 = O5.indexOf("?");
      if (-1 !== F4 ? (this.search = O5.substr(F4), this.query = O5.substr(F4 + 1), s6 && (this.query = b3.parse(this.query)), O5 = O5.slice(0, F4)) : s6 && (this.search = "", this.query = {}), O5 && (this.pathname = O5), y3[q3] && this.hostname && !this.pathname && (this.pathname = "/"), this.pathname || this.search) {
        E4 = this.pathname || "";
        var G3 = this.search || "";
        this.path = E4 + G3;
      }
      return this.href = this.format(), this;
    }, r3.prototype.format = function() {
      var t6 = this.auth || "";
      t6 && (t6 = (t6 = encodeURIComponent(t6)).replace(/%3A/i, ":"), t6 += "@");
      var s6 = this.protocol || "", h6 = this.pathname || "", e6 = this.hash || "", r6 = false, o6 = "";
      this.host ? r6 = t6 + this.host : this.hostname && (r6 = t6 + (-1 === this.hostname.indexOf(":") ? this.hostname : "[" + this.hostname + "]"), this.port && (r6 += ":" + this.port)), this.query && a3.isObject(this.query) && Object.keys(this.query).length && (o6 = b3.stringify(this.query));
      var n6 = this.search || o6 && "?" + o6 || "";
      return s6 && ":" !== s6.substr(-1) && (s6 += ":"), this.slashes || (!s6 || y3[s6]) && false !== r6 ? (r6 = "//" + (r6 || ""), h6 && "/" !== h6.charAt(0) && (h6 = "/" + h6)) : r6 || (r6 = ""), e6 && "#" !== e6.charAt(0) && (e6 = "#" + e6), n6 && "?" !== n6.charAt(0) && (n6 = "?" + n6), s6 + r6 + (h6 = h6.replace(/[?#]/g, (function(t7) {
        return encodeURIComponent(t7);
      }))) + (n6 = n6.replace("#", "%23")) + e6;
    }, r3.prototype.resolve = function(t6) {
      return this.resolveObject(O3(t6, false, true)).format();
    }, r3.prototype.resolveObject = function(t6) {
      if (a3.isString(t6)) {
        var s6 = new r3();
        s6.parse(t6, false, true), t6 = s6;
      }
      for (var h6 = new r3(), e6 = Object.keys(this), o6 = 0; o6 < e6.length; o6++) {
        var n6 = e6[o6];
        h6[n6] = this[n6];
      }
      if (h6.hash = t6.hash, "" === t6.href) return h6.href = h6.format(), h6;
      if (t6.slashes && !t6.protocol) {
        for (var i6 = Object.keys(t6), l6 = 0; l6 < i6.length; l6++) {
          var p6 = i6[l6];
          "protocol" !== p6 && (h6[p6] = t6[p6]);
        }
        return y3[h6.protocol] && h6.hostname && !h6.pathname && (h6.path = h6.pathname = "/"), h6.href = h6.format(), h6;
      }
      if (t6.protocol && t6.protocol !== h6.protocol) {
        if (!y3[t6.protocol]) {
          for (var c6 = Object.keys(t6), u6 = 0; u6 < c6.length; u6++) {
            var f6 = c6[u6];
            h6[f6] = t6[f6];
          }
          return h6.href = h6.format(), h6;
        }
        if (h6.protocol = t6.protocol, t6.host || g3[t6.protocol]) h6.pathname = t6.pathname;
        else {
          for (var m5 = (t6.pathname || "").split("/"); m5.length && !(t6.host = m5.shift()); ) ;
          t6.host || (t6.host = ""), t6.hostname || (t6.hostname = ""), "" !== m5[0] && m5.unshift(""), m5.length < 2 && m5.unshift(""), h6.pathname = m5.join("/");
        }
        if (h6.search = t6.search, h6.query = t6.query, h6.host = t6.host || "", h6.auth = t6.auth, h6.hostname = t6.hostname || t6.host, h6.port = t6.port, h6.pathname || h6.search) {
          var v6 = h6.pathname || "", b5 = h6.search || "";
          h6.path = v6 + b5;
        }
        return h6.slashes = h6.slashes || t6.slashes, h6.href = h6.format(), h6;
      }
      var O5 = h6.pathname && "/" === h6.pathname.charAt(0), d5 = t6.host || t6.pathname && "/" === t6.pathname.charAt(0), j4 = d5 || O5 || h6.host && t6.pathname, q3 = j4, x4 = h6.pathname && h6.pathname.split("/") || [], A4 = (m5 = t6.pathname && t6.pathname.split("/") || [], h6.protocol && !y3[h6.protocol]);
      if (A4 && (h6.hostname = "", h6.port = null, h6.host && ("" === x4[0] ? x4[0] = h6.host : x4.unshift(h6.host)), h6.host = "", t6.protocol && (t6.hostname = null, t6.port = null, t6.host && ("" === m5[0] ? m5[0] = t6.host : m5.unshift(t6.host)), t6.host = null), j4 = j4 && ("" === m5[0] || "" === x4[0])), d5) h6.host = t6.host || "" === t6.host ? t6.host : h6.host, h6.hostname = t6.hostname || "" === t6.hostname ? t6.hostname : h6.hostname, h6.search = t6.search, h6.query = t6.query, x4 = m5;
      else if (m5.length) x4 || (x4 = []), x4.pop(), x4 = x4.concat(m5), h6.search = t6.search, h6.query = t6.query;
      else if (!a3.isNullOrUndefined(t6.search)) {
        if (A4) h6.hostname = h6.host = x4.shift(), (U4 = !!(h6.host && h6.host.indexOf("@") > 0) && h6.host.split("@")) && (h6.auth = U4.shift(), h6.host = h6.hostname = U4.shift());
        return h6.search = t6.search, h6.query = t6.query, a3.isNull(h6.pathname) && a3.isNull(h6.search) || (h6.path = (h6.pathname ? h6.pathname : "") + (h6.search ? h6.search : "")), h6.href = h6.format(), h6;
      }
      if (!x4.length) return h6.pathname = null, h6.search ? h6.path = "/" + h6.search : h6.path = null, h6.href = h6.format(), h6;
      for (var C4 = x4.slice(-1)[0], I4 = (h6.host || t6.host || x4.length > 1) && ("." === C4 || ".." === C4) || "" === C4, w4 = 0, N4 = x4.length; N4 >= 0; N4--) "." === (C4 = x4[N4]) ? x4.splice(N4, 1) : ".." === C4 ? (x4.splice(N4, 1), w4++) : w4 && (x4.splice(N4, 1), w4--);
      if (!j4 && !q3) for (; w4--; w4) x4.unshift("..");
      !j4 || "" === x4[0] || x4[0] && "/" === x4[0].charAt(0) || x4.unshift(""), I4 && "/" !== x4.join("/").substr(-1) && x4.push("");
      var U4, k4 = "" === x4[0] || x4[0] && "/" === x4[0].charAt(0);
      A4 && (h6.hostname = h6.host = k4 ? "" : x4.length ? x4.shift() : "", (U4 = !!(h6.host && h6.host.indexOf("@") > 0) && h6.host.split("@")) && (h6.auth = U4.shift(), h6.host = h6.hostname = U4.shift()));
      return (j4 = j4 || h6.host && x4.length) && !k4 && x4.unshift(""), x4.length ? h6.pathname = x4.join("/") : (h6.pathname = null, h6.path = null), a3.isNull(h6.pathname) && a3.isNull(h6.search) || (h6.path = (h6.pathname ? h6.pathname : "") + (h6.search ? h6.search : "")), h6.auth = t6.auth || h6.auth, h6.slashes = h6.slashes || t6.slashes, h6.href = h6.format(), h6;
    }, r3.prototype.parseHost = function() {
      var t6 = this.host, s6 = n3.exec(t6);
      s6 && (":" !== (s6 = s6[0]) && (this.port = s6.substr(1)), t6 = t6.substr(0, t6.length - s6.length)), t6 && (this.hostname = t6);
    };
    h3.Url;
    h3.format;
    h3.resolve;
    h3.resolveObject;
    exports4 = {};
    _dewExec3 = false;
    path = dew3();
    processPlatform$1 = typeof Deno !== "undefined" ? Deno.build.os === "windows" ? "win32" : Deno.build.os : void 0;
    h3.URL = typeof URL !== "undefined" ? URL : null;
    h3.pathToFileURL = pathToFileURL$1;
    h3.fileURLToPath = fileURLToPath$1;
    h3.Url;
    h3.format;
    h3.resolve;
    h3.resolveObject;
    h3.URL;
    CHAR_BACKWARD_SLASH$1 = 92;
    CHAR_FORWARD_SLASH$1 = 47;
    CHAR_LOWERCASE_A$1 = 97;
    CHAR_LOWERCASE_Z$1 = 122;
    isWindows$1 = processPlatform$1 === "win32";
    forwardSlashRegEx$1 = /\//g;
    percentRegEx$1 = /%/g;
    backslashRegEx$1 = /\\/g;
    newlineRegEx$1 = /\n/g;
    carriageReturnRegEx$1 = /\r/g;
    tabRegEx$1 = /\t/g;
    processPlatform = typeof Deno !== "undefined" ? Deno.build.os === "windows" ? "win32" : Deno.build.os : void 0;
    h3.URL = typeof URL !== "undefined" ? URL : null;
    h3.pathToFileURL = pathToFileURL;
    h3.fileURLToPath = fileURLToPath;
    h3.Url;
    h3.format;
    h3.resolve;
    h3.resolveObject;
    h3.parse;
    h3.URL;
    CHAR_BACKWARD_SLASH = 92;
    CHAR_FORWARD_SLASH = 47;
    CHAR_LOWERCASE_A = 97;
    CHAR_LOWERCASE_Z = 122;
    isWindows = processPlatform === "win32";
    forwardSlashRegEx = /\//g;
    percentRegEx = /%/g;
    backslashRegEx = /\\/g;
    newlineRegEx = /\n/g;
    carriageReturnRegEx = /\r/g;
    tabRegEx = /\t/g;
  }
});

// node_modules/@jspm/core/nodelibs/browser/chunk-DEMDiNwt.js
function unimplemented2(name2) {
  throw new Error("Node.js process " + name2 + " is not supported by JSPM core outside of Node.js");
}
function cleanUpNextTick2() {
  if (!draining2 || !currentQueue2)
    return;
  draining2 = false;
  if (currentQueue2.length) {
    queue2 = currentQueue2.concat(queue2);
  } else {
    queueIndex2 = -1;
  }
  if (queue2.length)
    drainQueue2();
}
function drainQueue2() {
  if (draining2)
    return;
  var timeout = setTimeout(cleanUpNextTick2, 0);
  draining2 = true;
  var len = queue2.length;
  while (len) {
    currentQueue2 = queue2;
    queue2 = [];
    while (++queueIndex2 < len) {
      if (currentQueue2)
        currentQueue2[queueIndex2].run();
    }
    queueIndex2 = -1;
    len = queue2.length;
  }
  currentQueue2 = null;
  draining2 = false;
  clearTimeout(timeout);
}
function nextTick2(fun) {
  var args = new Array(arguments.length - 1);
  if (arguments.length > 1) {
    for (var i6 = 1; i6 < arguments.length; i6++)
      args[i6 - 1] = arguments[i6];
  }
  queue2.push(new Item2(fun, args));
  if (queue2.length === 1 && !draining2)
    setTimeout(drainQueue2, 0);
}
function Item2(fun, array) {
  this.fun = fun;
  this.array = array;
}
function noop2() {
}
function _linkedBinding2(name2) {
  unimplemented2("_linkedBinding");
}
function dlopen2(name2) {
  unimplemented2("dlopen");
}
function _getActiveRequests2() {
  return [];
}
function _getActiveHandles2() {
  return [];
}
function assert2(condition, message) {
  if (!condition) throw new Error(message || "assertion error");
}
function hasUncaughtExceptionCaptureCallback2() {
  return false;
}
function uptime2() {
  return _performance2.now() / 1e3;
}
function hrtime2(previousTimestamp) {
  var baseNow = Math.floor((Date.now() - _performance2.now()) * 1e-3);
  var clocktime = _performance2.now() * 1e-3;
  var seconds = Math.floor(clocktime) + baseNow;
  var nanoseconds = Math.floor(clocktime % 1 * 1e9);
  if (previousTimestamp) {
    seconds = seconds - previousTimestamp[0];
    nanoseconds = nanoseconds - previousTimestamp[1];
    if (nanoseconds < 0) {
      seconds--;
      nanoseconds += nanoPerSec2;
    }
  }
  return [seconds, nanoseconds];
}
function on2() {
  return process3;
}
function listeners2(name2) {
  return [];
}
var queue2, draining2, currentQueue2, queueIndex2, title2, arch2, platform2, env2, argv2, execArgv2, version2, versions2, emitWarning2, binding2, umask2, cwd2, chdir2, release2, _rawDebug2, moduleLoadList2, domain2, _exiting2, config2, reallyExit2, _kill2, cpuUsage2, resourceUsage2, memoryUsage2, kill2, exit3, openStdin2, allowedNodeEnvironmentFlags2, features2, _fatalExceptions2, setUncaughtExceptionCaptureCallback2, _tickCallback2, _debugProcess2, _debugEnd2, _startProfilerIdleNotifier2, _stopProfilerIdleNotifier2, stdout3, stderr3, stdin3, abort2, pid2, ppid2, execPath2, debugPort2, argv02, _preload_modules2, setSourceMapsEnabled2, _performance2, nowOffset2, nanoPerSec2, _maxListeners2, _events2, _eventsCount2, addListener2, once2, off2, removeListener2, removeAllListeners2, emit2, prependListener2, prependOnceListener2, process3;
var init_chunk_DEMDiNwt = __esm({
  "node_modules/@jspm/core/nodelibs/browser/chunk-DEMDiNwt.js"() {
    init_dirname();
    init_buffer2();
    init_process2();
    queue2 = [];
    draining2 = false;
    queueIndex2 = -1;
    Item2.prototype.run = function() {
      this.fun.apply(null, this.array);
    };
    title2 = "browser";
    arch2 = "x64";
    platform2 = "browser";
    env2 = {
      PATH: "/usr/bin",
      LANG: navigator.language + ".UTF-8",
      PWD: "/",
      HOME: "/home",
      TMP: "/tmp"
    };
    argv2 = ["/usr/bin/node"];
    execArgv2 = [];
    version2 = "v16.8.0";
    versions2 = {};
    emitWarning2 = function(message, type) {
      console.warn((type ? type + ": " : "") + message);
    };
    binding2 = function(name2) {
      unimplemented2("binding");
    };
    umask2 = function(mask) {
      return 0;
    };
    cwd2 = function() {
      return "/";
    };
    chdir2 = function(dir) {
    };
    release2 = {
      name: "node",
      sourceUrl: "",
      headersUrl: "",
      libUrl: ""
    };
    _rawDebug2 = noop2;
    moduleLoadList2 = [];
    domain2 = {};
    _exiting2 = false;
    config2 = {};
    reallyExit2 = noop2;
    _kill2 = noop2;
    cpuUsage2 = function() {
      return {};
    };
    resourceUsage2 = cpuUsage2;
    memoryUsage2 = cpuUsage2;
    kill2 = noop2;
    exit3 = noop2;
    openStdin2 = noop2;
    allowedNodeEnvironmentFlags2 = {};
    features2 = {
      inspector: false,
      debug: false,
      uv: false,
      ipv6: false,
      tls_alpn: false,
      tls_sni: false,
      tls_ocsp: false,
      tls: false,
      cached_builtins: true
    };
    _fatalExceptions2 = noop2;
    setUncaughtExceptionCaptureCallback2 = noop2;
    _tickCallback2 = noop2;
    _debugProcess2 = noop2;
    _debugEnd2 = noop2;
    _startProfilerIdleNotifier2 = noop2;
    _stopProfilerIdleNotifier2 = noop2;
    stdout3 = void 0;
    stderr3 = void 0;
    stdin3 = void 0;
    abort2 = noop2;
    pid2 = 2;
    ppid2 = 1;
    execPath2 = "/bin/usr/node";
    debugPort2 = 9229;
    argv02 = "node";
    _preload_modules2 = [];
    setSourceMapsEnabled2 = noop2;
    _performance2 = {
      now: typeof performance !== "undefined" ? performance.now.bind(performance) : void 0,
      timing: typeof performance !== "undefined" ? performance.timing : void 0
    };
    if (_performance2.now === void 0) {
      nowOffset2 = Date.now();
      if (_performance2.timing && _performance2.timing.navigationStart) {
        nowOffset2 = _performance2.timing.navigationStart;
      }
      _performance2.now = () => Date.now() - nowOffset2;
    }
    nanoPerSec2 = 1e9;
    hrtime2.bigint = function(time) {
      var diff = hrtime2(time);
      if (typeof BigInt === "undefined") {
        return diff[0] * nanoPerSec2 + diff[1];
      }
      return BigInt(diff[0] * nanoPerSec2) + BigInt(diff[1]);
    };
    _maxListeners2 = 10;
    _events2 = {};
    _eventsCount2 = 0;
    addListener2 = on2;
    once2 = on2;
    off2 = on2;
    removeListener2 = on2;
    removeAllListeners2 = on2;
    emit2 = noop2;
    prependListener2 = on2;
    prependOnceListener2 = on2;
    process3 = {
      version: version2,
      versions: versions2,
      arch: arch2,
      platform: platform2,
      release: release2,
      _rawDebug: _rawDebug2,
      moduleLoadList: moduleLoadList2,
      binding: binding2,
      _linkedBinding: _linkedBinding2,
      _events: _events2,
      _eventsCount: _eventsCount2,
      _maxListeners: _maxListeners2,
      on: on2,
      addListener: addListener2,
      once: once2,
      off: off2,
      removeListener: removeListener2,
      removeAllListeners: removeAllListeners2,
      emit: emit2,
      prependListener: prependListener2,
      prependOnceListener: prependOnceListener2,
      listeners: listeners2,
      domain: domain2,
      _exiting: _exiting2,
      config: config2,
      dlopen: dlopen2,
      uptime: uptime2,
      _getActiveRequests: _getActiveRequests2,
      _getActiveHandles: _getActiveHandles2,
      reallyExit: reallyExit2,
      _kill: _kill2,
      cpuUsage: cpuUsage2,
      resourceUsage: resourceUsage2,
      memoryUsage: memoryUsage2,
      kill: kill2,
      exit: exit3,
      openStdin: openStdin2,
      allowedNodeEnvironmentFlags: allowedNodeEnvironmentFlags2,
      assert: assert2,
      features: features2,
      _fatalExceptions: _fatalExceptions2,
      setUncaughtExceptionCaptureCallback: setUncaughtExceptionCaptureCallback2,
      hasUncaughtExceptionCaptureCallback: hasUncaughtExceptionCaptureCallback2,
      emitWarning: emitWarning2,
      nextTick: nextTick2,
      _tickCallback: _tickCallback2,
      _debugProcess: _debugProcess2,
      _debugEnd: _debugEnd2,
      _startProfilerIdleNotifier: _startProfilerIdleNotifier2,
      _stopProfilerIdleNotifier: _stopProfilerIdleNotifier2,
      stdout: stdout3,
      stdin: stdin3,
      stderr: stderr3,
      abort: abort2,
      umask: umask2,
      chdir: chdir2,
      cwd: cwd2,
      env: env2,
      title: title2,
      argv: argv2,
      execArgv: execArgv2,
      pid: pid2,
      ppid: ppid2,
      execPath: execPath2,
      debugPort: debugPort2,
      hrtime: hrtime2,
      argv0: argv02,
      _preload_modules: _preload_modules2,
      setSourceMapsEnabled: setSourceMapsEnabled2
    };
  }
});

// node_modules/@jspm/core/nodelibs/browser/chunk-tHuMsdT0.js
function o4() {
  o4.init.call(this);
}
function u4(e6) {
  if ("function" != typeof e6) throw new TypeError('The "listener" argument must be of type Function. Received type ' + typeof e6);
}
function f4(e6) {
  return void 0 === e6._maxListeners ? o4.defaultMaxListeners : e6._maxListeners;
}
function v4(e6, t6, n6, r6) {
  var i6, o6, s6, v6;
  if (u4(n6), void 0 === (o6 = e6._events) ? (o6 = e6._events = /* @__PURE__ */ Object.create(null), e6._eventsCount = 0) : (void 0 !== o6.newListener && (e6.emit("newListener", t6, n6.listener ? n6.listener : n6), o6 = e6._events), s6 = o6[t6]), void 0 === s6) s6 = o6[t6] = n6, ++e6._eventsCount;
  else if ("function" == typeof s6 ? s6 = o6[t6] = r6 ? [n6, s6] : [s6, n6] : r6 ? s6.unshift(n6) : s6.push(n6), (i6 = f4(e6)) > 0 && s6.length > i6 && !s6.warned) {
    s6.warned = true;
    var a6 = new Error("Possible EventEmitter memory leak detected. " + s6.length + " " + String(t6) + " listeners added. Use emitter.setMaxListeners() to increase limit");
    a6.name = "MaxListenersExceededWarning", a6.emitter = e6, a6.type = t6, a6.count = s6.length, v6 = a6, console && console.warn && console.warn(v6);
  }
  return e6;
}
function a4() {
  if (!this.fired) return this.target.removeListener(this.type, this.wrapFn), this.fired = true, 0 === arguments.length ? this.listener.call(this.target) : this.listener.apply(this.target, arguments);
}
function l4(e6, t6, n6) {
  var r6 = { fired: false, wrapFn: void 0, target: e6, type: t6, listener: n6 }, i6 = a4.bind(r6);
  return i6.listener = n6, r6.wrapFn = i6, i6;
}
function h4(e6, t6, n6) {
  var r6 = e6._events;
  if (void 0 === r6) return [];
  var i6 = r6[t6];
  return void 0 === i6 ? [] : "function" == typeof i6 ? n6 ? [i6.listener || i6] : [i6] : n6 ? (function(e7) {
    for (var t7 = new Array(e7.length), n7 = 0; n7 < t7.length; ++n7) t7[n7] = e7[n7].listener || e7[n7];
    return t7;
  })(i6) : c4(i6, i6.length);
}
function p4(e6) {
  var t6 = this._events;
  if (void 0 !== t6) {
    var n6 = t6[e6];
    if ("function" == typeof n6) return 1;
    if (void 0 !== n6) return n6.length;
  }
  return 0;
}
function c4(e6, t6) {
  for (var n6 = new Array(t6), r6 = 0; r6 < t6; ++r6) n6[r6] = e6[r6];
  return n6;
}
var e4, t4, n4, r4, i4, s4, y4;
var init_chunk_tHuMsdT0 = __esm({
  "node_modules/@jspm/core/nodelibs/browser/chunk-tHuMsdT0.js"() {
    init_dirname();
    init_buffer2();
    init_process2();
    n4 = "object" == typeof Reflect ? Reflect : null;
    r4 = n4 && "function" == typeof n4.apply ? n4.apply : function(e6, t6, n6) {
      return Function.prototype.apply.call(e6, t6, n6);
    };
    t4 = n4 && "function" == typeof n4.ownKeys ? n4.ownKeys : Object.getOwnPropertySymbols ? function(e6) {
      return Object.getOwnPropertyNames(e6).concat(Object.getOwnPropertySymbols(e6));
    } : function(e6) {
      return Object.getOwnPropertyNames(e6);
    };
    i4 = Number.isNaN || function(e6) {
      return e6 != e6;
    };
    e4 = o4, o4.EventEmitter = o4, o4.prototype._events = void 0, o4.prototype._eventsCount = 0, o4.prototype._maxListeners = void 0;
    s4 = 10;
    Object.defineProperty(o4, "defaultMaxListeners", { enumerable: true, get: function() {
      return s4;
    }, set: function(e6) {
      if ("number" != typeof e6 || e6 < 0 || i4(e6)) throw new RangeError('The value of "defaultMaxListeners" is out of range. It must be a non-negative number. Received ' + e6 + ".");
      s4 = e6;
    } }), o4.init = function() {
      void 0 !== this._events && this._events !== Object.getPrototypeOf(this)._events || (this._events = /* @__PURE__ */ Object.create(null), this._eventsCount = 0), this._maxListeners = this._maxListeners || void 0;
    }, o4.prototype.setMaxListeners = function(e6) {
      if ("number" != typeof e6 || e6 < 0 || i4(e6)) throw new RangeError('The value of "n" is out of range. It must be a non-negative number. Received ' + e6 + ".");
      return this._maxListeners = e6, this;
    }, o4.prototype.getMaxListeners = function() {
      return f4(this);
    }, o4.prototype.emit = function(e6) {
      for (var t6 = [], n6 = 1; n6 < arguments.length; n6++) t6.push(arguments[n6]);
      var i6 = "error" === e6, o6 = this._events;
      if (void 0 !== o6) i6 = i6 && void 0 === o6.error;
      else if (!i6) return false;
      if (i6) {
        var s6;
        if (t6.length > 0 && (s6 = t6[0]), s6 instanceof Error) throw s6;
        var u6 = new Error("Unhandled error." + (s6 ? " (" + s6.message + ")" : ""));
        throw u6.context = s6, u6;
      }
      var f6 = o6[e6];
      if (void 0 === f6) return false;
      if ("function" == typeof f6) r4(f6, this, t6);
      else {
        var v6 = f6.length, a6 = c4(f6, v6);
        for (n6 = 0; n6 < v6; ++n6) r4(a6[n6], this, t6);
      }
      return true;
    }, o4.prototype.addListener = function(e6, t6) {
      return v4(this, e6, t6, false);
    }, o4.prototype.on = o4.prototype.addListener, o4.prototype.prependListener = function(e6, t6) {
      return v4(this, e6, t6, true);
    }, o4.prototype.once = function(e6, t6) {
      return u4(t6), this.on(e6, l4(this, e6, t6)), this;
    }, o4.prototype.prependOnceListener = function(e6, t6) {
      return u4(t6), this.prependListener(e6, l4(this, e6, t6)), this;
    }, o4.prototype.removeListener = function(e6, t6) {
      var n6, r6, i6, o6, s6;
      if (u4(t6), void 0 === (r6 = this._events)) return this;
      if (void 0 === (n6 = r6[e6])) return this;
      if (n6 === t6 || n6.listener === t6) 0 == --this._eventsCount ? this._events = /* @__PURE__ */ Object.create(null) : (delete r6[e6], r6.removeListener && this.emit("removeListener", e6, n6.listener || t6));
      else if ("function" != typeof n6) {
        for (i6 = -1, o6 = n6.length - 1; o6 >= 0; o6--) if (n6[o6] === t6 || n6[o6].listener === t6) {
          s6 = n6[o6].listener, i6 = o6;
          break;
        }
        if (i6 < 0) return this;
        0 === i6 ? n6.shift() : !(function(e7, t7) {
          for (; t7 + 1 < e7.length; t7++) e7[t7] = e7[t7 + 1];
          e7.pop();
        })(n6, i6), 1 === n6.length && (r6[e6] = n6[0]), void 0 !== r6.removeListener && this.emit("removeListener", e6, s6 || t6);
      }
      return this;
    }, o4.prototype.off = o4.prototype.removeListener, o4.prototype.removeAllListeners = function(e6) {
      var t6, n6, r6;
      if (void 0 === (n6 = this._events)) return this;
      if (void 0 === n6.removeListener) return 0 === arguments.length ? (this._events = /* @__PURE__ */ Object.create(null), this._eventsCount = 0) : void 0 !== n6[e6] && (0 == --this._eventsCount ? this._events = /* @__PURE__ */ Object.create(null) : delete n6[e6]), this;
      if (0 === arguments.length) {
        var i6, o6 = Object.keys(n6);
        for (r6 = 0; r6 < o6.length; ++r6) "removeListener" !== (i6 = o6[r6]) && this.removeAllListeners(i6);
        return this.removeAllListeners("removeListener"), this._events = /* @__PURE__ */ Object.create(null), this._eventsCount = 0, this;
      }
      if ("function" == typeof (t6 = n6[e6])) this.removeListener(e6, t6);
      else if (void 0 !== t6) for (r6 = t6.length - 1; r6 >= 0; r6--) this.removeListener(e6, t6[r6]);
      return this;
    }, o4.prototype.listeners = function(e6) {
      return h4(this, e6, true);
    }, o4.prototype.rawListeners = function(e6) {
      return h4(this, e6, false);
    }, o4.listenerCount = function(e6, t6) {
      return "function" == typeof e6.listenerCount ? e6.listenerCount(t6) : p4.call(e6, t6);
    }, o4.prototype.listenerCount = p4, o4.prototype.eventNames = function() {
      return this._eventsCount > 0 ? t4(this._events) : [];
    };
    y4 = e4;
    y4.EventEmitter;
    y4.defaultMaxListeners;
    y4.init;
    y4.listenerCount;
    y4.EventEmitter;
    y4.defaultMaxListeners;
    y4.init;
    y4.listenerCount;
  }
});

// node_modules/@jspm/core/nodelibs/browser/chunk-DtDiafJB.js
var init_chunk_DtDiafJB = __esm({
  "node_modules/@jspm/core/nodelibs/browser/chunk-DtDiafJB.js"() {
    init_dirname();
    init_buffer2();
    init_process2();
    init_chunk_tHuMsdT0();
    y4.once = function(emitter, event) {
      return new Promise((resolve2, reject) => {
        function eventListener(...args) {
          if (errorListener !== void 0) {
            emitter.removeListener("error", errorListener);
          }
          resolve2(args);
        }
        let errorListener;
        if (event !== "error") {
          errorListener = (err) => {
            emitter.removeListener(name, eventListener);
            reject(err);
          };
          emitter.once("error", errorListener);
        }
        emitter.once(event, eventListener);
      });
    };
    y4.on = function(emitter, event) {
      const unconsumedEventValues = [];
      const unconsumedPromises = [];
      let error2 = null;
      let finished = false;
      const iterator = {
        async next() {
          const value = unconsumedEventValues.shift();
          if (value) {
            return createIterResult(value, false);
          }
          if (error2) {
            const p6 = Promise.reject(error2);
            error2 = null;
            return p6;
          }
          if (finished) {
            return createIterResult(void 0, true);
          }
          return new Promise((resolve2, reject) => unconsumedPromises.push({ resolve: resolve2, reject }));
        },
        async return() {
          emitter.removeListener(event, eventHandler);
          emitter.removeListener("error", errorHandler);
          finished = true;
          for (const promise of unconsumedPromises) {
            promise.resolve(createIterResult(void 0, true));
          }
          return createIterResult(void 0, true);
        },
        throw(err) {
          error2 = err;
          emitter.removeListener(event, eventHandler);
          emitter.removeListener("error", errorHandler);
        },
        [Symbol.asyncIterator]() {
          return this;
        }
      };
      emitter.on(event, eventHandler);
      emitter.on("error", errorHandler);
      return iterator;
      function eventHandler(...args) {
        const promise = unconsumedPromises.shift();
        if (promise) {
          promise.resolve(createIterResult(args, false));
        } else {
          unconsumedEventValues.push(args);
        }
      }
      function errorHandler(err) {
        finished = true;
        const toError = unconsumedPromises.shift();
        if (toError) {
          toError.reject(err);
        } else {
          error2 = err;
        }
        iterator.return();
      }
    };
  }
});

// node_modules/@jspm/core/nodelibs/browser/chunk-B738Er4n.js
function u$23(r6) {
  var t6 = r6.length;
  if (t6 % 4 > 0) throw new Error("Invalid string. Length must be a multiple of 4");
  var e6 = r6.indexOf("=");
  return -1 === e6 && (e6 = t6), [e6, e6 === t6 ? 0 : 4 - e6 % 4];
}
function c$14(r6, e6, n6) {
  for (var o6, a6, h6 = [], u6 = e6; u6 < n6; u6 += 3) o6 = (r6[u6] << 16 & 16711680) + (r6[u6 + 1] << 8 & 65280) + (255 & r6[u6 + 2]), h6.push(t$14[(a6 = o6) >> 18 & 63] + t$14[a6 >> 12 & 63] + t$14[a6 >> 6 & 63] + t$14[63 & a6]);
  return h6.join("");
}
function f$22(t6) {
  if (t6 > 2147483647) throw new RangeError('The value "' + t6 + '" is invalid for option "size"');
  var r6 = new Uint8Array(t6);
  return Object.setPrototypeOf(r6, u$1$1.prototype), r6;
}
function u$1$1(t6, r6, e6) {
  if ("number" == typeof t6) {
    if ("string" == typeof r6) throw new TypeError('The "string" argument must be of type string. Received type number');
    return a$22(t6);
  }
  return s$13(t6, r6, e6);
}
function s$13(t6, r6, e6) {
  if ("string" == typeof t6) return (function(t7, r7) {
    "string" == typeof r7 && "" !== r7 || (r7 = "utf8");
    if (!u$1$1.isEncoding(r7)) throw new TypeError("Unknown encoding: " + r7);
    var e7 = 0 | y5(t7, r7), n7 = f$22(e7), i7 = n7.write(t7, r7);
    i7 !== e7 && (n7 = n7.slice(0, i7));
    return n7;
  })(t6, r6);
  if (ArrayBuffer.isView(t6)) return p5(t6);
  if (null == t6) throw new TypeError("The first argument must be one of type string, Buffer, ArrayBuffer, Array, or Array-like Object. Received type " + typeof t6);
  if (F3(t6, ArrayBuffer) || t6 && F3(t6.buffer, ArrayBuffer)) return c$1$1(t6, r6, e6);
  if ("undefined" != typeof SharedArrayBuffer && (F3(t6, SharedArrayBuffer) || t6 && F3(t6.buffer, SharedArrayBuffer))) return c$1$1(t6, r6, e6);
  if ("number" == typeof t6) throw new TypeError('The "value" argument must not be of type number. Received type number');
  var n6 = t6.valueOf && t6.valueOf();
  if (null != n6 && n6 !== t6) return u$1$1.from(n6, r6, e6);
  var i6 = (function(t7) {
    if (u$1$1.isBuffer(t7)) {
      var r7 = 0 | l$14(t7.length), e7 = f$22(r7);
      return 0 === e7.length || t7.copy(e7, 0, 0, r7), e7;
    }
    if (void 0 !== t7.length) return "number" != typeof t7.length || N3(t7.length) ? f$22(0) : p5(t7);
    if ("Buffer" === t7.type && Array.isArray(t7.data)) return p5(t7.data);
  })(t6);
  if (i6) return i6;
  if ("undefined" != typeof Symbol && null != Symbol.toPrimitive && "function" == typeof t6[Symbol.toPrimitive]) return u$1$1.from(t6[Symbol.toPrimitive]("string"), r6, e6);
  throw new TypeError("The first argument must be one of type string, Buffer, ArrayBuffer, Array, or Array-like Object. Received type " + typeof t6);
}
function h$1$1(t6) {
  if ("number" != typeof t6) throw new TypeError('"size" argument must be of type number');
  if (t6 < 0) throw new RangeError('The value "' + t6 + '" is invalid for option "size"');
}
function a$22(t6) {
  return h$1$1(t6), f$22(t6 < 0 ? 0 : 0 | l$14(t6));
}
function p5(t6) {
  for (var r6 = t6.length < 0 ? 0 : 0 | l$14(t6.length), e6 = f$22(r6), n6 = 0; n6 < r6; n6 += 1) e6[n6] = 255 & t6[n6];
  return e6;
}
function c$1$1(t6, r6, e6) {
  if (r6 < 0 || t6.byteLength < r6) throw new RangeError('"offset" is outside of buffer bounds');
  if (t6.byteLength < r6 + (e6 || 0)) throw new RangeError('"length" is outside of buffer bounds');
  var n6;
  return n6 = void 0 === r6 && void 0 === e6 ? new Uint8Array(t6) : void 0 === e6 ? new Uint8Array(t6, r6) : new Uint8Array(t6, r6, e6), Object.setPrototypeOf(n6, u$1$1.prototype), n6;
}
function l$14(t6) {
  if (t6 >= 2147483647) throw new RangeError("Attempt to allocate Buffer larger than maximum size: 0x" + 2147483647 .toString(16) + " bytes");
  return 0 | t6;
}
function y5(t6, r6) {
  if (u$1$1.isBuffer(t6)) return t6.length;
  if (ArrayBuffer.isView(t6) || F3(t6, ArrayBuffer)) return t6.byteLength;
  if ("string" != typeof t6) throw new TypeError('The "string" argument must be one of type string, Buffer, or ArrayBuffer. Received type ' + typeof t6);
  var e6 = t6.length, n6 = arguments.length > 2 && true === arguments[2];
  if (!n6 && 0 === e6) return 0;
  for (var i6 = false; ; ) switch (r6) {
    case "ascii":
    case "latin1":
    case "binary":
      return e6;
    case "utf8":
    case "utf-8":
      return _3(t6).length;
    case "ucs2":
    case "ucs-2":
    case "utf16le":
    case "utf-16le":
      return 2 * e6;
    case "hex":
      return e6 >>> 1;
    case "base64":
      return z3(t6).length;
    default:
      if (i6) return n6 ? -1 : _3(t6).length;
      r6 = ("" + r6).toLowerCase(), i6 = true;
  }
}
function g4(t6, r6, e6) {
  var n6 = false;
  if ((void 0 === r6 || r6 < 0) && (r6 = 0), r6 > this.length) return "";
  if ((void 0 === e6 || e6 > this.length) && (e6 = this.length), e6 <= 0) return "";
  if ((e6 >>>= 0) <= (r6 >>>= 0)) return "";
  for (t6 || (t6 = "utf8"); ; ) switch (t6) {
    case "hex":
      return O4(this, r6, e6);
    case "utf8":
    case "utf-8":
      return I3(this, r6, e6);
    case "ascii":
      return S3(this, r6, e6);
    case "latin1":
    case "binary":
      return R3(this, r6, e6);
    case "base64":
      return T3(this, r6, e6);
    case "ucs2":
    case "ucs-2":
    case "utf16le":
    case "utf-16le":
      return L3(this, r6, e6);
    default:
      if (n6) throw new TypeError("Unknown encoding: " + t6);
      t6 = (t6 + "").toLowerCase(), n6 = true;
  }
}
function w3(t6, r6, e6) {
  var n6 = t6[r6];
  t6[r6] = t6[e6], t6[e6] = n6;
}
function d4(t6, r6, e6, n6, i6) {
  if (0 === t6.length) return -1;
  if ("string" == typeof e6 ? (n6 = e6, e6 = 0) : e6 > 2147483647 ? e6 = 2147483647 : e6 < -2147483648 && (e6 = -2147483648), N3(e6 = +e6) && (e6 = i6 ? 0 : t6.length - 1), e6 < 0 && (e6 = t6.length + e6), e6 >= t6.length) {
    if (i6) return -1;
    e6 = t6.length - 1;
  } else if (e6 < 0) {
    if (!i6) return -1;
    e6 = 0;
  }
  if ("string" == typeof r6 && (r6 = u$1$1.from(r6, n6)), u$1$1.isBuffer(r6)) return 0 === r6.length ? -1 : v5(t6, r6, e6, n6, i6);
  if ("number" == typeof r6) return r6 &= 255, "function" == typeof Uint8Array.prototype.indexOf ? i6 ? Uint8Array.prototype.indexOf.call(t6, r6, e6) : Uint8Array.prototype.lastIndexOf.call(t6, r6, e6) : v5(t6, [r6], e6, n6, i6);
  throw new TypeError("val must be string, number or Buffer");
}
function v5(t6, r6, e6, n6, i6) {
  var o6, f6 = 1, u6 = t6.length, s6 = r6.length;
  if (void 0 !== n6 && ("ucs2" === (n6 = String(n6).toLowerCase()) || "ucs-2" === n6 || "utf16le" === n6 || "utf-16le" === n6)) {
    if (t6.length < 2 || r6.length < 2) return -1;
    f6 = 2, u6 /= 2, s6 /= 2, e6 /= 2;
  }
  function h6(t7, r7) {
    return 1 === f6 ? t7[r7] : t7.readUInt16BE(r7 * f6);
  }
  if (i6) {
    var a6 = -1;
    for (o6 = e6; o6 < u6; o6++) if (h6(t6, o6) === h6(r6, -1 === a6 ? 0 : o6 - a6)) {
      if (-1 === a6 && (a6 = o6), o6 - a6 + 1 === s6) return a6 * f6;
    } else -1 !== a6 && (o6 -= o6 - a6), a6 = -1;
  } else for (e6 + s6 > u6 && (e6 = u6 - s6), o6 = e6; o6 >= 0; o6--) {
    for (var p6 = true, c6 = 0; c6 < s6; c6++) if (h6(t6, o6 + c6) !== h6(r6, c6)) {
      p6 = false;
      break;
    }
    if (p6) return o6;
  }
  return -1;
}
function b4(t6, r6, e6, n6) {
  e6 = Number(e6) || 0;
  var i6 = t6.length - e6;
  n6 ? (n6 = Number(n6)) > i6 && (n6 = i6) : n6 = i6;
  var o6 = r6.length;
  n6 > o6 / 2 && (n6 = o6 / 2);
  for (var f6 = 0; f6 < n6; ++f6) {
    var u6 = parseInt(r6.substr(2 * f6, 2), 16);
    if (N3(u6)) return f6;
    t6[e6 + f6] = u6;
  }
  return f6;
}
function m4(t6, r6, e6, n6) {
  return D3(_3(r6, t6.length - e6), t6, e6, n6);
}
function E3(t6, r6, e6, n6) {
  return D3((function(t7) {
    for (var r7 = [], e7 = 0; e7 < t7.length; ++e7) r7.push(255 & t7.charCodeAt(e7));
    return r7;
  })(r6), t6, e6, n6);
}
function B3(t6, r6, e6, n6) {
  return E3(t6, r6, e6, n6);
}
function A3(t6, r6, e6, n6) {
  return D3(z3(r6), t6, e6, n6);
}
function U3(t6, r6, e6, n6) {
  return D3((function(t7, r7) {
    for (var e7, n7, i6, o6 = [], f6 = 0; f6 < t7.length && !((r7 -= 2) < 0); ++f6) e7 = t7.charCodeAt(f6), n7 = e7 >> 8, i6 = e7 % 256, o6.push(i6), o6.push(n7);
    return o6;
  })(r6, t6.length - e6), t6, e6, n6);
}
function T3(t6, r6, e6) {
  return 0 === r6 && e6 === t6.length ? n$1$1.fromByteArray(t6) : n$1$1.fromByteArray(t6.slice(r6, e6));
}
function I3(t6, r6, e6) {
  e6 = Math.min(t6.length, e6);
  for (var n6 = [], i6 = r6; i6 < e6; ) {
    var o6, f6, u6, s6, h6 = t6[i6], a6 = null, p6 = h6 > 239 ? 4 : h6 > 223 ? 3 : h6 > 191 ? 2 : 1;
    if (i6 + p6 <= e6) switch (p6) {
      case 1:
        h6 < 128 && (a6 = h6);
        break;
      case 2:
        128 == (192 & (o6 = t6[i6 + 1])) && (s6 = (31 & h6) << 6 | 63 & o6) > 127 && (a6 = s6);
        break;
      case 3:
        o6 = t6[i6 + 1], f6 = t6[i6 + 2], 128 == (192 & o6) && 128 == (192 & f6) && (s6 = (15 & h6) << 12 | (63 & o6) << 6 | 63 & f6) > 2047 && (s6 < 55296 || s6 > 57343) && (a6 = s6);
        break;
      case 4:
        o6 = t6[i6 + 1], f6 = t6[i6 + 2], u6 = t6[i6 + 3], 128 == (192 & o6) && 128 == (192 & f6) && 128 == (192 & u6) && (s6 = (15 & h6) << 18 | (63 & o6) << 12 | (63 & f6) << 6 | 63 & u6) > 65535 && s6 < 1114112 && (a6 = s6);
    }
    null === a6 ? (a6 = 65533, p6 = 1) : a6 > 65535 && (a6 -= 65536, n6.push(a6 >>> 10 & 1023 | 55296), a6 = 56320 | 1023 & a6), n6.push(a6), i6 += p6;
  }
  return (function(t7) {
    var r7 = t7.length;
    if (r7 <= 4096) return String.fromCharCode.apply(String, t7);
    var e7 = "", n7 = 0;
    for (; n7 < r7; ) e7 += String.fromCharCode.apply(String, t7.slice(n7, n7 += 4096));
    return e7;
  })(n6);
}
function S3(t6, r6, e6) {
  var n6 = "";
  e6 = Math.min(t6.length, e6);
  for (var i6 = r6; i6 < e6; ++i6) n6 += String.fromCharCode(127 & t6[i6]);
  return n6;
}
function R3(t6, r6, e6) {
  var n6 = "";
  e6 = Math.min(t6.length, e6);
  for (var i6 = r6; i6 < e6; ++i6) n6 += String.fromCharCode(t6[i6]);
  return n6;
}
function O4(t6, r6, e6) {
  var n6 = t6.length;
  (!r6 || r6 < 0) && (r6 = 0), (!e6 || e6 < 0 || e6 > n6) && (e6 = n6);
  for (var i6 = "", o6 = r6; o6 < e6; ++o6) i6 += Y3[t6[o6]];
  return i6;
}
function L3(t6, r6, e6) {
  for (var n6 = t6.slice(r6, e6), i6 = "", o6 = 0; o6 < n6.length; o6 += 2) i6 += String.fromCharCode(n6[o6] + 256 * n6[o6 + 1]);
  return i6;
}
function x3(t6, r6, e6) {
  if (t6 % 1 != 0 || t6 < 0) throw new RangeError("offset is not uint");
  if (t6 + r6 > e6) throw new RangeError("Trying to access beyond buffer length");
}
function C3(t6, r6, e6, n6, i6, o6) {
  if (!u$1$1.isBuffer(t6)) throw new TypeError('"buffer" argument must be a Buffer instance');
  if (r6 > i6 || r6 < o6) throw new RangeError('"value" argument is out of bounds');
  if (e6 + n6 > t6.length) throw new RangeError("Index out of range");
}
function P3(t6, r6, e6, n6, i6, o6) {
  if (e6 + n6 > t6.length) throw new RangeError("Index out of range");
  if (e6 < 0) throw new RangeError("Index out of range");
}
function k3(t6, r6, e6, n6, o6) {
  return r6 = +r6, e6 >>>= 0, o6 || P3(t6, 0, e6, 4), i$14.write(t6, r6, e6, n6, 23, 4), e6 + 4;
}
function M3(t6, r6, e6, n6, o6) {
  return r6 = +r6, e6 >>>= 0, o6 || P3(t6, 0, e6, 8), i$14.write(t6, r6, e6, n6, 52, 8), e6 + 8;
}
function _3(t6, r6) {
  var e6;
  r6 = r6 || 1 / 0;
  for (var n6 = t6.length, i6 = null, o6 = [], f6 = 0; f6 < n6; ++f6) {
    if ((e6 = t6.charCodeAt(f6)) > 55295 && e6 < 57344) {
      if (!i6) {
        if (e6 > 56319) {
          (r6 -= 3) > -1 && o6.push(239, 191, 189);
          continue;
        }
        if (f6 + 1 === n6) {
          (r6 -= 3) > -1 && o6.push(239, 191, 189);
          continue;
        }
        i6 = e6;
        continue;
      }
      if (e6 < 56320) {
        (r6 -= 3) > -1 && o6.push(239, 191, 189), i6 = e6;
        continue;
      }
      e6 = 65536 + (i6 - 55296 << 10 | e6 - 56320);
    } else i6 && (r6 -= 3) > -1 && o6.push(239, 191, 189);
    if (i6 = null, e6 < 128) {
      if ((r6 -= 1) < 0) break;
      o6.push(e6);
    } else if (e6 < 2048) {
      if ((r6 -= 2) < 0) break;
      o6.push(e6 >> 6 | 192, 63 & e6 | 128);
    } else if (e6 < 65536) {
      if ((r6 -= 3) < 0) break;
      o6.push(e6 >> 12 | 224, e6 >> 6 & 63 | 128, 63 & e6 | 128);
    } else {
      if (!(e6 < 1114112)) throw new Error("Invalid code point");
      if ((r6 -= 4) < 0) break;
      o6.push(e6 >> 18 | 240, e6 >> 12 & 63 | 128, e6 >> 6 & 63 | 128, 63 & e6 | 128);
    }
  }
  return o6;
}
function z3(t6) {
  return n$1$1.toByteArray((function(t7) {
    if ((t7 = (t7 = t7.split("=")[0]).trim().replace(j3, "")).length < 2) return "";
    for (; t7.length % 4 != 0; ) t7 += "=";
    return t7;
  })(t6));
}
function D3(t6, r6, e6, n6) {
  for (var i6 = 0; i6 < n6 && !(i6 + e6 >= r6.length || i6 >= t6.length); ++i6) r6[i6 + e6] = t6[i6];
  return i6;
}
function F3(t6, r6) {
  return t6 instanceof r6 || null != t6 && null != t6.constructor && null != t6.constructor.name && t6.constructor.name === r6.name;
}
function N3(t6) {
  return t6 != t6;
}
function t5(r6, e6) {
  for (var n6 in r6) e6[n6] = r6[n6];
}
function f5(r6, e6, n6) {
  return o5(r6, e6, n6);
}
function a5(t6) {
  var e6;
  switch (this.encoding = (function(t7) {
    var e7 = (function(t8) {
      if (!t8) return "utf8";
      for (var e8; ; ) switch (t8) {
        case "utf8":
        case "utf-8":
          return "utf8";
        case "ucs2":
        case "ucs-2":
        case "utf16le":
        case "utf-16le":
          return "utf16le";
        case "latin1":
        case "binary":
          return "latin1";
        case "base64":
        case "ascii":
        case "hex":
          return t8;
        default:
          if (e8) return;
          t8 = ("" + t8).toLowerCase(), e8 = true;
      }
    })(t7);
    if ("string" != typeof e7 && (s5.isEncoding === i5 || !i5(t7))) throw new Error("Unknown encoding: " + t7);
    return e7 || t7;
  })(t6), this.encoding) {
    case "utf16le":
      this.text = h5, this.end = l5, e6 = 4;
      break;
    case "utf8":
      this.fillLast = n$14, e6 = 4;
      break;
    case "base64":
      this.text = u$14, this.end = o$14, e6 = 3;
      break;
    default:
      return this.write = f$14, this.end = c5, void 0;
  }
  this.lastNeed = 0, this.lastTotal = 0, this.lastChar = s5.allocUnsafe(e6);
}
function r5(t6) {
  return t6 <= 127 ? 0 : t6 >> 5 == 6 ? 2 : t6 >> 4 == 14 ? 3 : t6 >> 3 == 30 ? 4 : t6 >> 6 == 2 ? -1 : -2;
}
function n$14(t6) {
  var e6 = this.lastTotal - this.lastNeed, s6 = (function(t7, e7, s7) {
    if (128 != (192 & e7[0])) return t7.lastNeed = 0, "\uFFFD";
    if (t7.lastNeed > 1 && e7.length > 1) {
      if (128 != (192 & e7[1])) return t7.lastNeed = 1, "\uFFFD";
      if (t7.lastNeed > 2 && e7.length > 2 && 128 != (192 & e7[2])) return t7.lastNeed = 2, "\uFFFD";
    }
  })(this, t6);
  return void 0 !== s6 ? s6 : this.lastNeed <= t6.length ? (t6.copy(this.lastChar, e6, 0, this.lastNeed), this.lastChar.toString(this.encoding, 0, this.lastTotal)) : (t6.copy(this.lastChar, e6, 0, t6.length), this.lastNeed -= t6.length, void 0);
}
function h5(t6, e6) {
  if ((t6.length - e6) % 2 == 0) {
    var s6 = t6.toString("utf16le", e6);
    if (s6) {
      var i6 = s6.charCodeAt(s6.length - 1);
      if (i6 >= 55296 && i6 <= 56319) return this.lastNeed = 2, this.lastTotal = 4, this.lastChar[0] = t6[t6.length - 2], this.lastChar[1] = t6[t6.length - 1], s6.slice(0, -1);
    }
    return s6;
  }
  return this.lastNeed = 1, this.lastTotal = 2, this.lastChar[0] = t6[t6.length - 1], t6.toString("utf16le", e6, t6.length - 1);
}
function l5(t6) {
  var e6 = t6 && t6.length ? this.write(t6) : "";
  if (this.lastNeed) {
    var s6 = this.lastTotal - this.lastNeed;
    return e6 + this.lastChar.toString("utf16le", 0, s6);
  }
  return e6;
}
function u$14(t6, e6) {
  var s6 = (t6.length - e6) % 3;
  return 0 === s6 ? t6.toString("base64", e6) : (this.lastNeed = 3 - s6, this.lastTotal = 3, 1 === s6 ? this.lastChar[0] = t6[t6.length - 1] : (this.lastChar[0] = t6[t6.length - 2], this.lastChar[1] = t6[t6.length - 1]), t6.toString("base64", e6, t6.length - s6));
}
function o$14(t6) {
  var e6 = t6 && t6.length ? this.write(t6) : "";
  return this.lastNeed ? e6 + this.lastChar.toString("base64", 0, 3 - this.lastNeed) : e6;
}
function f$14(t6) {
  return t6.toString(this.encoding);
}
function c5(t6) {
  return t6 && t6.length ? this.write(t6) : "";
}
function dew$2$1() {
  if (_dewExec$2$1) return exports$2$1;
  _dewExec$2$1 = true;
  exports$2$1.byteLength = byteLength;
  exports$2$1.toByteArray = toByteArray;
  exports$2$1.fromByteArray = fromByteArray;
  var lookup = [];
  var revLookup = [];
  var Arr = typeof Uint8Array !== "undefined" ? Uint8Array : Array;
  var code = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
  for (var i6 = 0, len = code.length; i6 < len; ++i6) {
    lookup[i6] = code[i6];
    revLookup[code.charCodeAt(i6)] = i6;
  }
  revLookup["-".charCodeAt(0)] = 62;
  revLookup["_".charCodeAt(0)] = 63;
  function getLens(b64) {
    var len2 = b64.length;
    if (len2 % 4 > 0) {
      throw new Error("Invalid string. Length must be a multiple of 4");
    }
    var validLen = b64.indexOf("=");
    if (validLen === -1) validLen = len2;
    var placeHoldersLen = validLen === len2 ? 0 : 4 - validLen % 4;
    return [validLen, placeHoldersLen];
  }
  function byteLength(b64) {
    var lens = getLens(b64);
    var validLen = lens[0];
    var placeHoldersLen = lens[1];
    return (validLen + placeHoldersLen) * 3 / 4 - placeHoldersLen;
  }
  function _byteLength(b64, validLen, placeHoldersLen) {
    return (validLen + placeHoldersLen) * 3 / 4 - placeHoldersLen;
  }
  function toByteArray(b64) {
    var tmp;
    var lens = getLens(b64);
    var validLen = lens[0];
    var placeHoldersLen = lens[1];
    var arr = new Arr(_byteLength(b64, validLen, placeHoldersLen));
    var curByte = 0;
    var len2 = placeHoldersLen > 0 ? validLen - 4 : validLen;
    var i7;
    for (i7 = 0; i7 < len2; i7 += 4) {
      tmp = revLookup[b64.charCodeAt(i7)] << 18 | revLookup[b64.charCodeAt(i7 + 1)] << 12 | revLookup[b64.charCodeAt(i7 + 2)] << 6 | revLookup[b64.charCodeAt(i7 + 3)];
      arr[curByte++] = tmp >> 16 & 255;
      arr[curByte++] = tmp >> 8 & 255;
      arr[curByte++] = tmp & 255;
    }
    if (placeHoldersLen === 2) {
      tmp = revLookup[b64.charCodeAt(i7)] << 2 | revLookup[b64.charCodeAt(i7 + 1)] >> 4;
      arr[curByte++] = tmp & 255;
    }
    if (placeHoldersLen === 1) {
      tmp = revLookup[b64.charCodeAt(i7)] << 10 | revLookup[b64.charCodeAt(i7 + 1)] << 4 | revLookup[b64.charCodeAt(i7 + 2)] >> 2;
      arr[curByte++] = tmp >> 8 & 255;
      arr[curByte++] = tmp & 255;
    }
    return arr;
  }
  function tripletToBase64(num) {
    return lookup[num >> 18 & 63] + lookup[num >> 12 & 63] + lookup[num >> 6 & 63] + lookup[num & 63];
  }
  function encodeChunk(uint8, start, end) {
    var tmp;
    var output = [];
    for (var i7 = start; i7 < end; i7 += 3) {
      tmp = (uint8[i7] << 16 & 16711680) + (uint8[i7 + 1] << 8 & 65280) + (uint8[i7 + 2] & 255);
      output.push(tripletToBase64(tmp));
    }
    return output.join("");
  }
  function fromByteArray(uint8) {
    var tmp;
    var len2 = uint8.length;
    var extraBytes = len2 % 3;
    var parts = [];
    var maxChunkLength = 16383;
    for (var i7 = 0, len22 = len2 - extraBytes; i7 < len22; i7 += maxChunkLength) {
      parts.push(encodeChunk(uint8, i7, i7 + maxChunkLength > len22 ? len22 : i7 + maxChunkLength));
    }
    if (extraBytes === 1) {
      tmp = uint8[len2 - 1];
      parts.push(lookup[tmp >> 2] + lookup[tmp << 4 & 63] + "==");
    } else if (extraBytes === 2) {
      tmp = (uint8[len2 - 2] << 8) + uint8[len2 - 1];
      parts.push(lookup[tmp >> 10] + lookup[tmp >> 4 & 63] + lookup[tmp << 2 & 63] + "=");
    }
    return parts.join("");
  }
  return exports$2$1;
}
function dew$1$1() {
  if (_dewExec$1$1) return exports$1$1;
  _dewExec$1$1 = true;
  exports$1$1.read = function(buffer2, offset, isLE, mLen, nBytes) {
    var e6, m5;
    var eLen = nBytes * 8 - mLen - 1;
    var eMax = (1 << eLen) - 1;
    var eBias = eMax >> 1;
    var nBits = -7;
    var i6 = isLE ? nBytes - 1 : 0;
    var d5 = isLE ? -1 : 1;
    var s6 = buffer2[offset + i6];
    i6 += d5;
    e6 = s6 & (1 << -nBits) - 1;
    s6 >>= -nBits;
    nBits += eLen;
    for (; nBits > 0; e6 = e6 * 256 + buffer2[offset + i6], i6 += d5, nBits -= 8) {
    }
    m5 = e6 & (1 << -nBits) - 1;
    e6 >>= -nBits;
    nBits += mLen;
    for (; nBits > 0; m5 = m5 * 256 + buffer2[offset + i6], i6 += d5, nBits -= 8) {
    }
    if (e6 === 0) {
      e6 = 1 - eBias;
    } else if (e6 === eMax) {
      return m5 ? NaN : (s6 ? -1 : 1) * Infinity;
    } else {
      m5 = m5 + Math.pow(2, mLen);
      e6 = e6 - eBias;
    }
    return (s6 ? -1 : 1) * m5 * Math.pow(2, e6 - mLen);
  };
  exports$1$1.write = function(buffer2, value, offset, isLE, mLen, nBytes) {
    var e6, m5, c6;
    var eLen = nBytes * 8 - mLen - 1;
    var eMax = (1 << eLen) - 1;
    var eBias = eMax >> 1;
    var rt = mLen === 23 ? Math.pow(2, -24) - Math.pow(2, -77) : 0;
    var i6 = isLE ? 0 : nBytes - 1;
    var d5 = isLE ? 1 : -1;
    var s6 = value < 0 || value === 0 && 1 / value < 0 ? 1 : 0;
    value = Math.abs(value);
    if (isNaN(value) || value === Infinity) {
      m5 = isNaN(value) ? 1 : 0;
      e6 = eMax;
    } else {
      e6 = Math.floor(Math.log(value) / Math.LN2);
      if (value * (c6 = Math.pow(2, -e6)) < 1) {
        e6--;
        c6 *= 2;
      }
      if (e6 + eBias >= 1) {
        value += rt / c6;
      } else {
        value += rt * Math.pow(2, 1 - eBias);
      }
      if (value * c6 >= 2) {
        e6++;
        c6 /= 2;
      }
      if (e6 + eBias >= eMax) {
        m5 = 0;
        e6 = eMax;
      } else if (e6 + eBias >= 1) {
        m5 = (value * c6 - 1) * Math.pow(2, mLen);
        e6 = e6 + eBias;
      } else {
        m5 = value * Math.pow(2, eBias - 1) * Math.pow(2, mLen);
        e6 = 0;
      }
    }
    for (; mLen >= 8; buffer2[offset + i6] = m5 & 255, i6 += d5, m5 /= 256, mLen -= 8) {
    }
    e6 = e6 << mLen | m5;
    eLen += mLen;
    for (; eLen > 0; buffer2[offset + i6] = e6 & 255, i6 += d5, e6 /= 256, eLen -= 8) {
    }
    buffer2[offset + i6 - d5] |= s6 * 128;
  };
  return exports$1$1;
}
function dew$g() {
  if (_dewExec$g) return exports$g;
  _dewExec$g = true;
  const base64 = dew$2$1();
  const ieee754 = dew$1$1();
  const customInspectSymbol = typeof Symbol === "function" && typeof Symbol["for"] === "function" ? Symbol["for"]("nodejs.util.inspect.custom") : null;
  exports$g.Buffer = Buffer3;
  exports$g.SlowBuffer = SlowBuffer;
  exports$g.INSPECT_MAX_BYTES = 50;
  const K_MAX_LENGTH = 2147483647;
  exports$g.kMaxLength = K_MAX_LENGTH;
  Buffer3.TYPED_ARRAY_SUPPORT = typedArraySupport();
  if (!Buffer3.TYPED_ARRAY_SUPPORT && typeof console !== "undefined" && typeof console.error === "function") {
    console.error("This browser lacks typed array (Uint8Array) support which is required by `buffer` v5.x. Use `buffer` v4.x if you require old browser support.");
  }
  function typedArraySupport() {
    try {
      const arr = new Uint8Array(1);
      const proto = {
        foo: function() {
          return 42;
        }
      };
      Object.setPrototypeOf(proto, Uint8Array.prototype);
      Object.setPrototypeOf(arr, proto);
      return arr.foo() === 42;
    } catch (e6) {
      return false;
    }
  }
  Object.defineProperty(Buffer3.prototype, "parent", {
    enumerable: true,
    get: function() {
      if (!Buffer3.isBuffer(this)) return void 0;
      return this.buffer;
    }
  });
  Object.defineProperty(Buffer3.prototype, "offset", {
    enumerable: true,
    get: function() {
      if (!Buffer3.isBuffer(this)) return void 0;
      return this.byteOffset;
    }
  });
  function createBuffer(length) {
    if (length > K_MAX_LENGTH) {
      throw new RangeError('The value "' + length + '" is invalid for option "size"');
    }
    const buf = new Uint8Array(length);
    Object.setPrototypeOf(buf, Buffer3.prototype);
    return buf;
  }
  function Buffer3(arg, encodingOrOffset, length) {
    if (typeof arg === "number") {
      if (typeof encodingOrOffset === "string") {
        throw new TypeError('The "string" argument must be of type string. Received type number');
      }
      return allocUnsafe(arg);
    }
    return from(arg, encodingOrOffset, length);
  }
  Buffer3.poolSize = 8192;
  function from(value, encodingOrOffset, length) {
    if (typeof value === "string") {
      return fromString(value, encodingOrOffset);
    }
    if (ArrayBuffer.isView(value)) {
      return fromArrayView(value);
    }
    if (value == null) {
      throw new TypeError("The first argument must be one of type string, Buffer, ArrayBuffer, Array, or Array-like Object. Received type " + typeof value);
    }
    if (isInstance(value, ArrayBuffer) || value && isInstance(value.buffer, ArrayBuffer)) {
      return fromArrayBuffer(value, encodingOrOffset, length);
    }
    if (typeof SharedArrayBuffer !== "undefined" && (isInstance(value, SharedArrayBuffer) || value && isInstance(value.buffer, SharedArrayBuffer))) {
      return fromArrayBuffer(value, encodingOrOffset, length);
    }
    if (typeof value === "number") {
      throw new TypeError('The "value" argument must not be of type number. Received type number');
    }
    const valueOf = value.valueOf && value.valueOf();
    if (valueOf != null && valueOf !== value) {
      return Buffer3.from(valueOf, encodingOrOffset, length);
    }
    const b5 = fromObject(value);
    if (b5) return b5;
    if (typeof Symbol !== "undefined" && Symbol.toPrimitive != null && typeof value[Symbol.toPrimitive] === "function") {
      return Buffer3.from(value[Symbol.toPrimitive]("string"), encodingOrOffset, length);
    }
    throw new TypeError("The first argument must be one of type string, Buffer, ArrayBuffer, Array, or Array-like Object. Received type " + typeof value);
  }
  Buffer3.from = function(value, encodingOrOffset, length) {
    return from(value, encodingOrOffset, length);
  };
  Object.setPrototypeOf(Buffer3.prototype, Uint8Array.prototype);
  Object.setPrototypeOf(Buffer3, Uint8Array);
  function assertSize(size) {
    if (typeof size !== "number") {
      throw new TypeError('"size" argument must be of type number');
    } else if (size < 0) {
      throw new RangeError('The value "' + size + '" is invalid for option "size"');
    }
  }
  function alloc(size, fill, encoding) {
    assertSize(size);
    if (size <= 0) {
      return createBuffer(size);
    }
    if (fill !== void 0) {
      return typeof encoding === "string" ? createBuffer(size).fill(fill, encoding) : createBuffer(size).fill(fill);
    }
    return createBuffer(size);
  }
  Buffer3.alloc = function(size, fill, encoding) {
    return alloc(size, fill, encoding);
  };
  function allocUnsafe(size) {
    assertSize(size);
    return createBuffer(size < 0 ? 0 : checked(size) | 0);
  }
  Buffer3.allocUnsafe = function(size) {
    return allocUnsafe(size);
  };
  Buffer3.allocUnsafeSlow = function(size) {
    return allocUnsafe(size);
  };
  function fromString(string, encoding) {
    if (typeof encoding !== "string" || encoding === "") {
      encoding = "utf8";
    }
    if (!Buffer3.isEncoding(encoding)) {
      throw new TypeError("Unknown encoding: " + encoding);
    }
    const length = byteLength(string, encoding) | 0;
    let buf = createBuffer(length);
    const actual = buf.write(string, encoding);
    if (actual !== length) {
      buf = buf.slice(0, actual);
    }
    return buf;
  }
  function fromArrayLike(array) {
    const length = array.length < 0 ? 0 : checked(array.length) | 0;
    const buf = createBuffer(length);
    for (let i6 = 0; i6 < length; i6 += 1) {
      buf[i6] = array[i6] & 255;
    }
    return buf;
  }
  function fromArrayView(arrayView) {
    if (isInstance(arrayView, Uint8Array)) {
      const copy = new Uint8Array(arrayView);
      return fromArrayBuffer(copy.buffer, copy.byteOffset, copy.byteLength);
    }
    return fromArrayLike(arrayView);
  }
  function fromArrayBuffer(array, byteOffset, length) {
    if (byteOffset < 0 || array.byteLength < byteOffset) {
      throw new RangeError('"offset" is outside of buffer bounds');
    }
    if (array.byteLength < byteOffset + (length || 0)) {
      throw new RangeError('"length" is outside of buffer bounds');
    }
    let buf;
    if (byteOffset === void 0 && length === void 0) {
      buf = new Uint8Array(array);
    } else if (length === void 0) {
      buf = new Uint8Array(array, byteOffset);
    } else {
      buf = new Uint8Array(array, byteOffset, length);
    }
    Object.setPrototypeOf(buf, Buffer3.prototype);
    return buf;
  }
  function fromObject(obj) {
    if (Buffer3.isBuffer(obj)) {
      const len = checked(obj.length) | 0;
      const buf = createBuffer(len);
      if (buf.length === 0) {
        return buf;
      }
      obj.copy(buf, 0, 0, len);
      return buf;
    }
    if (obj.length !== void 0) {
      if (typeof obj.length !== "number" || numberIsNaN(obj.length)) {
        return createBuffer(0);
      }
      return fromArrayLike(obj);
    }
    if (obj.type === "Buffer" && Array.isArray(obj.data)) {
      return fromArrayLike(obj.data);
    }
  }
  function checked(length) {
    if (length >= K_MAX_LENGTH) {
      throw new RangeError("Attempt to allocate Buffer larger than maximum size: 0x" + K_MAX_LENGTH.toString(16) + " bytes");
    }
    return length | 0;
  }
  function SlowBuffer(length) {
    if (+length != length) {
      length = 0;
    }
    return Buffer3.alloc(+length);
  }
  Buffer3.isBuffer = function isBuffer(b5) {
    return b5 != null && b5._isBuffer === true && b5 !== Buffer3.prototype;
  };
  Buffer3.compare = function compare(a6, b5) {
    if (isInstance(a6, Uint8Array)) a6 = Buffer3.from(a6, a6.offset, a6.byteLength);
    if (isInstance(b5, Uint8Array)) b5 = Buffer3.from(b5, b5.offset, b5.byteLength);
    if (!Buffer3.isBuffer(a6) || !Buffer3.isBuffer(b5)) {
      throw new TypeError('The "buf1", "buf2" arguments must be one of type Buffer or Uint8Array');
    }
    if (a6 === b5) return 0;
    let x4 = a6.length;
    let y6 = b5.length;
    for (let i6 = 0, len = Math.min(x4, y6); i6 < len; ++i6) {
      if (a6[i6] !== b5[i6]) {
        x4 = a6[i6];
        y6 = b5[i6];
        break;
      }
    }
    if (x4 < y6) return -1;
    if (y6 < x4) return 1;
    return 0;
  };
  Buffer3.isEncoding = function isEncoding(encoding) {
    switch (String(encoding).toLowerCase()) {
      case "hex":
      case "utf8":
      case "utf-8":
      case "ascii":
      case "latin1":
      case "binary":
      case "base64":
      case "ucs2":
      case "ucs-2":
      case "utf16le":
      case "utf-16le":
        return true;
      default:
        return false;
    }
  };
  Buffer3.concat = function concat(list, length) {
    if (!Array.isArray(list)) {
      throw new TypeError('"list" argument must be an Array of Buffers');
    }
    if (list.length === 0) {
      return Buffer3.alloc(0);
    }
    let i6;
    if (length === void 0) {
      length = 0;
      for (i6 = 0; i6 < list.length; ++i6) {
        length += list[i6].length;
      }
    }
    const buffer2 = Buffer3.allocUnsafe(length);
    let pos = 0;
    for (i6 = 0; i6 < list.length; ++i6) {
      let buf = list[i6];
      if (isInstance(buf, Uint8Array)) {
        if (pos + buf.length > buffer2.length) {
          if (!Buffer3.isBuffer(buf)) buf = Buffer3.from(buf);
          buf.copy(buffer2, pos);
        } else {
          Uint8Array.prototype.set.call(buffer2, buf, pos);
        }
      } else if (!Buffer3.isBuffer(buf)) {
        throw new TypeError('"list" argument must be an Array of Buffers');
      } else {
        buf.copy(buffer2, pos);
      }
      pos += buf.length;
    }
    return buffer2;
  };
  function byteLength(string, encoding) {
    if (Buffer3.isBuffer(string)) {
      return string.length;
    }
    if (ArrayBuffer.isView(string) || isInstance(string, ArrayBuffer)) {
      return string.byteLength;
    }
    if (typeof string !== "string") {
      throw new TypeError('The "string" argument must be one of type string, Buffer, or ArrayBuffer. Received type ' + typeof string);
    }
    const len = string.length;
    const mustMatch = arguments.length > 2 && arguments[2] === true;
    if (!mustMatch && len === 0) return 0;
    let loweredCase = false;
    for (; ; ) {
      switch (encoding) {
        case "ascii":
        case "latin1":
        case "binary":
          return len;
        case "utf8":
        case "utf-8":
          return utf8ToBytes(string).length;
        case "ucs2":
        case "ucs-2":
        case "utf16le":
        case "utf-16le":
          return len * 2;
        case "hex":
          return len >>> 1;
        case "base64":
          return base64ToBytes(string).length;
        default:
          if (loweredCase) {
            return mustMatch ? -1 : utf8ToBytes(string).length;
          }
          encoding = ("" + encoding).toLowerCase();
          loweredCase = true;
      }
    }
  }
  Buffer3.byteLength = byteLength;
  function slowToString(encoding, start, end) {
    let loweredCase = false;
    if (start === void 0 || start < 0) {
      start = 0;
    }
    if (start > this.length) {
      return "";
    }
    if (end === void 0 || end > this.length) {
      end = this.length;
    }
    if (end <= 0) {
      return "";
    }
    end >>>= 0;
    start >>>= 0;
    if (end <= start) {
      return "";
    }
    if (!encoding) encoding = "utf8";
    while (true) {
      switch (encoding) {
        case "hex":
          return hexSlice(this, start, end);
        case "utf8":
        case "utf-8":
          return utf8Slice(this, start, end);
        case "ascii":
          return asciiSlice(this, start, end);
        case "latin1":
        case "binary":
          return latin1Slice(this, start, end);
        case "base64":
          return base64Slice(this, start, end);
        case "ucs2":
        case "ucs-2":
        case "utf16le":
        case "utf-16le":
          return utf16leSlice(this, start, end);
        default:
          if (loweredCase) throw new TypeError("Unknown encoding: " + encoding);
          encoding = (encoding + "").toLowerCase();
          loweredCase = true;
      }
    }
  }
  Buffer3.prototype._isBuffer = true;
  function swap(b5, n6, m5) {
    const i6 = b5[n6];
    b5[n6] = b5[m5];
    b5[m5] = i6;
  }
  Buffer3.prototype.swap16 = function swap16() {
    const len = this.length;
    if (len % 2 !== 0) {
      throw new RangeError("Buffer size must be a multiple of 16-bits");
    }
    for (let i6 = 0; i6 < len; i6 += 2) {
      swap(this, i6, i6 + 1);
    }
    return this;
  };
  Buffer3.prototype.swap32 = function swap32() {
    const len = this.length;
    if (len % 4 !== 0) {
      throw new RangeError("Buffer size must be a multiple of 32-bits");
    }
    for (let i6 = 0; i6 < len; i6 += 4) {
      swap(this, i6, i6 + 3);
      swap(this, i6 + 1, i6 + 2);
    }
    return this;
  };
  Buffer3.prototype.swap64 = function swap64() {
    const len = this.length;
    if (len % 8 !== 0) {
      throw new RangeError("Buffer size must be a multiple of 64-bits");
    }
    for (let i6 = 0; i6 < len; i6 += 8) {
      swap(this, i6, i6 + 7);
      swap(this, i6 + 1, i6 + 6);
      swap(this, i6 + 2, i6 + 5);
      swap(this, i6 + 3, i6 + 4);
    }
    return this;
  };
  Buffer3.prototype.toString = function toString() {
    const length = this.length;
    if (length === 0) return "";
    if (arguments.length === 0) return utf8Slice(this, 0, length);
    return slowToString.apply(this, arguments);
  };
  Buffer3.prototype.toLocaleString = Buffer3.prototype.toString;
  Buffer3.prototype.equals = function equals(b5) {
    if (!Buffer3.isBuffer(b5)) throw new TypeError("Argument must be a Buffer");
    if (this === b5) return true;
    return Buffer3.compare(this, b5) === 0;
  };
  Buffer3.prototype.inspect = function inspect() {
    let str = "";
    const max = exports$g.INSPECT_MAX_BYTES;
    str = this.toString("hex", 0, max).replace(/(.{2})/g, "$1 ").trim();
    if (this.length > max) str += " ... ";
    return "<Buffer " + str + ">";
  };
  if (customInspectSymbol) {
    Buffer3.prototype[customInspectSymbol] = Buffer3.prototype.inspect;
  }
  Buffer3.prototype.compare = function compare(target, start, end, thisStart, thisEnd) {
    if (isInstance(target, Uint8Array)) {
      target = Buffer3.from(target, target.offset, target.byteLength);
    }
    if (!Buffer3.isBuffer(target)) {
      throw new TypeError('The "target" argument must be one of type Buffer or Uint8Array. Received type ' + typeof target);
    }
    if (start === void 0) {
      start = 0;
    }
    if (end === void 0) {
      end = target ? target.length : 0;
    }
    if (thisStart === void 0) {
      thisStart = 0;
    }
    if (thisEnd === void 0) {
      thisEnd = this.length;
    }
    if (start < 0 || end > target.length || thisStart < 0 || thisEnd > this.length) {
      throw new RangeError("out of range index");
    }
    if (thisStart >= thisEnd && start >= end) {
      return 0;
    }
    if (thisStart >= thisEnd) {
      return -1;
    }
    if (start >= end) {
      return 1;
    }
    start >>>= 0;
    end >>>= 0;
    thisStart >>>= 0;
    thisEnd >>>= 0;
    if (this === target) return 0;
    let x4 = thisEnd - thisStart;
    let y6 = end - start;
    const len = Math.min(x4, y6);
    const thisCopy = this.slice(thisStart, thisEnd);
    const targetCopy = target.slice(start, end);
    for (let i6 = 0; i6 < len; ++i6) {
      if (thisCopy[i6] !== targetCopy[i6]) {
        x4 = thisCopy[i6];
        y6 = targetCopy[i6];
        break;
      }
    }
    if (x4 < y6) return -1;
    if (y6 < x4) return 1;
    return 0;
  };
  function bidirectionalIndexOf(buffer2, val, byteOffset, encoding, dir) {
    if (buffer2.length === 0) return -1;
    if (typeof byteOffset === "string") {
      encoding = byteOffset;
      byteOffset = 0;
    } else if (byteOffset > 2147483647) {
      byteOffset = 2147483647;
    } else if (byteOffset < -2147483648) {
      byteOffset = -2147483648;
    }
    byteOffset = +byteOffset;
    if (numberIsNaN(byteOffset)) {
      byteOffset = dir ? 0 : buffer2.length - 1;
    }
    if (byteOffset < 0) byteOffset = buffer2.length + byteOffset;
    if (byteOffset >= buffer2.length) {
      if (dir) return -1;
      else byteOffset = buffer2.length - 1;
    } else if (byteOffset < 0) {
      if (dir) byteOffset = 0;
      else return -1;
    }
    if (typeof val === "string") {
      val = Buffer3.from(val, encoding);
    }
    if (Buffer3.isBuffer(val)) {
      if (val.length === 0) {
        return -1;
      }
      return arrayIndexOf(buffer2, val, byteOffset, encoding, dir);
    } else if (typeof val === "number") {
      val = val & 255;
      if (typeof Uint8Array.prototype.indexOf === "function") {
        if (dir) {
          return Uint8Array.prototype.indexOf.call(buffer2, val, byteOffset);
        } else {
          return Uint8Array.prototype.lastIndexOf.call(buffer2, val, byteOffset);
        }
      }
      return arrayIndexOf(buffer2, [val], byteOffset, encoding, dir);
    }
    throw new TypeError("val must be string, number or Buffer");
  }
  function arrayIndexOf(arr, val, byteOffset, encoding, dir) {
    let indexSize = 1;
    let arrLength = arr.length;
    let valLength = val.length;
    if (encoding !== void 0) {
      encoding = String(encoding).toLowerCase();
      if (encoding === "ucs2" || encoding === "ucs-2" || encoding === "utf16le" || encoding === "utf-16le") {
        if (arr.length < 2 || val.length < 2) {
          return -1;
        }
        indexSize = 2;
        arrLength /= 2;
        valLength /= 2;
        byteOffset /= 2;
      }
    }
    function read2(buf, i7) {
      if (indexSize === 1) {
        return buf[i7];
      } else {
        return buf.readUInt16BE(i7 * indexSize);
      }
    }
    let i6;
    if (dir) {
      let foundIndex = -1;
      for (i6 = byteOffset; i6 < arrLength; i6++) {
        if (read2(arr, i6) === read2(val, foundIndex === -1 ? 0 : i6 - foundIndex)) {
          if (foundIndex === -1) foundIndex = i6;
          if (i6 - foundIndex + 1 === valLength) return foundIndex * indexSize;
        } else {
          if (foundIndex !== -1) i6 -= i6 - foundIndex;
          foundIndex = -1;
        }
      }
    } else {
      if (byteOffset + valLength > arrLength) byteOffset = arrLength - valLength;
      for (i6 = byteOffset; i6 >= 0; i6--) {
        let found = true;
        for (let j4 = 0; j4 < valLength; j4++) {
          if (read2(arr, i6 + j4) !== read2(val, j4)) {
            found = false;
            break;
          }
        }
        if (found) return i6;
      }
    }
    return -1;
  }
  Buffer3.prototype.includes = function includes(val, byteOffset, encoding) {
    return this.indexOf(val, byteOffset, encoding) !== -1;
  };
  Buffer3.prototype.indexOf = function indexOf(val, byteOffset, encoding) {
    return bidirectionalIndexOf(this, val, byteOffset, encoding, true);
  };
  Buffer3.prototype.lastIndexOf = function lastIndexOf(val, byteOffset, encoding) {
    return bidirectionalIndexOf(this, val, byteOffset, encoding, false);
  };
  function hexWrite(buf, string, offset, length) {
    offset = Number(offset) || 0;
    const remaining = buf.length - offset;
    if (!length) {
      length = remaining;
    } else {
      length = Number(length);
      if (length > remaining) {
        length = remaining;
      }
    }
    const strLen = string.length;
    if (length > strLen / 2) {
      length = strLen / 2;
    }
    let i6;
    for (i6 = 0; i6 < length; ++i6) {
      const parsed = parseInt(string.substr(i6 * 2, 2), 16);
      if (numberIsNaN(parsed)) return i6;
      buf[offset + i6] = parsed;
    }
    return i6;
  }
  function utf8Write(buf, string, offset, length) {
    return blitBuffer(utf8ToBytes(string, buf.length - offset), buf, offset, length);
  }
  function asciiWrite(buf, string, offset, length) {
    return blitBuffer(asciiToBytes(string), buf, offset, length);
  }
  function base64Write(buf, string, offset, length) {
    return blitBuffer(base64ToBytes(string), buf, offset, length);
  }
  function ucs2Write(buf, string, offset, length) {
    return blitBuffer(utf16leToBytes(string, buf.length - offset), buf, offset, length);
  }
  Buffer3.prototype.write = function write2(string, offset, length, encoding) {
    if (offset === void 0) {
      encoding = "utf8";
      length = this.length;
      offset = 0;
    } else if (length === void 0 && typeof offset === "string") {
      encoding = offset;
      length = this.length;
      offset = 0;
    } else if (isFinite(offset)) {
      offset = offset >>> 0;
      if (isFinite(length)) {
        length = length >>> 0;
        if (encoding === void 0) encoding = "utf8";
      } else {
        encoding = length;
        length = void 0;
      }
    } else {
      throw new Error("Buffer.write(string, encoding, offset[, length]) is no longer supported");
    }
    const remaining = this.length - offset;
    if (length === void 0 || length > remaining) length = remaining;
    if (string.length > 0 && (length < 0 || offset < 0) || offset > this.length) {
      throw new RangeError("Attempt to write outside buffer bounds");
    }
    if (!encoding) encoding = "utf8";
    let loweredCase = false;
    for (; ; ) {
      switch (encoding) {
        case "hex":
          return hexWrite(this, string, offset, length);
        case "utf8":
        case "utf-8":
          return utf8Write(this, string, offset, length);
        case "ascii":
        case "latin1":
        case "binary":
          return asciiWrite(this, string, offset, length);
        case "base64":
          return base64Write(this, string, offset, length);
        case "ucs2":
        case "ucs-2":
        case "utf16le":
        case "utf-16le":
          return ucs2Write(this, string, offset, length);
        default:
          if (loweredCase) throw new TypeError("Unknown encoding: " + encoding);
          encoding = ("" + encoding).toLowerCase();
          loweredCase = true;
      }
    }
  };
  Buffer3.prototype.toJSON = function toJSON() {
    return {
      type: "Buffer",
      data: Array.prototype.slice.call(this._arr || this, 0)
    };
  };
  function base64Slice(buf, start, end) {
    if (start === 0 && end === buf.length) {
      return base64.fromByteArray(buf);
    } else {
      return base64.fromByteArray(buf.slice(start, end));
    }
  }
  function utf8Slice(buf, start, end) {
    end = Math.min(buf.length, end);
    const res = [];
    let i6 = start;
    while (i6 < end) {
      const firstByte = buf[i6];
      let codePoint = null;
      let bytesPerSequence = firstByte > 239 ? 4 : firstByte > 223 ? 3 : firstByte > 191 ? 2 : 1;
      if (i6 + bytesPerSequence <= end) {
        let secondByte, thirdByte, fourthByte, tempCodePoint;
        switch (bytesPerSequence) {
          case 1:
            if (firstByte < 128) {
              codePoint = firstByte;
            }
            break;
          case 2:
            secondByte = buf[i6 + 1];
            if ((secondByte & 192) === 128) {
              tempCodePoint = (firstByte & 31) << 6 | secondByte & 63;
              if (tempCodePoint > 127) {
                codePoint = tempCodePoint;
              }
            }
            break;
          case 3:
            secondByte = buf[i6 + 1];
            thirdByte = buf[i6 + 2];
            if ((secondByte & 192) === 128 && (thirdByte & 192) === 128) {
              tempCodePoint = (firstByte & 15) << 12 | (secondByte & 63) << 6 | thirdByte & 63;
              if (tempCodePoint > 2047 && (tempCodePoint < 55296 || tempCodePoint > 57343)) {
                codePoint = tempCodePoint;
              }
            }
            break;
          case 4:
            secondByte = buf[i6 + 1];
            thirdByte = buf[i6 + 2];
            fourthByte = buf[i6 + 3];
            if ((secondByte & 192) === 128 && (thirdByte & 192) === 128 && (fourthByte & 192) === 128) {
              tempCodePoint = (firstByte & 15) << 18 | (secondByte & 63) << 12 | (thirdByte & 63) << 6 | fourthByte & 63;
              if (tempCodePoint > 65535 && tempCodePoint < 1114112) {
                codePoint = tempCodePoint;
              }
            }
        }
      }
      if (codePoint === null) {
        codePoint = 65533;
        bytesPerSequence = 1;
      } else if (codePoint > 65535) {
        codePoint -= 65536;
        res.push(codePoint >>> 10 & 1023 | 55296);
        codePoint = 56320 | codePoint & 1023;
      }
      res.push(codePoint);
      i6 += bytesPerSequence;
    }
    return decodeCodePointsArray(res);
  }
  const MAX_ARGUMENTS_LENGTH = 4096;
  function decodeCodePointsArray(codePoints) {
    const len = codePoints.length;
    if (len <= MAX_ARGUMENTS_LENGTH) {
      return String.fromCharCode.apply(String, codePoints);
    }
    let res = "";
    let i6 = 0;
    while (i6 < len) {
      res += String.fromCharCode.apply(String, codePoints.slice(i6, i6 += MAX_ARGUMENTS_LENGTH));
    }
    return res;
  }
  function asciiSlice(buf, start, end) {
    let ret = "";
    end = Math.min(buf.length, end);
    for (let i6 = start; i6 < end; ++i6) {
      ret += String.fromCharCode(buf[i6] & 127);
    }
    return ret;
  }
  function latin1Slice(buf, start, end) {
    let ret = "";
    end = Math.min(buf.length, end);
    for (let i6 = start; i6 < end; ++i6) {
      ret += String.fromCharCode(buf[i6]);
    }
    return ret;
  }
  function hexSlice(buf, start, end) {
    const len = buf.length;
    if (!start || start < 0) start = 0;
    if (!end || end < 0 || end > len) end = len;
    let out = "";
    for (let i6 = start; i6 < end; ++i6) {
      out += hexSliceLookupTable[buf[i6]];
    }
    return out;
  }
  function utf16leSlice(buf, start, end) {
    const bytes = buf.slice(start, end);
    let res = "";
    for (let i6 = 0; i6 < bytes.length - 1; i6 += 2) {
      res += String.fromCharCode(bytes[i6] + bytes[i6 + 1] * 256);
    }
    return res;
  }
  Buffer3.prototype.slice = function slice(start, end) {
    const len = this.length;
    start = ~~start;
    end = end === void 0 ? len : ~~end;
    if (start < 0) {
      start += len;
      if (start < 0) start = 0;
    } else if (start > len) {
      start = len;
    }
    if (end < 0) {
      end += len;
      if (end < 0) end = 0;
    } else if (end > len) {
      end = len;
    }
    if (end < start) end = start;
    const newBuf = this.subarray(start, end);
    Object.setPrototypeOf(newBuf, Buffer3.prototype);
    return newBuf;
  };
  function checkOffset(offset, ext, length) {
    if (offset % 1 !== 0 || offset < 0) throw new RangeError("offset is not uint");
    if (offset + ext > length) throw new RangeError("Trying to access beyond buffer length");
  }
  Buffer3.prototype.readUintLE = Buffer3.prototype.readUIntLE = function readUIntLE(offset, byteLength2, noAssert) {
    offset = offset >>> 0;
    byteLength2 = byteLength2 >>> 0;
    if (!noAssert) checkOffset(offset, byteLength2, this.length);
    let val = this[offset];
    let mul = 1;
    let i6 = 0;
    while (++i6 < byteLength2 && (mul *= 256)) {
      val += this[offset + i6] * mul;
    }
    return val;
  };
  Buffer3.prototype.readUintBE = Buffer3.prototype.readUIntBE = function readUIntBE(offset, byteLength2, noAssert) {
    offset = offset >>> 0;
    byteLength2 = byteLength2 >>> 0;
    if (!noAssert) {
      checkOffset(offset, byteLength2, this.length);
    }
    let val = this[offset + --byteLength2];
    let mul = 1;
    while (byteLength2 > 0 && (mul *= 256)) {
      val += this[offset + --byteLength2] * mul;
    }
    return val;
  };
  Buffer3.prototype.readUint8 = Buffer3.prototype.readUInt8 = function readUInt8(offset, noAssert) {
    offset = offset >>> 0;
    if (!noAssert) checkOffset(offset, 1, this.length);
    return this[offset];
  };
  Buffer3.prototype.readUint16LE = Buffer3.prototype.readUInt16LE = function readUInt16LE(offset, noAssert) {
    offset = offset >>> 0;
    if (!noAssert) checkOffset(offset, 2, this.length);
    return this[offset] | this[offset + 1] << 8;
  };
  Buffer3.prototype.readUint16BE = Buffer3.prototype.readUInt16BE = function readUInt16BE(offset, noAssert) {
    offset = offset >>> 0;
    if (!noAssert) checkOffset(offset, 2, this.length);
    return this[offset] << 8 | this[offset + 1];
  };
  Buffer3.prototype.readUint32LE = Buffer3.prototype.readUInt32LE = function readUInt32LE(offset, noAssert) {
    offset = offset >>> 0;
    if (!noAssert) checkOffset(offset, 4, this.length);
    return (this[offset] | this[offset + 1] << 8 | this[offset + 2] << 16) + this[offset + 3] * 16777216;
  };
  Buffer3.prototype.readUint32BE = Buffer3.prototype.readUInt32BE = function readUInt32BE(offset, noAssert) {
    offset = offset >>> 0;
    if (!noAssert) checkOffset(offset, 4, this.length);
    return this[offset] * 16777216 + (this[offset + 1] << 16 | this[offset + 2] << 8 | this[offset + 3]);
  };
  Buffer3.prototype.readBigUInt64LE = defineBigIntMethod(function readBigUInt64LE(offset) {
    offset = offset >>> 0;
    validateNumber(offset, "offset");
    const first = this[offset];
    const last = this[offset + 7];
    if (first === void 0 || last === void 0) {
      boundsError(offset, this.length - 8);
    }
    const lo = first + this[++offset] * 2 ** 8 + this[++offset] * 2 ** 16 + this[++offset] * 2 ** 24;
    const hi = this[++offset] + this[++offset] * 2 ** 8 + this[++offset] * 2 ** 16 + last * 2 ** 24;
    return BigInt(lo) + (BigInt(hi) << BigInt(32));
  });
  Buffer3.prototype.readBigUInt64BE = defineBigIntMethod(function readBigUInt64BE(offset) {
    offset = offset >>> 0;
    validateNumber(offset, "offset");
    const first = this[offset];
    const last = this[offset + 7];
    if (first === void 0 || last === void 0) {
      boundsError(offset, this.length - 8);
    }
    const hi = first * 2 ** 24 + this[++offset] * 2 ** 16 + this[++offset] * 2 ** 8 + this[++offset];
    const lo = this[++offset] * 2 ** 24 + this[++offset] * 2 ** 16 + this[++offset] * 2 ** 8 + last;
    return (BigInt(hi) << BigInt(32)) + BigInt(lo);
  });
  Buffer3.prototype.readIntLE = function readIntLE(offset, byteLength2, noAssert) {
    offset = offset >>> 0;
    byteLength2 = byteLength2 >>> 0;
    if (!noAssert) checkOffset(offset, byteLength2, this.length);
    let val = this[offset];
    let mul = 1;
    let i6 = 0;
    while (++i6 < byteLength2 && (mul *= 256)) {
      val += this[offset + i6] * mul;
    }
    mul *= 128;
    if (val >= mul) val -= Math.pow(2, 8 * byteLength2);
    return val;
  };
  Buffer3.prototype.readIntBE = function readIntBE(offset, byteLength2, noAssert) {
    offset = offset >>> 0;
    byteLength2 = byteLength2 >>> 0;
    if (!noAssert) checkOffset(offset, byteLength2, this.length);
    let i6 = byteLength2;
    let mul = 1;
    let val = this[offset + --i6];
    while (i6 > 0 && (mul *= 256)) {
      val += this[offset + --i6] * mul;
    }
    mul *= 128;
    if (val >= mul) val -= Math.pow(2, 8 * byteLength2);
    return val;
  };
  Buffer3.prototype.readInt8 = function readInt8(offset, noAssert) {
    offset = offset >>> 0;
    if (!noAssert) checkOffset(offset, 1, this.length);
    if (!(this[offset] & 128)) return this[offset];
    return (255 - this[offset] + 1) * -1;
  };
  Buffer3.prototype.readInt16LE = function readInt16LE(offset, noAssert) {
    offset = offset >>> 0;
    if (!noAssert) checkOffset(offset, 2, this.length);
    const val = this[offset] | this[offset + 1] << 8;
    return val & 32768 ? val | 4294901760 : val;
  };
  Buffer3.prototype.readInt16BE = function readInt16BE(offset, noAssert) {
    offset = offset >>> 0;
    if (!noAssert) checkOffset(offset, 2, this.length);
    const val = this[offset + 1] | this[offset] << 8;
    return val & 32768 ? val | 4294901760 : val;
  };
  Buffer3.prototype.readInt32LE = function readInt32LE(offset, noAssert) {
    offset = offset >>> 0;
    if (!noAssert) checkOffset(offset, 4, this.length);
    return this[offset] | this[offset + 1] << 8 | this[offset + 2] << 16 | this[offset + 3] << 24;
  };
  Buffer3.prototype.readInt32BE = function readInt32BE(offset, noAssert) {
    offset = offset >>> 0;
    if (!noAssert) checkOffset(offset, 4, this.length);
    return this[offset] << 24 | this[offset + 1] << 16 | this[offset + 2] << 8 | this[offset + 3];
  };
  Buffer3.prototype.readBigInt64LE = defineBigIntMethod(function readBigInt64LE(offset) {
    offset = offset >>> 0;
    validateNumber(offset, "offset");
    const first = this[offset];
    const last = this[offset + 7];
    if (first === void 0 || last === void 0) {
      boundsError(offset, this.length - 8);
    }
    const val = this[offset + 4] + this[offset + 5] * 2 ** 8 + this[offset + 6] * 2 ** 16 + (last << 24);
    return (BigInt(val) << BigInt(32)) + BigInt(first + this[++offset] * 2 ** 8 + this[++offset] * 2 ** 16 + this[++offset] * 2 ** 24);
  });
  Buffer3.prototype.readBigInt64BE = defineBigIntMethod(function readBigInt64BE(offset) {
    offset = offset >>> 0;
    validateNumber(offset, "offset");
    const first = this[offset];
    const last = this[offset + 7];
    if (first === void 0 || last === void 0) {
      boundsError(offset, this.length - 8);
    }
    const val = (first << 24) + // Overflow
    this[++offset] * 2 ** 16 + this[++offset] * 2 ** 8 + this[++offset];
    return (BigInt(val) << BigInt(32)) + BigInt(this[++offset] * 2 ** 24 + this[++offset] * 2 ** 16 + this[++offset] * 2 ** 8 + last);
  });
  Buffer3.prototype.readFloatLE = function readFloatLE(offset, noAssert) {
    offset = offset >>> 0;
    if (!noAssert) checkOffset(offset, 4, this.length);
    return ieee754.read(this, offset, true, 23, 4);
  };
  Buffer3.prototype.readFloatBE = function readFloatBE(offset, noAssert) {
    offset = offset >>> 0;
    if (!noAssert) checkOffset(offset, 4, this.length);
    return ieee754.read(this, offset, false, 23, 4);
  };
  Buffer3.prototype.readDoubleLE = function readDoubleLE(offset, noAssert) {
    offset = offset >>> 0;
    if (!noAssert) checkOffset(offset, 8, this.length);
    return ieee754.read(this, offset, true, 52, 8);
  };
  Buffer3.prototype.readDoubleBE = function readDoubleBE(offset, noAssert) {
    offset = offset >>> 0;
    if (!noAssert) checkOffset(offset, 8, this.length);
    return ieee754.read(this, offset, false, 52, 8);
  };
  function checkInt(buf, value, offset, ext, max, min) {
    if (!Buffer3.isBuffer(buf)) throw new TypeError('"buffer" argument must be a Buffer instance');
    if (value > max || value < min) throw new RangeError('"value" argument is out of bounds');
    if (offset + ext > buf.length) throw new RangeError("Index out of range");
  }
  Buffer3.prototype.writeUintLE = Buffer3.prototype.writeUIntLE = function writeUIntLE(value, offset, byteLength2, noAssert) {
    value = +value;
    offset = offset >>> 0;
    byteLength2 = byteLength2 >>> 0;
    if (!noAssert) {
      const maxBytes = Math.pow(2, 8 * byteLength2) - 1;
      checkInt(this, value, offset, byteLength2, maxBytes, 0);
    }
    let mul = 1;
    let i6 = 0;
    this[offset] = value & 255;
    while (++i6 < byteLength2 && (mul *= 256)) {
      this[offset + i6] = value / mul & 255;
    }
    return offset + byteLength2;
  };
  Buffer3.prototype.writeUintBE = Buffer3.prototype.writeUIntBE = function writeUIntBE(value, offset, byteLength2, noAssert) {
    value = +value;
    offset = offset >>> 0;
    byteLength2 = byteLength2 >>> 0;
    if (!noAssert) {
      const maxBytes = Math.pow(2, 8 * byteLength2) - 1;
      checkInt(this, value, offset, byteLength2, maxBytes, 0);
    }
    let i6 = byteLength2 - 1;
    let mul = 1;
    this[offset + i6] = value & 255;
    while (--i6 >= 0 && (mul *= 256)) {
      this[offset + i6] = value / mul & 255;
    }
    return offset + byteLength2;
  };
  Buffer3.prototype.writeUint8 = Buffer3.prototype.writeUInt8 = function writeUInt8(value, offset, noAssert) {
    value = +value;
    offset = offset >>> 0;
    if (!noAssert) checkInt(this, value, offset, 1, 255, 0);
    this[offset] = value & 255;
    return offset + 1;
  };
  Buffer3.prototype.writeUint16LE = Buffer3.prototype.writeUInt16LE = function writeUInt16LE(value, offset, noAssert) {
    value = +value;
    offset = offset >>> 0;
    if (!noAssert) checkInt(this, value, offset, 2, 65535, 0);
    this[offset] = value & 255;
    this[offset + 1] = value >>> 8;
    return offset + 2;
  };
  Buffer3.prototype.writeUint16BE = Buffer3.prototype.writeUInt16BE = function writeUInt16BE(value, offset, noAssert) {
    value = +value;
    offset = offset >>> 0;
    if (!noAssert) checkInt(this, value, offset, 2, 65535, 0);
    this[offset] = value >>> 8;
    this[offset + 1] = value & 255;
    return offset + 2;
  };
  Buffer3.prototype.writeUint32LE = Buffer3.prototype.writeUInt32LE = function writeUInt32LE(value, offset, noAssert) {
    value = +value;
    offset = offset >>> 0;
    if (!noAssert) checkInt(this, value, offset, 4, 4294967295, 0);
    this[offset + 3] = value >>> 24;
    this[offset + 2] = value >>> 16;
    this[offset + 1] = value >>> 8;
    this[offset] = value & 255;
    return offset + 4;
  };
  Buffer3.prototype.writeUint32BE = Buffer3.prototype.writeUInt32BE = function writeUInt32BE(value, offset, noAssert) {
    value = +value;
    offset = offset >>> 0;
    if (!noAssert) checkInt(this, value, offset, 4, 4294967295, 0);
    this[offset] = value >>> 24;
    this[offset + 1] = value >>> 16;
    this[offset + 2] = value >>> 8;
    this[offset + 3] = value & 255;
    return offset + 4;
  };
  function wrtBigUInt64LE(buf, value, offset, min, max) {
    checkIntBI(value, min, max, buf, offset, 7);
    let lo = Number(value & BigInt(4294967295));
    buf[offset++] = lo;
    lo = lo >> 8;
    buf[offset++] = lo;
    lo = lo >> 8;
    buf[offset++] = lo;
    lo = lo >> 8;
    buf[offset++] = lo;
    let hi = Number(value >> BigInt(32) & BigInt(4294967295));
    buf[offset++] = hi;
    hi = hi >> 8;
    buf[offset++] = hi;
    hi = hi >> 8;
    buf[offset++] = hi;
    hi = hi >> 8;
    buf[offset++] = hi;
    return offset;
  }
  function wrtBigUInt64BE(buf, value, offset, min, max) {
    checkIntBI(value, min, max, buf, offset, 7);
    let lo = Number(value & BigInt(4294967295));
    buf[offset + 7] = lo;
    lo = lo >> 8;
    buf[offset + 6] = lo;
    lo = lo >> 8;
    buf[offset + 5] = lo;
    lo = lo >> 8;
    buf[offset + 4] = lo;
    let hi = Number(value >> BigInt(32) & BigInt(4294967295));
    buf[offset + 3] = hi;
    hi = hi >> 8;
    buf[offset + 2] = hi;
    hi = hi >> 8;
    buf[offset + 1] = hi;
    hi = hi >> 8;
    buf[offset] = hi;
    return offset + 8;
  }
  Buffer3.prototype.writeBigUInt64LE = defineBigIntMethod(function writeBigUInt64LE(value, offset = 0) {
    return wrtBigUInt64LE(this, value, offset, BigInt(0), BigInt("0xffffffffffffffff"));
  });
  Buffer3.prototype.writeBigUInt64BE = defineBigIntMethod(function writeBigUInt64BE(value, offset = 0) {
    return wrtBigUInt64BE(this, value, offset, BigInt(0), BigInt("0xffffffffffffffff"));
  });
  Buffer3.prototype.writeIntLE = function writeIntLE(value, offset, byteLength2, noAssert) {
    value = +value;
    offset = offset >>> 0;
    if (!noAssert) {
      const limit = Math.pow(2, 8 * byteLength2 - 1);
      checkInt(this, value, offset, byteLength2, limit - 1, -limit);
    }
    let i6 = 0;
    let mul = 1;
    let sub = 0;
    this[offset] = value & 255;
    while (++i6 < byteLength2 && (mul *= 256)) {
      if (value < 0 && sub === 0 && this[offset + i6 - 1] !== 0) {
        sub = 1;
      }
      this[offset + i6] = (value / mul >> 0) - sub & 255;
    }
    return offset + byteLength2;
  };
  Buffer3.prototype.writeIntBE = function writeIntBE(value, offset, byteLength2, noAssert) {
    value = +value;
    offset = offset >>> 0;
    if (!noAssert) {
      const limit = Math.pow(2, 8 * byteLength2 - 1);
      checkInt(this, value, offset, byteLength2, limit - 1, -limit);
    }
    let i6 = byteLength2 - 1;
    let mul = 1;
    let sub = 0;
    this[offset + i6] = value & 255;
    while (--i6 >= 0 && (mul *= 256)) {
      if (value < 0 && sub === 0 && this[offset + i6 + 1] !== 0) {
        sub = 1;
      }
      this[offset + i6] = (value / mul >> 0) - sub & 255;
    }
    return offset + byteLength2;
  };
  Buffer3.prototype.writeInt8 = function writeInt8(value, offset, noAssert) {
    value = +value;
    offset = offset >>> 0;
    if (!noAssert) checkInt(this, value, offset, 1, 127, -128);
    if (value < 0) value = 255 + value + 1;
    this[offset] = value & 255;
    return offset + 1;
  };
  Buffer3.prototype.writeInt16LE = function writeInt16LE(value, offset, noAssert) {
    value = +value;
    offset = offset >>> 0;
    if (!noAssert) checkInt(this, value, offset, 2, 32767, -32768);
    this[offset] = value & 255;
    this[offset + 1] = value >>> 8;
    return offset + 2;
  };
  Buffer3.prototype.writeInt16BE = function writeInt16BE(value, offset, noAssert) {
    value = +value;
    offset = offset >>> 0;
    if (!noAssert) checkInt(this, value, offset, 2, 32767, -32768);
    this[offset] = value >>> 8;
    this[offset + 1] = value & 255;
    return offset + 2;
  };
  Buffer3.prototype.writeInt32LE = function writeInt32LE(value, offset, noAssert) {
    value = +value;
    offset = offset >>> 0;
    if (!noAssert) checkInt(this, value, offset, 4, 2147483647, -2147483648);
    this[offset] = value & 255;
    this[offset + 1] = value >>> 8;
    this[offset + 2] = value >>> 16;
    this[offset + 3] = value >>> 24;
    return offset + 4;
  };
  Buffer3.prototype.writeInt32BE = function writeInt32BE(value, offset, noAssert) {
    value = +value;
    offset = offset >>> 0;
    if (!noAssert) checkInt(this, value, offset, 4, 2147483647, -2147483648);
    if (value < 0) value = 4294967295 + value + 1;
    this[offset] = value >>> 24;
    this[offset + 1] = value >>> 16;
    this[offset + 2] = value >>> 8;
    this[offset + 3] = value & 255;
    return offset + 4;
  };
  Buffer3.prototype.writeBigInt64LE = defineBigIntMethod(function writeBigInt64LE(value, offset = 0) {
    return wrtBigUInt64LE(this, value, offset, -BigInt("0x8000000000000000"), BigInt("0x7fffffffffffffff"));
  });
  Buffer3.prototype.writeBigInt64BE = defineBigIntMethod(function writeBigInt64BE(value, offset = 0) {
    return wrtBigUInt64BE(this, value, offset, -BigInt("0x8000000000000000"), BigInt("0x7fffffffffffffff"));
  });
  function checkIEEE754(buf, value, offset, ext, max, min) {
    if (offset + ext > buf.length) throw new RangeError("Index out of range");
    if (offset < 0) throw new RangeError("Index out of range");
  }
  function writeFloat(buf, value, offset, littleEndian, noAssert) {
    value = +value;
    offset = offset >>> 0;
    if (!noAssert) {
      checkIEEE754(buf, value, offset, 4);
    }
    ieee754.write(buf, value, offset, littleEndian, 23, 4);
    return offset + 4;
  }
  Buffer3.prototype.writeFloatLE = function writeFloatLE(value, offset, noAssert) {
    return writeFloat(this, value, offset, true, noAssert);
  };
  Buffer3.prototype.writeFloatBE = function writeFloatBE(value, offset, noAssert) {
    return writeFloat(this, value, offset, false, noAssert);
  };
  function writeDouble(buf, value, offset, littleEndian, noAssert) {
    value = +value;
    offset = offset >>> 0;
    if (!noAssert) {
      checkIEEE754(buf, value, offset, 8);
    }
    ieee754.write(buf, value, offset, littleEndian, 52, 8);
    return offset + 8;
  }
  Buffer3.prototype.writeDoubleLE = function writeDoubleLE(value, offset, noAssert) {
    return writeDouble(this, value, offset, true, noAssert);
  };
  Buffer3.prototype.writeDoubleBE = function writeDoubleBE(value, offset, noAssert) {
    return writeDouble(this, value, offset, false, noAssert);
  };
  Buffer3.prototype.copy = function copy(target, targetStart, start, end) {
    if (!Buffer3.isBuffer(target)) throw new TypeError("argument should be a Buffer");
    if (!start) start = 0;
    if (!end && end !== 0) end = this.length;
    if (targetStart >= target.length) targetStart = target.length;
    if (!targetStart) targetStart = 0;
    if (end > 0 && end < start) end = start;
    if (end === start) return 0;
    if (target.length === 0 || this.length === 0) return 0;
    if (targetStart < 0) {
      throw new RangeError("targetStart out of bounds");
    }
    if (start < 0 || start >= this.length) throw new RangeError("Index out of range");
    if (end < 0) throw new RangeError("sourceEnd out of bounds");
    if (end > this.length) end = this.length;
    if (target.length - targetStart < end - start) {
      end = target.length - targetStart + start;
    }
    const len = end - start;
    if (this === target && typeof Uint8Array.prototype.copyWithin === "function") {
      this.copyWithin(targetStart, start, end);
    } else {
      Uint8Array.prototype.set.call(target, this.subarray(start, end), targetStart);
    }
    return len;
  };
  Buffer3.prototype.fill = function fill(val, start, end, encoding) {
    if (typeof val === "string") {
      if (typeof start === "string") {
        encoding = start;
        start = 0;
        end = this.length;
      } else if (typeof end === "string") {
        encoding = end;
        end = this.length;
      }
      if (encoding !== void 0 && typeof encoding !== "string") {
        throw new TypeError("encoding must be a string");
      }
      if (typeof encoding === "string" && !Buffer3.isEncoding(encoding)) {
        throw new TypeError("Unknown encoding: " + encoding);
      }
      if (val.length === 1) {
        const code = val.charCodeAt(0);
        if (encoding === "utf8" && code < 128 || encoding === "latin1") {
          val = code;
        }
      }
    } else if (typeof val === "number") {
      val = val & 255;
    } else if (typeof val === "boolean") {
      val = Number(val);
    }
    if (start < 0 || this.length < start || this.length < end) {
      throw new RangeError("Out of range index");
    }
    if (end <= start) {
      return this;
    }
    start = start >>> 0;
    end = end === void 0 ? this.length : end >>> 0;
    if (!val) val = 0;
    let i6;
    if (typeof val === "number") {
      for (i6 = start; i6 < end; ++i6) {
        this[i6] = val;
      }
    } else {
      const bytes = Buffer3.isBuffer(val) ? val : Buffer3.from(val, encoding);
      const len = bytes.length;
      if (len === 0) {
        throw new TypeError('The value "' + val + '" is invalid for argument "value"');
      }
      for (i6 = 0; i6 < end - start; ++i6) {
        this[i6 + start] = bytes[i6 % len];
      }
    }
    return this;
  };
  const errors = {};
  function E4(sym, getMessage, Base) {
    errors[sym] = class NodeError extends Base {
      constructor() {
        super();
        Object.defineProperty(this, "message", {
          value: getMessage.apply(this, arguments),
          writable: true,
          configurable: true
        });
        this.name = `${this.name} [${sym}]`;
        this.stack;
        delete this.name;
      }
      get code() {
        return sym;
      }
      set code(value) {
        Object.defineProperty(this, "code", {
          configurable: true,
          enumerable: true,
          value,
          writable: true
        });
      }
      toString() {
        return `${this.name} [${sym}]: ${this.message}`;
      }
    };
  }
  E4("ERR_BUFFER_OUT_OF_BOUNDS", function(name2) {
    if (name2) {
      return `${name2} is outside of buffer bounds`;
    }
    return "Attempt to access memory outside buffer bounds";
  }, RangeError);
  E4("ERR_INVALID_ARG_TYPE", function(name2, actual) {
    return `The "${name2}" argument must be of type number. Received type ${typeof actual}`;
  }, TypeError);
  E4("ERR_OUT_OF_RANGE", function(str, range, input) {
    let msg = `The value of "${str}" is out of range.`;
    let received = input;
    if (Number.isInteger(input) && Math.abs(input) > 2 ** 32) {
      received = addNumericalSeparator(String(input));
    } else if (typeof input === "bigint") {
      received = String(input);
      if (input > BigInt(2) ** BigInt(32) || input < -(BigInt(2) ** BigInt(32))) {
        received = addNumericalSeparator(received);
      }
      received += "n";
    }
    msg += ` It must be ${range}. Received ${received}`;
    return msg;
  }, RangeError);
  function addNumericalSeparator(val) {
    let res = "";
    let i6 = val.length;
    const start = val[0] === "-" ? 1 : 0;
    for (; i6 >= start + 4; i6 -= 3) {
      res = `_${val.slice(i6 - 3, i6)}${res}`;
    }
    return `${val.slice(0, i6)}${res}`;
  }
  function checkBounds(buf, offset, byteLength2) {
    validateNumber(offset, "offset");
    if (buf[offset] === void 0 || buf[offset + byteLength2] === void 0) {
      boundsError(offset, buf.length - (byteLength2 + 1));
    }
  }
  function checkIntBI(value, min, max, buf, offset, byteLength2) {
    if (value > max || value < min) {
      const n6 = typeof min === "bigint" ? "n" : "";
      let range;
      {
        if (min === 0 || min === BigInt(0)) {
          range = `>= 0${n6} and < 2${n6} ** ${(byteLength2 + 1) * 8}${n6}`;
        } else {
          range = `>= -(2${n6} ** ${(byteLength2 + 1) * 8 - 1}${n6}) and < 2 ** ${(byteLength2 + 1) * 8 - 1}${n6}`;
        }
      }
      throw new errors.ERR_OUT_OF_RANGE("value", range, value);
    }
    checkBounds(buf, offset, byteLength2);
  }
  function validateNumber(value, name2) {
    if (typeof value !== "number") {
      throw new errors.ERR_INVALID_ARG_TYPE(name2, "number", value);
    }
  }
  function boundsError(value, length, type) {
    if (Math.floor(value) !== value) {
      validateNumber(value, type);
      throw new errors.ERR_OUT_OF_RANGE("offset", "an integer", value);
    }
    if (length < 0) {
      throw new errors.ERR_BUFFER_OUT_OF_BOUNDS();
    }
    throw new errors.ERR_OUT_OF_RANGE("offset", `>= ${0} and <= ${length}`, value);
  }
  const INVALID_BASE64_RE = /[^+/0-9A-Za-z-_]/g;
  function base64clean(str) {
    str = str.split("=")[0];
    str = str.trim().replace(INVALID_BASE64_RE, "");
    if (str.length < 2) return "";
    while (str.length % 4 !== 0) {
      str = str + "=";
    }
    return str;
  }
  function utf8ToBytes(string, units) {
    units = units || Infinity;
    let codePoint;
    const length = string.length;
    let leadSurrogate = null;
    const bytes = [];
    for (let i6 = 0; i6 < length; ++i6) {
      codePoint = string.charCodeAt(i6);
      if (codePoint > 55295 && codePoint < 57344) {
        if (!leadSurrogate) {
          if (codePoint > 56319) {
            if ((units -= 3) > -1) bytes.push(239, 191, 189);
            continue;
          } else if (i6 + 1 === length) {
            if ((units -= 3) > -1) bytes.push(239, 191, 189);
            continue;
          }
          leadSurrogate = codePoint;
          continue;
        }
        if (codePoint < 56320) {
          if ((units -= 3) > -1) bytes.push(239, 191, 189);
          leadSurrogate = codePoint;
          continue;
        }
        codePoint = (leadSurrogate - 55296 << 10 | codePoint - 56320) + 65536;
      } else if (leadSurrogate) {
        if ((units -= 3) > -1) bytes.push(239, 191, 189);
      }
      leadSurrogate = null;
      if (codePoint < 128) {
        if ((units -= 1) < 0) break;
        bytes.push(codePoint);
      } else if (codePoint < 2048) {
        if ((units -= 2) < 0) break;
        bytes.push(codePoint >> 6 | 192, codePoint & 63 | 128);
      } else if (codePoint < 65536) {
        if ((units -= 3) < 0) break;
        bytes.push(codePoint >> 12 | 224, codePoint >> 6 & 63 | 128, codePoint & 63 | 128);
      } else if (codePoint < 1114112) {
        if ((units -= 4) < 0) break;
        bytes.push(codePoint >> 18 | 240, codePoint >> 12 & 63 | 128, codePoint >> 6 & 63 | 128, codePoint & 63 | 128);
      } else {
        throw new Error("Invalid code point");
      }
    }
    return bytes;
  }
  function asciiToBytes(str) {
    const byteArray = [];
    for (let i6 = 0; i6 < str.length; ++i6) {
      byteArray.push(str.charCodeAt(i6) & 255);
    }
    return byteArray;
  }
  function utf16leToBytes(str, units) {
    let c6, hi, lo;
    const byteArray = [];
    for (let i6 = 0; i6 < str.length; ++i6) {
      if ((units -= 2) < 0) break;
      c6 = str.charCodeAt(i6);
      hi = c6 >> 8;
      lo = c6 % 256;
      byteArray.push(lo);
      byteArray.push(hi);
    }
    return byteArray;
  }
  function base64ToBytes(str) {
    return base64.toByteArray(base64clean(str));
  }
  function blitBuffer(src, dst, offset, length) {
    let i6;
    for (i6 = 0; i6 < length; ++i6) {
      if (i6 + offset >= dst.length || i6 >= src.length) break;
      dst[i6 + offset] = src[i6];
    }
    return i6;
  }
  function isInstance(obj, type) {
    return obj instanceof type || obj != null && obj.constructor != null && obj.constructor.name != null && obj.constructor.name === type.name;
  }
  function numberIsNaN(obj) {
    return obj !== obj;
  }
  const hexSliceLookupTable = (function() {
    const alphabet = "0123456789abcdef";
    const table = new Array(256);
    for (let i6 = 0; i6 < 16; ++i6) {
      const i16 = i6 * 16;
      for (let j4 = 0; j4 < 16; ++j4) {
        table[i16 + j4] = alphabet[i6] + alphabet[j4];
      }
    }
    return table;
  })();
  function defineBigIntMethod(fn) {
    return typeof BigInt === "undefined" ? BufferBigIntNotDefined : fn;
  }
  function BufferBigIntNotDefined() {
    throw new Error("BigInt not supported");
  }
  return exports$g;
}
function dew$f() {
  if (_dewExec$f) return exports$f;
  _dewExec$f = true;
  if (typeof Object.create === "function") {
    exports$f = function inherits(ctor, superCtor) {
      if (superCtor) {
        ctor.super_ = superCtor;
        ctor.prototype = Object.create(superCtor.prototype, {
          constructor: {
            value: ctor,
            enumerable: false,
            writable: true,
            configurable: true
          }
        });
      }
    };
  } else {
    exports$f = function inherits(ctor, superCtor) {
      if (superCtor) {
        ctor.super_ = superCtor;
        var TempCtor = function() {
        };
        TempCtor.prototype = superCtor.prototype;
        ctor.prototype = new TempCtor();
        ctor.prototype.constructor = ctor;
      }
    };
  }
  return exports$f;
}
function dew$e() {
  if (_dewExec$e) return exports$e;
  _dewExec$e = true;
  exports$e = y4.EventEmitter;
  return exports$e;
}
function dew$d() {
  if (_dewExec$d) return exports$d;
  _dewExec$d = true;
  function ownKeys(object, enumerableOnly) {
    var keys = Object.keys(object);
    if (Object.getOwnPropertySymbols) {
      var symbols = Object.getOwnPropertySymbols(object);
      if (enumerableOnly) symbols = symbols.filter(function(sym) {
        return Object.getOwnPropertyDescriptor(object, sym).enumerable;
      });
      keys.push.apply(keys, symbols);
    }
    return keys;
  }
  function _objectSpread(target) {
    for (var i6 = 1; i6 < arguments.length; i6++) {
      var source = arguments[i6] != null ? arguments[i6] : {};
      if (i6 % 2) {
        ownKeys(Object(source), true).forEach(function(key) {
          _defineProperty(target, key, source[key]);
        });
      } else if (Object.getOwnPropertyDescriptors) {
        Object.defineProperties(target, Object.getOwnPropertyDescriptors(source));
      } else {
        ownKeys(Object(source)).forEach(function(key) {
          Object.defineProperty(target, key, Object.getOwnPropertyDescriptor(source, key));
        });
      }
    }
    return target;
  }
  function _defineProperty(obj, key, value) {
    if (key in obj) {
      Object.defineProperty(obj, key, {
        value,
        enumerable: true,
        configurable: true,
        writable: true
      });
    } else {
      obj[key] = value;
    }
    return obj;
  }
  function _classCallCheck(instance, Constructor) {
    if (!(instance instanceof Constructor)) {
      throw new TypeError("Cannot call a class as a function");
    }
  }
  function _defineProperties(target, props) {
    for (var i6 = 0; i6 < props.length; i6++) {
      var descriptor = props[i6];
      descriptor.enumerable = descriptor.enumerable || false;
      descriptor.configurable = true;
      if ("value" in descriptor) descriptor.writable = true;
      Object.defineProperty(target, descriptor.key, descriptor);
    }
  }
  function _createClass(Constructor, protoProps, staticProps) {
    if (protoProps) _defineProperties(Constructor.prototype, protoProps);
    return Constructor;
  }
  var _require = buffer, Buffer3 = _require.Buffer;
  var _require2 = X, inspect = _require2.inspect;
  var custom = inspect && inspect.custom || "inspect";
  function copyBuffer(src, target, offset) {
    Buffer3.prototype.copy.call(src, target, offset);
  }
  exports$d = /* @__PURE__ */ (function() {
    function BufferList() {
      _classCallCheck(this, BufferList);
      this.head = null;
      this.tail = null;
      this.length = 0;
    }
    _createClass(BufferList, [{
      key: "push",
      value: function push(v6) {
        var entry = {
          data: v6,
          next: null
        };
        if (this.length > 0) this.tail.next = entry;
        else this.head = entry;
        this.tail = entry;
        ++this.length;
      }
    }, {
      key: "unshift",
      value: function unshift(v6) {
        var entry = {
          data: v6,
          next: this.head
        };
        if (this.length === 0) this.tail = entry;
        this.head = entry;
        ++this.length;
      }
    }, {
      key: "shift",
      value: function shift() {
        if (this.length === 0) return;
        var ret = this.head.data;
        if (this.length === 1) this.head = this.tail = null;
        else this.head = this.head.next;
        --this.length;
        return ret;
      }
    }, {
      key: "clear",
      value: function clear() {
        this.head = this.tail = null;
        this.length = 0;
      }
    }, {
      key: "join",
      value: function join(s6) {
        if (this.length === 0) return "";
        var p6 = this.head;
        var ret = "" + p6.data;
        while (p6 = p6.next) {
          ret += s6 + p6.data;
        }
        return ret;
      }
    }, {
      key: "concat",
      value: function concat(n6) {
        if (this.length === 0) return Buffer3.alloc(0);
        var ret = Buffer3.allocUnsafe(n6 >>> 0);
        var p6 = this.head;
        var i6 = 0;
        while (p6) {
          copyBuffer(p6.data, ret, i6);
          i6 += p6.data.length;
          p6 = p6.next;
        }
        return ret;
      }
      // Consumes a specified amount of bytes or characters from the buffered data.
    }, {
      key: "consume",
      value: function consume(n6, hasStrings) {
        var ret;
        if (n6 < this.head.data.length) {
          ret = this.head.data.slice(0, n6);
          this.head.data = this.head.data.slice(n6);
        } else if (n6 === this.head.data.length) {
          ret = this.shift();
        } else {
          ret = hasStrings ? this._getString(n6) : this._getBuffer(n6);
        }
        return ret;
      }
    }, {
      key: "first",
      value: function first() {
        return this.head.data;
      }
      // Consumes a specified amount of characters from the buffered data.
    }, {
      key: "_getString",
      value: function _getString(n6) {
        var p6 = this.head;
        var c6 = 1;
        var ret = p6.data;
        n6 -= ret.length;
        while (p6 = p6.next) {
          var str = p6.data;
          var nb = n6 > str.length ? str.length : n6;
          if (nb === str.length) ret += str;
          else ret += str.slice(0, n6);
          n6 -= nb;
          if (n6 === 0) {
            if (nb === str.length) {
              ++c6;
              if (p6.next) this.head = p6.next;
              else this.head = this.tail = null;
            } else {
              this.head = p6;
              p6.data = str.slice(nb);
            }
            break;
          }
          ++c6;
        }
        this.length -= c6;
        return ret;
      }
      // Consumes a specified amount of bytes from the buffered data.
    }, {
      key: "_getBuffer",
      value: function _getBuffer(n6) {
        var ret = Buffer3.allocUnsafe(n6);
        var p6 = this.head;
        var c6 = 1;
        p6.data.copy(ret);
        n6 -= p6.data.length;
        while (p6 = p6.next) {
          var buf = p6.data;
          var nb = n6 > buf.length ? buf.length : n6;
          buf.copy(ret, ret.length - n6, 0, nb);
          n6 -= nb;
          if (n6 === 0) {
            if (nb === buf.length) {
              ++c6;
              if (p6.next) this.head = p6.next;
              else this.head = this.tail = null;
            } else {
              this.head = p6;
              p6.data = buf.slice(nb);
            }
            break;
          }
          ++c6;
        }
        this.length -= c6;
        return ret;
      }
      // Make sure the linked list only shows the minimal necessary information.
    }, {
      key: custom,
      value: function value(_4, options) {
        return inspect(this, _objectSpread({}, options, {
          // Only inspect one level.
          depth: 0,
          // It should not recurse.
          customInspect: false
        }));
      }
    }]);
    return BufferList;
  })();
  return exports$d;
}
function dew$c() {
  if (_dewExec$c) return exports$c;
  _dewExec$c = true;
  var process$1 = process2;
  function destroy(err, cb) {
    var _this = this;
    var readableDestroyed = this._readableState && this._readableState.destroyed;
    var writableDestroyed = this._writableState && this._writableState.destroyed;
    if (readableDestroyed || writableDestroyed) {
      if (cb) {
        cb(err);
      } else if (err) {
        if (!this._writableState) {
          process$1.nextTick(emitErrorNT, this, err);
        } else if (!this._writableState.errorEmitted) {
          this._writableState.errorEmitted = true;
          process$1.nextTick(emitErrorNT, this, err);
        }
      }
      return this;
    }
    if (this._readableState) {
      this._readableState.destroyed = true;
    }
    if (this._writableState) {
      this._writableState.destroyed = true;
    }
    this._destroy(err || null, function(err2) {
      if (!cb && err2) {
        if (!_this._writableState) {
          process$1.nextTick(emitErrorAndCloseNT, _this, err2);
        } else if (!_this._writableState.errorEmitted) {
          _this._writableState.errorEmitted = true;
          process$1.nextTick(emitErrorAndCloseNT, _this, err2);
        } else {
          process$1.nextTick(emitCloseNT, _this);
        }
      } else if (cb) {
        process$1.nextTick(emitCloseNT, _this);
        cb(err2);
      } else {
        process$1.nextTick(emitCloseNT, _this);
      }
    });
    return this;
  }
  function emitErrorAndCloseNT(self2, err) {
    emitErrorNT(self2, err);
    emitCloseNT(self2);
  }
  function emitCloseNT(self2) {
    if (self2._writableState && !self2._writableState.emitClose) return;
    if (self2._readableState && !self2._readableState.emitClose) return;
    self2.emit("close");
  }
  function undestroy() {
    if (this._readableState) {
      this._readableState.destroyed = false;
      this._readableState.reading = false;
      this._readableState.ended = false;
      this._readableState.endEmitted = false;
    }
    if (this._writableState) {
      this._writableState.destroyed = false;
      this._writableState.ended = false;
      this._writableState.ending = false;
      this._writableState.finalCalled = false;
      this._writableState.prefinished = false;
      this._writableState.finished = false;
      this._writableState.errorEmitted = false;
    }
  }
  function emitErrorNT(self2, err) {
    self2.emit("error", err);
  }
  function errorOrDestroy(stream, err) {
    var rState = stream._readableState;
    var wState = stream._writableState;
    if (rState && rState.autoDestroy || wState && wState.autoDestroy) stream.destroy(err);
    else stream.emit("error", err);
  }
  exports$c = {
    destroy,
    undestroy,
    errorOrDestroy
  };
  return exports$c;
}
function dew$b() {
  if (_dewExec$b) return exports$b;
  _dewExec$b = true;
  const codes = {};
  function createErrorType(code, message, Base) {
    if (!Base) {
      Base = Error;
    }
    function getMessage(arg1, arg2, arg3) {
      if (typeof message === "string") {
        return message;
      } else {
        return message(arg1, arg2, arg3);
      }
    }
    class NodeError extends Base {
      constructor(arg1, arg2, arg3) {
        super(getMessage(arg1, arg2, arg3));
      }
    }
    NodeError.prototype.name = Base.name;
    NodeError.prototype.code = code;
    codes[code] = NodeError;
  }
  function oneOf(expected, thing) {
    if (Array.isArray(expected)) {
      const len = expected.length;
      expected = expected.map((i6) => String(i6));
      if (len > 2) {
        return `one of ${thing} ${expected.slice(0, len - 1).join(", ")}, or ` + expected[len - 1];
      } else if (len === 2) {
        return `one of ${thing} ${expected[0]} or ${expected[1]}`;
      } else {
        return `of ${thing} ${expected[0]}`;
      }
    } else {
      return `of ${thing} ${String(expected)}`;
    }
  }
  function startsWith(str, search, pos) {
    return str.substr(0, search.length) === search;
  }
  function endsWith(str, search, this_len) {
    if (this_len === void 0 || this_len > str.length) {
      this_len = str.length;
    }
    return str.substring(this_len - search.length, this_len) === search;
  }
  function includes(str, search, start) {
    if (typeof start !== "number") {
      start = 0;
    }
    if (start + search.length > str.length) {
      return false;
    } else {
      return str.indexOf(search, start) !== -1;
    }
  }
  createErrorType("ERR_INVALID_OPT_VALUE", function(name2, value) {
    return 'The value "' + value + '" is invalid for option "' + name2 + '"';
  }, TypeError);
  createErrorType("ERR_INVALID_ARG_TYPE", function(name2, expected, actual) {
    let determiner;
    if (typeof expected === "string" && startsWith(expected, "not ")) {
      determiner = "must not be";
      expected = expected.replace(/^not /, "");
    } else {
      determiner = "must be";
    }
    let msg;
    if (endsWith(name2, " argument")) {
      msg = `The ${name2} ${determiner} ${oneOf(expected, "type")}`;
    } else {
      const type = includes(name2, ".") ? "property" : "argument";
      msg = `The "${name2}" ${type} ${determiner} ${oneOf(expected, "type")}`;
    }
    msg += `. Received type ${typeof actual}`;
    return msg;
  }, TypeError);
  createErrorType("ERR_STREAM_PUSH_AFTER_EOF", "stream.push() after EOF");
  createErrorType("ERR_METHOD_NOT_IMPLEMENTED", function(name2) {
    return "The " + name2 + " method is not implemented";
  });
  createErrorType("ERR_STREAM_PREMATURE_CLOSE", "Premature close");
  createErrorType("ERR_STREAM_DESTROYED", function(name2) {
    return "Cannot call " + name2 + " after a stream was destroyed";
  });
  createErrorType("ERR_MULTIPLE_CALLBACK", "Callback called multiple times");
  createErrorType("ERR_STREAM_CANNOT_PIPE", "Cannot pipe, not readable");
  createErrorType("ERR_STREAM_WRITE_AFTER_END", "write after end");
  createErrorType("ERR_STREAM_NULL_VALUES", "May not write null values to stream", TypeError);
  createErrorType("ERR_UNKNOWN_ENCODING", function(arg) {
    return "Unknown encoding: " + arg;
  }, TypeError);
  createErrorType("ERR_STREAM_UNSHIFT_AFTER_END_EVENT", "stream.unshift() after end event");
  exports$b.codes = codes;
  return exports$b;
}
function dew$a() {
  if (_dewExec$a) return exports$a;
  _dewExec$a = true;
  var ERR_INVALID_OPT_VALUE = dew$b().codes.ERR_INVALID_OPT_VALUE;
  function highWaterMarkFrom(options, isDuplex, duplexKey) {
    return options.highWaterMark != null ? options.highWaterMark : isDuplex ? options[duplexKey] : null;
  }
  function getHighWaterMark(state, options, duplexKey, isDuplex) {
    var hwm = highWaterMarkFrom(options, isDuplex, duplexKey);
    if (hwm != null) {
      if (!(isFinite(hwm) && Math.floor(hwm) === hwm) || hwm < 0) {
        var name2 = isDuplex ? duplexKey : "highWaterMark";
        throw new ERR_INVALID_OPT_VALUE(name2, hwm);
      }
      return Math.floor(hwm);
    }
    return state.objectMode ? 16 : 16 * 1024;
  }
  exports$a = {
    getHighWaterMark
  };
  return exports$a;
}
function dew$9() {
  if (_dewExec$9) return exports$9;
  _dewExec$9 = true;
  exports$9 = deprecate;
  function deprecate(fn, msg) {
    if (config3("noDeprecation")) {
      return fn;
    }
    var warned = false;
    function deprecated() {
      if (!warned) {
        if (config3("throwDeprecation")) {
          throw new Error(msg);
        } else if (config3("traceDeprecation")) {
          console.trace(msg);
        } else {
          console.warn(msg);
        }
        warned = true;
      }
      return fn.apply(this || _global$2, arguments);
    }
    return deprecated;
  }
  function config3(name2) {
    try {
      if (!_global$2.localStorage) return false;
    } catch (_4) {
      return false;
    }
    var val = _global$2.localStorage[name2];
    if (null == val) return false;
    return String(val).toLowerCase() === "true";
  }
  return exports$9;
}
function dew$8() {
  if (_dewExec$8) return exports$8;
  _dewExec$8 = true;
  var process$1 = process2;
  exports$8 = Writable;
  function CorkedRequest(state) {
    var _this = this;
    this.next = null;
    this.entry = null;
    this.finish = function() {
      onCorkedFinish(_this, state);
    };
  }
  var Duplex;
  Writable.WritableState = WritableState;
  var internalUtil = {
    deprecate: dew$9()
  };
  var Stream = dew$e();
  var Buffer3 = buffer.Buffer;
  var OurUint8Array = _global$1.Uint8Array || function() {
  };
  function _uint8ArrayToBuffer(chunk) {
    return Buffer3.from(chunk);
  }
  function _isUint8Array(obj) {
    return Buffer3.isBuffer(obj) || obj instanceof OurUint8Array;
  }
  var destroyImpl = dew$c();
  var _require = dew$a(), getHighWaterMark = _require.getHighWaterMark;
  var _require$codes = dew$b().codes, ERR_INVALID_ARG_TYPE = _require$codes.ERR_INVALID_ARG_TYPE, ERR_METHOD_NOT_IMPLEMENTED = _require$codes.ERR_METHOD_NOT_IMPLEMENTED, ERR_MULTIPLE_CALLBACK = _require$codes.ERR_MULTIPLE_CALLBACK, ERR_STREAM_CANNOT_PIPE = _require$codes.ERR_STREAM_CANNOT_PIPE, ERR_STREAM_DESTROYED = _require$codes.ERR_STREAM_DESTROYED, ERR_STREAM_NULL_VALUES = _require$codes.ERR_STREAM_NULL_VALUES, ERR_STREAM_WRITE_AFTER_END = _require$codes.ERR_STREAM_WRITE_AFTER_END, ERR_UNKNOWN_ENCODING = _require$codes.ERR_UNKNOWN_ENCODING;
  var errorOrDestroy = destroyImpl.errorOrDestroy;
  dew$f()(Writable, Stream);
  function nop() {
  }
  function WritableState(options, stream, isDuplex) {
    Duplex = Duplex || dew$7();
    options = options || {};
    if (typeof isDuplex !== "boolean") isDuplex = stream instanceof Duplex;
    this.objectMode = !!options.objectMode;
    if (isDuplex) this.objectMode = this.objectMode || !!options.writableObjectMode;
    this.highWaterMark = getHighWaterMark(this, options, "writableHighWaterMark", isDuplex);
    this.finalCalled = false;
    this.needDrain = false;
    this.ending = false;
    this.ended = false;
    this.finished = false;
    this.destroyed = false;
    var noDecode = options.decodeStrings === false;
    this.decodeStrings = !noDecode;
    this.defaultEncoding = options.defaultEncoding || "utf8";
    this.length = 0;
    this.writing = false;
    this.corked = 0;
    this.sync = true;
    this.bufferProcessing = false;
    this.onwrite = function(er) {
      onwrite(stream, er);
    };
    this.writecb = null;
    this.writelen = 0;
    this.bufferedRequest = null;
    this.lastBufferedRequest = null;
    this.pendingcb = 0;
    this.prefinished = false;
    this.errorEmitted = false;
    this.emitClose = options.emitClose !== false;
    this.autoDestroy = !!options.autoDestroy;
    this.bufferedRequestCount = 0;
    this.corkedRequestsFree = new CorkedRequest(this);
  }
  WritableState.prototype.getBuffer = function getBuffer() {
    var current = this.bufferedRequest;
    var out = [];
    while (current) {
      out.push(current);
      current = current.next;
    }
    return out;
  };
  (function() {
    try {
      Object.defineProperty(WritableState.prototype, "buffer", {
        get: internalUtil.deprecate(function writableStateBufferGetter() {
          return this.getBuffer();
        }, "_writableState.buffer is deprecated. Use _writableState.getBuffer instead.", "DEP0003")
      });
    } catch (_4) {
    }
  })();
  var realHasInstance;
  if (typeof Symbol === "function" && Symbol.hasInstance && typeof Function.prototype[Symbol.hasInstance] === "function") {
    realHasInstance = Function.prototype[Symbol.hasInstance];
    Object.defineProperty(Writable, Symbol.hasInstance, {
      value: function value(object) {
        if (realHasInstance.call(this, object)) return true;
        if (this !== Writable) return false;
        return object && object._writableState instanceof WritableState;
      }
    });
  } else {
    realHasInstance = function realHasInstance2(object) {
      return object instanceof this;
    };
  }
  function Writable(options) {
    Duplex = Duplex || dew$7();
    var isDuplex = this instanceof Duplex;
    if (!isDuplex && !realHasInstance.call(Writable, this)) return new Writable(options);
    this._writableState = new WritableState(options, this, isDuplex);
    this.writable = true;
    if (options) {
      if (typeof options.write === "function") this._write = options.write;
      if (typeof options.writev === "function") this._writev = options.writev;
      if (typeof options.destroy === "function") this._destroy = options.destroy;
      if (typeof options.final === "function") this._final = options.final;
    }
    Stream.call(this);
  }
  Writable.prototype.pipe = function() {
    errorOrDestroy(this, new ERR_STREAM_CANNOT_PIPE());
  };
  function writeAfterEnd(stream, cb) {
    var er = new ERR_STREAM_WRITE_AFTER_END();
    errorOrDestroy(stream, er);
    process$1.nextTick(cb, er);
  }
  function validChunk(stream, state, chunk, cb) {
    var er;
    if (chunk === null) {
      er = new ERR_STREAM_NULL_VALUES();
    } else if (typeof chunk !== "string" && !state.objectMode) {
      er = new ERR_INVALID_ARG_TYPE("chunk", ["string", "Buffer"], chunk);
    }
    if (er) {
      errorOrDestroy(stream, er);
      process$1.nextTick(cb, er);
      return false;
    }
    return true;
  }
  Writable.prototype.write = function(chunk, encoding, cb) {
    var state = this._writableState;
    var ret = false;
    var isBuf = !state.objectMode && _isUint8Array(chunk);
    if (isBuf && !Buffer3.isBuffer(chunk)) {
      chunk = _uint8ArrayToBuffer(chunk);
    }
    if (typeof encoding === "function") {
      cb = encoding;
      encoding = null;
    }
    if (isBuf) encoding = "buffer";
    else if (!encoding) encoding = state.defaultEncoding;
    if (typeof cb !== "function") cb = nop;
    if (state.ending) writeAfterEnd(this, cb);
    else if (isBuf || validChunk(this, state, chunk, cb)) {
      state.pendingcb++;
      ret = writeOrBuffer(this, state, isBuf, chunk, encoding, cb);
    }
    return ret;
  };
  Writable.prototype.cork = function() {
    this._writableState.corked++;
  };
  Writable.prototype.uncork = function() {
    var state = this._writableState;
    if (state.corked) {
      state.corked--;
      if (!state.writing && !state.corked && !state.bufferProcessing && state.bufferedRequest) clearBuffer(this, state);
    }
  };
  Writable.prototype.setDefaultEncoding = function setDefaultEncoding(encoding) {
    if (typeof encoding === "string") encoding = encoding.toLowerCase();
    if (!(["hex", "utf8", "utf-8", "ascii", "binary", "base64", "ucs2", "ucs-2", "utf16le", "utf-16le", "raw"].indexOf((encoding + "").toLowerCase()) > -1)) throw new ERR_UNKNOWN_ENCODING(encoding);
    this._writableState.defaultEncoding = encoding;
    return this;
  };
  Object.defineProperty(Writable.prototype, "writableBuffer", {
    // making it explicit this property is not enumerable
    // because otherwise some prototype manipulation in
    // userland will fail
    enumerable: false,
    get: function get() {
      return this._writableState && this._writableState.getBuffer();
    }
  });
  function decodeChunk(state, chunk, encoding) {
    if (!state.objectMode && state.decodeStrings !== false && typeof chunk === "string") {
      chunk = Buffer3.from(chunk, encoding);
    }
    return chunk;
  }
  Object.defineProperty(Writable.prototype, "writableHighWaterMark", {
    // making it explicit this property is not enumerable
    // because otherwise some prototype manipulation in
    // userland will fail
    enumerable: false,
    get: function get() {
      return this._writableState.highWaterMark;
    }
  });
  function writeOrBuffer(stream, state, isBuf, chunk, encoding, cb) {
    if (!isBuf) {
      var newChunk = decodeChunk(state, chunk, encoding);
      if (chunk !== newChunk) {
        isBuf = true;
        encoding = "buffer";
        chunk = newChunk;
      }
    }
    var len = state.objectMode ? 1 : chunk.length;
    state.length += len;
    var ret = state.length < state.highWaterMark;
    if (!ret) state.needDrain = true;
    if (state.writing || state.corked) {
      var last = state.lastBufferedRequest;
      state.lastBufferedRequest = {
        chunk,
        encoding,
        isBuf,
        callback: cb,
        next: null
      };
      if (last) {
        last.next = state.lastBufferedRequest;
      } else {
        state.bufferedRequest = state.lastBufferedRequest;
      }
      state.bufferedRequestCount += 1;
    } else {
      doWrite(stream, state, false, len, chunk, encoding, cb);
    }
    return ret;
  }
  function doWrite(stream, state, writev2, len, chunk, encoding, cb) {
    state.writelen = len;
    state.writecb = cb;
    state.writing = true;
    state.sync = true;
    if (state.destroyed) state.onwrite(new ERR_STREAM_DESTROYED("write"));
    else if (writev2) stream._writev(chunk, state.onwrite);
    else stream._write(chunk, encoding, state.onwrite);
    state.sync = false;
  }
  function onwriteError(stream, state, sync, er, cb) {
    --state.pendingcb;
    if (sync) {
      process$1.nextTick(cb, er);
      process$1.nextTick(finishMaybe, stream, state);
      stream._writableState.errorEmitted = true;
      errorOrDestroy(stream, er);
    } else {
      cb(er);
      stream._writableState.errorEmitted = true;
      errorOrDestroy(stream, er);
      finishMaybe(stream, state);
    }
  }
  function onwriteStateUpdate(state) {
    state.writing = false;
    state.writecb = null;
    state.length -= state.writelen;
    state.writelen = 0;
  }
  function onwrite(stream, er) {
    var state = stream._writableState;
    var sync = state.sync;
    var cb = state.writecb;
    if (typeof cb !== "function") throw new ERR_MULTIPLE_CALLBACK();
    onwriteStateUpdate(state);
    if (er) onwriteError(stream, state, sync, er, cb);
    else {
      var finished = needFinish(state) || stream.destroyed;
      if (!finished && !state.corked && !state.bufferProcessing && state.bufferedRequest) {
        clearBuffer(stream, state);
      }
      if (sync) {
        process$1.nextTick(afterWrite, stream, state, finished, cb);
      } else {
        afterWrite(stream, state, finished, cb);
      }
    }
  }
  function afterWrite(stream, state, finished, cb) {
    if (!finished) onwriteDrain(stream, state);
    state.pendingcb--;
    cb();
    finishMaybe(stream, state);
  }
  function onwriteDrain(stream, state) {
    if (state.length === 0 && state.needDrain) {
      state.needDrain = false;
      stream.emit("drain");
    }
  }
  function clearBuffer(stream, state) {
    state.bufferProcessing = true;
    var entry = state.bufferedRequest;
    if (stream._writev && entry && entry.next) {
      var l6 = state.bufferedRequestCount;
      var buffer2 = new Array(l6);
      var holder = state.corkedRequestsFree;
      holder.entry = entry;
      var count = 0;
      var allBuffers = true;
      while (entry) {
        buffer2[count] = entry;
        if (!entry.isBuf) allBuffers = false;
        entry = entry.next;
        count += 1;
      }
      buffer2.allBuffers = allBuffers;
      doWrite(stream, state, true, state.length, buffer2, "", holder.finish);
      state.pendingcb++;
      state.lastBufferedRequest = null;
      if (holder.next) {
        state.corkedRequestsFree = holder.next;
        holder.next = null;
      } else {
        state.corkedRequestsFree = new CorkedRequest(state);
      }
      state.bufferedRequestCount = 0;
    } else {
      while (entry) {
        var chunk = entry.chunk;
        var encoding = entry.encoding;
        var cb = entry.callback;
        var len = state.objectMode ? 1 : chunk.length;
        doWrite(stream, state, false, len, chunk, encoding, cb);
        entry = entry.next;
        state.bufferedRequestCount--;
        if (state.writing) {
          break;
        }
      }
      if (entry === null) state.lastBufferedRequest = null;
    }
    state.bufferedRequest = entry;
    state.bufferProcessing = false;
  }
  Writable.prototype._write = function(chunk, encoding, cb) {
    cb(new ERR_METHOD_NOT_IMPLEMENTED("_write()"));
  };
  Writable.prototype._writev = null;
  Writable.prototype.end = function(chunk, encoding, cb) {
    var state = this._writableState;
    if (typeof chunk === "function") {
      cb = chunk;
      chunk = null;
      encoding = null;
    } else if (typeof encoding === "function") {
      cb = encoding;
      encoding = null;
    }
    if (chunk !== null && chunk !== void 0) this.write(chunk, encoding);
    if (state.corked) {
      state.corked = 1;
      this.uncork();
    }
    if (!state.ending) endWritable(this, state, cb);
    return this;
  };
  Object.defineProperty(Writable.prototype, "writableLength", {
    // making it explicit this property is not enumerable
    // because otherwise some prototype manipulation in
    // userland will fail
    enumerable: false,
    get: function get() {
      return this._writableState.length;
    }
  });
  function needFinish(state) {
    return state.ending && state.length === 0 && state.bufferedRequest === null && !state.finished && !state.writing;
  }
  function callFinal(stream, state) {
    stream._final(function(err) {
      state.pendingcb--;
      if (err) {
        errorOrDestroy(stream, err);
      }
      state.prefinished = true;
      stream.emit("prefinish");
      finishMaybe(stream, state);
    });
  }
  function prefinish(stream, state) {
    if (!state.prefinished && !state.finalCalled) {
      if (typeof stream._final === "function" && !state.destroyed) {
        state.pendingcb++;
        state.finalCalled = true;
        process$1.nextTick(callFinal, stream, state);
      } else {
        state.prefinished = true;
        stream.emit("prefinish");
      }
    }
  }
  function finishMaybe(stream, state) {
    var need = needFinish(state);
    if (need) {
      prefinish(stream, state);
      if (state.pendingcb === 0) {
        state.finished = true;
        stream.emit("finish");
        if (state.autoDestroy) {
          var rState = stream._readableState;
          if (!rState || rState.autoDestroy && rState.endEmitted) {
            stream.destroy();
          }
        }
      }
    }
    return need;
  }
  function endWritable(stream, state, cb) {
    state.ending = true;
    finishMaybe(stream, state);
    if (cb) {
      if (state.finished) process$1.nextTick(cb);
      else stream.once("finish", cb);
    }
    state.ended = true;
    stream.writable = false;
  }
  function onCorkedFinish(corkReq, state, err) {
    var entry = corkReq.entry;
    corkReq.entry = null;
    while (entry) {
      var cb = entry.callback;
      state.pendingcb--;
      cb(err);
      entry = entry.next;
    }
    state.corkedRequestsFree.next = corkReq;
  }
  Object.defineProperty(Writable.prototype, "destroyed", {
    // making it explicit this property is not enumerable
    // because otherwise some prototype manipulation in
    // userland will fail
    enumerable: false,
    get: function get() {
      if (this._writableState === void 0) {
        return false;
      }
      return this._writableState.destroyed;
    },
    set: function set(value) {
      if (!this._writableState) {
        return;
      }
      this._writableState.destroyed = value;
    }
  });
  Writable.prototype.destroy = destroyImpl.destroy;
  Writable.prototype._undestroy = destroyImpl.undestroy;
  Writable.prototype._destroy = function(err, cb) {
    cb(err);
  };
  return exports$8;
}
function dew$7() {
  if (_dewExec$7) return exports$7;
  _dewExec$7 = true;
  var process$1 = process2;
  var objectKeys = Object.keys || function(obj) {
    var keys2 = [];
    for (var key in obj) {
      keys2.push(key);
    }
    return keys2;
  };
  exports$7 = Duplex;
  var Readable2 = dew$3();
  var Writable = dew$8();
  dew$f()(Duplex, Readable2);
  {
    var keys = objectKeys(Writable.prototype);
    for (var v6 = 0; v6 < keys.length; v6++) {
      var method = keys[v6];
      if (!Duplex.prototype[method]) Duplex.prototype[method] = Writable.prototype[method];
    }
  }
  function Duplex(options) {
    if (!(this instanceof Duplex)) return new Duplex(options);
    Readable2.call(this, options);
    Writable.call(this, options);
    this.allowHalfOpen = true;
    if (options) {
      if (options.readable === false) this.readable = false;
      if (options.writable === false) this.writable = false;
      if (options.allowHalfOpen === false) {
        this.allowHalfOpen = false;
        this.once("end", onend);
      }
    }
  }
  Object.defineProperty(Duplex.prototype, "writableHighWaterMark", {
    // making it explicit this property is not enumerable
    // because otherwise some prototype manipulation in
    // userland will fail
    enumerable: false,
    get: function get() {
      return this._writableState.highWaterMark;
    }
  });
  Object.defineProperty(Duplex.prototype, "writableBuffer", {
    // making it explicit this property is not enumerable
    // because otherwise some prototype manipulation in
    // userland will fail
    enumerable: false,
    get: function get() {
      return this._writableState && this._writableState.getBuffer();
    }
  });
  Object.defineProperty(Duplex.prototype, "writableLength", {
    // making it explicit this property is not enumerable
    // because otherwise some prototype manipulation in
    // userland will fail
    enumerable: false,
    get: function get() {
      return this._writableState.length;
    }
  });
  function onend() {
    if (this._writableState.ended) return;
    process$1.nextTick(onEndNT, this);
  }
  function onEndNT(self2) {
    self2.end();
  }
  Object.defineProperty(Duplex.prototype, "destroyed", {
    // making it explicit this property is not enumerable
    // because otherwise some prototype manipulation in
    // userland will fail
    enumerable: false,
    get: function get() {
      if (this._readableState === void 0 || this._writableState === void 0) {
        return false;
      }
      return this._readableState.destroyed && this._writableState.destroyed;
    },
    set: function set(value) {
      if (this._readableState === void 0 || this._writableState === void 0) {
        return;
      }
      this._readableState.destroyed = value;
      this._writableState.destroyed = value;
    }
  });
  return exports$7;
}
function dew$6() {
  if (_dewExec$6) return exports$6;
  _dewExec$6 = true;
  var ERR_STREAM_PREMATURE_CLOSE = dew$b().codes.ERR_STREAM_PREMATURE_CLOSE;
  function once3(callback) {
    var called = false;
    return function() {
      if (called) return;
      called = true;
      for (var _len = arguments.length, args = new Array(_len), _key = 0; _key < _len; _key++) {
        args[_key] = arguments[_key];
      }
      callback.apply(this, args);
    };
  }
  function noop3() {
  }
  function isRequest(stream) {
    return stream.setHeader && typeof stream.abort === "function";
  }
  function eos(stream, opts, callback) {
    if (typeof opts === "function") return eos(stream, null, opts);
    if (!opts) opts = {};
    callback = once3(callback || noop3);
    var readable = opts.readable || opts.readable !== false && stream.readable;
    var writable = opts.writable || opts.writable !== false && stream.writable;
    var onlegacyfinish = function onlegacyfinish2() {
      if (!stream.writable) onfinish();
    };
    var writableEnded = stream._writableState && stream._writableState.finished;
    var onfinish = function onfinish2() {
      writable = false;
      writableEnded = true;
      if (!readable) callback.call(stream);
    };
    var readableEnded = stream._readableState && stream._readableState.endEmitted;
    var onend = function onend2() {
      readable = false;
      readableEnded = true;
      if (!writable) callback.call(stream);
    };
    var onerror = function onerror2(err) {
      callback.call(stream, err);
    };
    var onclose = function onclose2() {
      var err;
      if (readable && !readableEnded) {
        if (!stream._readableState || !stream._readableState.ended) err = new ERR_STREAM_PREMATURE_CLOSE();
        return callback.call(stream, err);
      }
      if (writable && !writableEnded) {
        if (!stream._writableState || !stream._writableState.ended) err = new ERR_STREAM_PREMATURE_CLOSE();
        return callback.call(stream, err);
      }
    };
    var onrequest = function onrequest2() {
      stream.req.on("finish", onfinish);
    };
    if (isRequest(stream)) {
      stream.on("complete", onfinish);
      stream.on("abort", onclose);
      if (stream.req) onrequest();
      else stream.on("request", onrequest);
    } else if (writable && !stream._writableState) {
      stream.on("end", onlegacyfinish);
      stream.on("close", onlegacyfinish);
    }
    stream.on("end", onend);
    stream.on("finish", onfinish);
    if (opts.error !== false) stream.on("error", onerror);
    stream.on("close", onclose);
    return function() {
      stream.removeListener("complete", onfinish);
      stream.removeListener("abort", onclose);
      stream.removeListener("request", onrequest);
      if (stream.req) stream.req.removeListener("finish", onfinish);
      stream.removeListener("end", onlegacyfinish);
      stream.removeListener("close", onlegacyfinish);
      stream.removeListener("finish", onfinish);
      stream.removeListener("end", onend);
      stream.removeListener("error", onerror);
      stream.removeListener("close", onclose);
    };
  }
  exports$6 = eos;
  return exports$6;
}
function dew$5() {
  if (_dewExec$5) return exports$5;
  _dewExec$5 = true;
  var process$1 = process2;
  var _Object$setPrototypeO;
  function _defineProperty(obj, key, value) {
    if (key in obj) {
      Object.defineProperty(obj, key, {
        value,
        enumerable: true,
        configurable: true,
        writable: true
      });
    } else {
      obj[key] = value;
    }
    return obj;
  }
  var finished = dew$6();
  var kLastResolve = /* @__PURE__ */ Symbol("lastResolve");
  var kLastReject = /* @__PURE__ */ Symbol("lastReject");
  var kError = /* @__PURE__ */ Symbol("error");
  var kEnded = /* @__PURE__ */ Symbol("ended");
  var kLastPromise = /* @__PURE__ */ Symbol("lastPromise");
  var kHandlePromise = /* @__PURE__ */ Symbol("handlePromise");
  var kStream = /* @__PURE__ */ Symbol("stream");
  function createIterResult2(value, done) {
    return {
      value,
      done
    };
  }
  function readAndResolve(iter) {
    var resolve2 = iter[kLastResolve];
    if (resolve2 !== null) {
      var data = iter[kStream].read();
      if (data !== null) {
        iter[kLastPromise] = null;
        iter[kLastResolve] = null;
        iter[kLastReject] = null;
        resolve2(createIterResult2(data, false));
      }
    }
  }
  function onReadable(iter) {
    process$1.nextTick(readAndResolve, iter);
  }
  function wrapForNext(lastPromise, iter) {
    return function(resolve2, reject) {
      lastPromise.then(function() {
        if (iter[kEnded]) {
          resolve2(createIterResult2(void 0, true));
          return;
        }
        iter[kHandlePromise](resolve2, reject);
      }, reject);
    };
  }
  var AsyncIteratorPrototype = Object.getPrototypeOf(function() {
  });
  var ReadableStreamAsyncIteratorPrototype = Object.setPrototypeOf((_Object$setPrototypeO = {
    get stream() {
      return this[kStream];
    },
    next: function next() {
      var _this = this;
      var error2 = this[kError];
      if (error2 !== null) {
        return Promise.reject(error2);
      }
      if (this[kEnded]) {
        return Promise.resolve(createIterResult2(void 0, true));
      }
      if (this[kStream].destroyed) {
        return new Promise(function(resolve2, reject) {
          process$1.nextTick(function() {
            if (_this[kError]) {
              reject(_this[kError]);
            } else {
              resolve2(createIterResult2(void 0, true));
            }
          });
        });
      }
      var lastPromise = this[kLastPromise];
      var promise;
      if (lastPromise) {
        promise = new Promise(wrapForNext(lastPromise, this));
      } else {
        var data = this[kStream].read();
        if (data !== null) {
          return Promise.resolve(createIterResult2(data, false));
        }
        promise = new Promise(this[kHandlePromise]);
      }
      this[kLastPromise] = promise;
      return promise;
    }
  }, _defineProperty(_Object$setPrototypeO, Symbol.asyncIterator, function() {
    return this;
  }), _defineProperty(_Object$setPrototypeO, "return", function _return() {
    var _this2 = this;
    return new Promise(function(resolve2, reject) {
      _this2[kStream].destroy(null, function(err) {
        if (err) {
          reject(err);
          return;
        }
        resolve2(createIterResult2(void 0, true));
      });
    });
  }), _Object$setPrototypeO), AsyncIteratorPrototype);
  var createReadableStreamAsyncIterator = function createReadableStreamAsyncIterator2(stream) {
    var _Object$create;
    var iterator = Object.create(ReadableStreamAsyncIteratorPrototype, (_Object$create = {}, _defineProperty(_Object$create, kStream, {
      value: stream,
      writable: true
    }), _defineProperty(_Object$create, kLastResolve, {
      value: null,
      writable: true
    }), _defineProperty(_Object$create, kLastReject, {
      value: null,
      writable: true
    }), _defineProperty(_Object$create, kError, {
      value: null,
      writable: true
    }), _defineProperty(_Object$create, kEnded, {
      value: stream._readableState.endEmitted,
      writable: true
    }), _defineProperty(_Object$create, kHandlePromise, {
      value: function value(resolve2, reject) {
        var data = iterator[kStream].read();
        if (data) {
          iterator[kLastPromise] = null;
          iterator[kLastResolve] = null;
          iterator[kLastReject] = null;
          resolve2(createIterResult2(data, false));
        } else {
          iterator[kLastResolve] = resolve2;
          iterator[kLastReject] = reject;
        }
      },
      writable: true
    }), _Object$create));
    iterator[kLastPromise] = null;
    finished(stream, function(err) {
      if (err && err.code !== "ERR_STREAM_PREMATURE_CLOSE") {
        var reject = iterator[kLastReject];
        if (reject !== null) {
          iterator[kLastPromise] = null;
          iterator[kLastResolve] = null;
          iterator[kLastReject] = null;
          reject(err);
        }
        iterator[kError] = err;
        return;
      }
      var resolve2 = iterator[kLastResolve];
      if (resolve2 !== null) {
        iterator[kLastPromise] = null;
        iterator[kLastResolve] = null;
        iterator[kLastReject] = null;
        resolve2(createIterResult2(void 0, true));
      }
      iterator[kEnded] = true;
    });
    stream.on("readable", onReadable.bind(null, iterator));
    return iterator;
  };
  exports$5 = createReadableStreamAsyncIterator;
  return exports$5;
}
function dew$4() {
  if (_dewExec$4) return exports$4;
  _dewExec$4 = true;
  exports$4 = function() {
    throw new Error("Readable.from is not available in the browser");
  };
  return exports$4;
}
function dew$3() {
  if (_dewExec$3) return exports$3;
  _dewExec$3 = true;
  var process$1 = process2;
  exports$3 = Readable2;
  var Duplex;
  Readable2.ReadableState = ReadableState;
  y4.EventEmitter;
  var EElistenerCount = function EElistenerCount2(emitter, type) {
    return emitter.listeners(type).length;
  };
  var Stream = dew$e();
  var Buffer3 = buffer.Buffer;
  var OurUint8Array = _global2.Uint8Array || function() {
  };
  function _uint8ArrayToBuffer(chunk) {
    return Buffer3.from(chunk);
  }
  function _isUint8Array(obj) {
    return Buffer3.isBuffer(obj) || obj instanceof OurUint8Array;
  }
  var debugUtil = X;
  var debug;
  if (debugUtil && debugUtil.debuglog) {
    debug = debugUtil.debuglog("stream");
  } else {
    debug = function debug2() {
    };
  }
  var BufferList = dew$d();
  var destroyImpl = dew$c();
  var _require = dew$a(), getHighWaterMark = _require.getHighWaterMark;
  var _require$codes = dew$b().codes, ERR_INVALID_ARG_TYPE = _require$codes.ERR_INVALID_ARG_TYPE, ERR_STREAM_PUSH_AFTER_EOF = _require$codes.ERR_STREAM_PUSH_AFTER_EOF, ERR_METHOD_NOT_IMPLEMENTED = _require$codes.ERR_METHOD_NOT_IMPLEMENTED, ERR_STREAM_UNSHIFT_AFTER_END_EVENT = _require$codes.ERR_STREAM_UNSHIFT_AFTER_END_EVENT;
  var StringDecoder;
  var createReadableStreamAsyncIterator;
  var from;
  dew$f()(Readable2, Stream);
  var errorOrDestroy = destroyImpl.errorOrDestroy;
  var kProxyEvents = ["error", "close", "destroy", "pause", "resume"];
  function prependListener3(emitter, event, fn) {
    if (typeof emitter.prependListener === "function") return emitter.prependListener(event, fn);
    if (!emitter._events || !emitter._events[event]) emitter.on(event, fn);
    else if (Array.isArray(emitter._events[event])) emitter._events[event].unshift(fn);
    else emitter._events[event] = [fn, emitter._events[event]];
  }
  function ReadableState(options, stream, isDuplex) {
    Duplex = Duplex || dew$7();
    options = options || {};
    if (typeof isDuplex !== "boolean") isDuplex = stream instanceof Duplex;
    this.objectMode = !!options.objectMode;
    if (isDuplex) this.objectMode = this.objectMode || !!options.readableObjectMode;
    this.highWaterMark = getHighWaterMark(this, options, "readableHighWaterMark", isDuplex);
    this.buffer = new BufferList();
    this.length = 0;
    this.pipes = null;
    this.pipesCount = 0;
    this.flowing = null;
    this.ended = false;
    this.endEmitted = false;
    this.reading = false;
    this.sync = true;
    this.needReadable = false;
    this.emittedReadable = false;
    this.readableListening = false;
    this.resumeScheduled = false;
    this.paused = true;
    this.emitClose = options.emitClose !== false;
    this.autoDestroy = !!options.autoDestroy;
    this.destroyed = false;
    this.defaultEncoding = options.defaultEncoding || "utf8";
    this.awaitDrain = 0;
    this.readingMore = false;
    this.decoder = null;
    this.encoding = null;
    if (options.encoding) {
      if (!StringDecoder) StringDecoder = e$14.StringDecoder;
      this.decoder = new StringDecoder(options.encoding);
      this.encoding = options.encoding;
    }
  }
  function Readable2(options) {
    Duplex = Duplex || dew$7();
    if (!(this instanceof Readable2)) return new Readable2(options);
    var isDuplex = this instanceof Duplex;
    this._readableState = new ReadableState(options, this, isDuplex);
    this.readable = true;
    if (options) {
      if (typeof options.read === "function") this._read = options.read;
      if (typeof options.destroy === "function") this._destroy = options.destroy;
    }
    Stream.call(this);
  }
  Object.defineProperty(Readable2.prototype, "destroyed", {
    // making it explicit this property is not enumerable
    // because otherwise some prototype manipulation in
    // userland will fail
    enumerable: false,
    get: function get() {
      if (this._readableState === void 0) {
        return false;
      }
      return this._readableState.destroyed;
    },
    set: function set(value) {
      if (!this._readableState) {
        return;
      }
      this._readableState.destroyed = value;
    }
  });
  Readable2.prototype.destroy = destroyImpl.destroy;
  Readable2.prototype._undestroy = destroyImpl.undestroy;
  Readable2.prototype._destroy = function(err, cb) {
    cb(err);
  };
  Readable2.prototype.push = function(chunk, encoding) {
    var state = this._readableState;
    var skipChunkCheck;
    if (!state.objectMode) {
      if (typeof chunk === "string") {
        encoding = encoding || state.defaultEncoding;
        if (encoding !== state.encoding) {
          chunk = Buffer3.from(chunk, encoding);
          encoding = "";
        }
        skipChunkCheck = true;
      }
    } else {
      skipChunkCheck = true;
    }
    return readableAddChunk(this, chunk, encoding, false, skipChunkCheck);
  };
  Readable2.prototype.unshift = function(chunk) {
    return readableAddChunk(this, chunk, null, true, false);
  };
  function readableAddChunk(stream, chunk, encoding, addToFront, skipChunkCheck) {
    debug("readableAddChunk", chunk);
    var state = stream._readableState;
    if (chunk === null) {
      state.reading = false;
      onEofChunk(stream, state);
    } else {
      var er;
      if (!skipChunkCheck) er = chunkInvalid(state, chunk);
      if (er) {
        errorOrDestroy(stream, er);
      } else if (state.objectMode || chunk && chunk.length > 0) {
        if (typeof chunk !== "string" && !state.objectMode && Object.getPrototypeOf(chunk) !== Buffer3.prototype) {
          chunk = _uint8ArrayToBuffer(chunk);
        }
        if (addToFront) {
          if (state.endEmitted) errorOrDestroy(stream, new ERR_STREAM_UNSHIFT_AFTER_END_EVENT());
          else addChunk(stream, state, chunk, true);
        } else if (state.ended) {
          errorOrDestroy(stream, new ERR_STREAM_PUSH_AFTER_EOF());
        } else if (state.destroyed) {
          return false;
        } else {
          state.reading = false;
          if (state.decoder && !encoding) {
            chunk = state.decoder.write(chunk);
            if (state.objectMode || chunk.length !== 0) addChunk(stream, state, chunk, false);
            else maybeReadMore(stream, state);
          } else {
            addChunk(stream, state, chunk, false);
          }
        }
      } else if (!addToFront) {
        state.reading = false;
        maybeReadMore(stream, state);
      }
    }
    return !state.ended && (state.length < state.highWaterMark || state.length === 0);
  }
  function addChunk(stream, state, chunk, addToFront) {
    if (state.flowing && state.length === 0 && !state.sync) {
      state.awaitDrain = 0;
      stream.emit("data", chunk);
    } else {
      state.length += state.objectMode ? 1 : chunk.length;
      if (addToFront) state.buffer.unshift(chunk);
      else state.buffer.push(chunk);
      if (state.needReadable) emitReadable(stream);
    }
    maybeReadMore(stream, state);
  }
  function chunkInvalid(state, chunk) {
    var er;
    if (!_isUint8Array(chunk) && typeof chunk !== "string" && chunk !== void 0 && !state.objectMode) {
      er = new ERR_INVALID_ARG_TYPE("chunk", ["string", "Buffer", "Uint8Array"], chunk);
    }
    return er;
  }
  Readable2.prototype.isPaused = function() {
    return this._readableState.flowing === false;
  };
  Readable2.prototype.setEncoding = function(enc) {
    if (!StringDecoder) StringDecoder = e$14.StringDecoder;
    var decoder = new StringDecoder(enc);
    this._readableState.decoder = decoder;
    this._readableState.encoding = this._readableState.decoder.encoding;
    var p6 = this._readableState.buffer.head;
    var content = "";
    while (p6 !== null) {
      content += decoder.write(p6.data);
      p6 = p6.next;
    }
    this._readableState.buffer.clear();
    if (content !== "") this._readableState.buffer.push(content);
    this._readableState.length = content.length;
    return this;
  };
  var MAX_HWM = 1073741824;
  function computeNewHighWaterMark(n6) {
    if (n6 >= MAX_HWM) {
      n6 = MAX_HWM;
    } else {
      n6--;
      n6 |= n6 >>> 1;
      n6 |= n6 >>> 2;
      n6 |= n6 >>> 4;
      n6 |= n6 >>> 8;
      n6 |= n6 >>> 16;
      n6++;
    }
    return n6;
  }
  function howMuchToRead(n6, state) {
    if (n6 <= 0 || state.length === 0 && state.ended) return 0;
    if (state.objectMode) return 1;
    if (n6 !== n6) {
      if (state.flowing && state.length) return state.buffer.head.data.length;
      else return state.length;
    }
    if (n6 > state.highWaterMark) state.highWaterMark = computeNewHighWaterMark(n6);
    if (n6 <= state.length) return n6;
    if (!state.ended) {
      state.needReadable = true;
      return 0;
    }
    return state.length;
  }
  Readable2.prototype.read = function(n6) {
    debug("read", n6);
    n6 = parseInt(n6, 10);
    var state = this._readableState;
    var nOrig = n6;
    if (n6 !== 0) state.emittedReadable = false;
    if (n6 === 0 && state.needReadable && ((state.highWaterMark !== 0 ? state.length >= state.highWaterMark : state.length > 0) || state.ended)) {
      debug("read: emitReadable", state.length, state.ended);
      if (state.length === 0 && state.ended) endReadable(this);
      else emitReadable(this);
      return null;
    }
    n6 = howMuchToRead(n6, state);
    if (n6 === 0 && state.ended) {
      if (state.length === 0) endReadable(this);
      return null;
    }
    var doRead = state.needReadable;
    debug("need readable", doRead);
    if (state.length === 0 || state.length - n6 < state.highWaterMark) {
      doRead = true;
      debug("length less than watermark", doRead);
    }
    if (state.ended || state.reading) {
      doRead = false;
      debug("reading or ended", doRead);
    } else if (doRead) {
      debug("do read");
      state.reading = true;
      state.sync = true;
      if (state.length === 0) state.needReadable = true;
      this._read(state.highWaterMark);
      state.sync = false;
      if (!state.reading) n6 = howMuchToRead(nOrig, state);
    }
    var ret;
    if (n6 > 0) ret = fromList(n6, state);
    else ret = null;
    if (ret === null) {
      state.needReadable = state.length <= state.highWaterMark;
      n6 = 0;
    } else {
      state.length -= n6;
      state.awaitDrain = 0;
    }
    if (state.length === 0) {
      if (!state.ended) state.needReadable = true;
      if (nOrig !== n6 && state.ended) endReadable(this);
    }
    if (ret !== null) this.emit("data", ret);
    return ret;
  };
  function onEofChunk(stream, state) {
    debug("onEofChunk");
    if (state.ended) return;
    if (state.decoder) {
      var chunk = state.decoder.end();
      if (chunk && chunk.length) {
        state.buffer.push(chunk);
        state.length += state.objectMode ? 1 : chunk.length;
      }
    }
    state.ended = true;
    if (state.sync) {
      emitReadable(stream);
    } else {
      state.needReadable = false;
      if (!state.emittedReadable) {
        state.emittedReadable = true;
        emitReadable_(stream);
      }
    }
  }
  function emitReadable(stream) {
    var state = stream._readableState;
    debug("emitReadable", state.needReadable, state.emittedReadable);
    state.needReadable = false;
    if (!state.emittedReadable) {
      debug("emitReadable", state.flowing);
      state.emittedReadable = true;
      process$1.nextTick(emitReadable_, stream);
    }
  }
  function emitReadable_(stream) {
    var state = stream._readableState;
    debug("emitReadable_", state.destroyed, state.length, state.ended);
    if (!state.destroyed && (state.length || state.ended)) {
      stream.emit("readable");
      state.emittedReadable = false;
    }
    state.needReadable = !state.flowing && !state.ended && state.length <= state.highWaterMark;
    flow(stream);
  }
  function maybeReadMore(stream, state) {
    if (!state.readingMore) {
      state.readingMore = true;
      process$1.nextTick(maybeReadMore_, stream, state);
    }
  }
  function maybeReadMore_(stream, state) {
    while (!state.reading && !state.ended && (state.length < state.highWaterMark || state.flowing && state.length === 0)) {
      var len = state.length;
      debug("maybeReadMore read 0");
      stream.read(0);
      if (len === state.length)
        break;
    }
    state.readingMore = false;
  }
  Readable2.prototype._read = function(n6) {
    errorOrDestroy(this, new ERR_METHOD_NOT_IMPLEMENTED("_read()"));
  };
  Readable2.prototype.pipe = function(dest, pipeOpts) {
    var src = this;
    var state = this._readableState;
    switch (state.pipesCount) {
      case 0:
        state.pipes = dest;
        break;
      case 1:
        state.pipes = [state.pipes, dest];
        break;
      default:
        state.pipes.push(dest);
        break;
    }
    state.pipesCount += 1;
    debug("pipe count=%d opts=%j", state.pipesCount, pipeOpts);
    var doEnd = (!pipeOpts || pipeOpts.end !== false) && dest !== process$1.stdout && dest !== process$1.stderr;
    var endFn = doEnd ? onend : unpipe;
    if (state.endEmitted) process$1.nextTick(endFn);
    else src.once("end", endFn);
    dest.on("unpipe", onunpipe);
    function onunpipe(readable, unpipeInfo) {
      debug("onunpipe");
      if (readable === src) {
        if (unpipeInfo && unpipeInfo.hasUnpiped === false) {
          unpipeInfo.hasUnpiped = true;
          cleanup();
        }
      }
    }
    function onend() {
      debug("onend");
      dest.end();
    }
    var ondrain = pipeOnDrain(src);
    dest.on("drain", ondrain);
    var cleanedUp = false;
    function cleanup() {
      debug("cleanup");
      dest.removeListener("close", onclose);
      dest.removeListener("finish", onfinish);
      dest.removeListener("drain", ondrain);
      dest.removeListener("error", onerror);
      dest.removeListener("unpipe", onunpipe);
      src.removeListener("end", onend);
      src.removeListener("end", unpipe);
      src.removeListener("data", ondata);
      cleanedUp = true;
      if (state.awaitDrain && (!dest._writableState || dest._writableState.needDrain)) ondrain();
    }
    src.on("data", ondata);
    function ondata(chunk) {
      debug("ondata");
      var ret = dest.write(chunk);
      debug("dest.write", ret);
      if (ret === false) {
        if ((state.pipesCount === 1 && state.pipes === dest || state.pipesCount > 1 && indexOf(state.pipes, dest) !== -1) && !cleanedUp) {
          debug("false write response, pause", state.awaitDrain);
          state.awaitDrain++;
        }
        src.pause();
      }
    }
    function onerror(er) {
      debug("onerror", er);
      unpipe();
      dest.removeListener("error", onerror);
      if (EElistenerCount(dest, "error") === 0) errorOrDestroy(dest, er);
    }
    prependListener3(dest, "error", onerror);
    function onclose() {
      dest.removeListener("finish", onfinish);
      unpipe();
    }
    dest.once("close", onclose);
    function onfinish() {
      debug("onfinish");
      dest.removeListener("close", onclose);
      unpipe();
    }
    dest.once("finish", onfinish);
    function unpipe() {
      debug("unpipe");
      src.unpipe(dest);
    }
    dest.emit("pipe", src);
    if (!state.flowing) {
      debug("pipe resume");
      src.resume();
    }
    return dest;
  };
  function pipeOnDrain(src) {
    return function pipeOnDrainFunctionResult() {
      var state = src._readableState;
      debug("pipeOnDrain", state.awaitDrain);
      if (state.awaitDrain) state.awaitDrain--;
      if (state.awaitDrain === 0 && EElistenerCount(src, "data")) {
        state.flowing = true;
        flow(src);
      }
    };
  }
  Readable2.prototype.unpipe = function(dest) {
    var state = this._readableState;
    var unpipeInfo = {
      hasUnpiped: false
    };
    if (state.pipesCount === 0) return this;
    if (state.pipesCount === 1) {
      if (dest && dest !== state.pipes) return this;
      if (!dest) dest = state.pipes;
      state.pipes = null;
      state.pipesCount = 0;
      state.flowing = false;
      if (dest) dest.emit("unpipe", this, unpipeInfo);
      return this;
    }
    if (!dest) {
      var dests = state.pipes;
      var len = state.pipesCount;
      state.pipes = null;
      state.pipesCount = 0;
      state.flowing = false;
      for (var i6 = 0; i6 < len; i6++) {
        dests[i6].emit("unpipe", this, {
          hasUnpiped: false
        });
      }
      return this;
    }
    var index = indexOf(state.pipes, dest);
    if (index === -1) return this;
    state.pipes.splice(index, 1);
    state.pipesCount -= 1;
    if (state.pipesCount === 1) state.pipes = state.pipes[0];
    dest.emit("unpipe", this, unpipeInfo);
    return this;
  };
  Readable2.prototype.on = function(ev, fn) {
    var res = Stream.prototype.on.call(this, ev, fn);
    var state = this._readableState;
    if (ev === "data") {
      state.readableListening = this.listenerCount("readable") > 0;
      if (state.flowing !== false) this.resume();
    } else if (ev === "readable") {
      if (!state.endEmitted && !state.readableListening) {
        state.readableListening = state.needReadable = true;
        state.flowing = false;
        state.emittedReadable = false;
        debug("on readable", state.length, state.reading);
        if (state.length) {
          emitReadable(this);
        } else if (!state.reading) {
          process$1.nextTick(nReadingNextTick, this);
        }
      }
    }
    return res;
  };
  Readable2.prototype.addListener = Readable2.prototype.on;
  Readable2.prototype.removeListener = function(ev, fn) {
    var res = Stream.prototype.removeListener.call(this, ev, fn);
    if (ev === "readable") {
      process$1.nextTick(updateReadableListening, this);
    }
    return res;
  };
  Readable2.prototype.removeAllListeners = function(ev) {
    var res = Stream.prototype.removeAllListeners.apply(this, arguments);
    if (ev === "readable" || ev === void 0) {
      process$1.nextTick(updateReadableListening, this);
    }
    return res;
  };
  function updateReadableListening(self2) {
    var state = self2._readableState;
    state.readableListening = self2.listenerCount("readable") > 0;
    if (state.resumeScheduled && !state.paused) {
      state.flowing = true;
    } else if (self2.listenerCount("data") > 0) {
      self2.resume();
    }
  }
  function nReadingNextTick(self2) {
    debug("readable nexttick read 0");
    self2.read(0);
  }
  Readable2.prototype.resume = function() {
    var state = this._readableState;
    if (!state.flowing) {
      debug("resume");
      state.flowing = !state.readableListening;
      resume(this, state);
    }
    state.paused = false;
    return this;
  };
  function resume(stream, state) {
    if (!state.resumeScheduled) {
      state.resumeScheduled = true;
      process$1.nextTick(resume_, stream, state);
    }
  }
  function resume_(stream, state) {
    debug("resume", state.reading);
    if (!state.reading) {
      stream.read(0);
    }
    state.resumeScheduled = false;
    stream.emit("resume");
    flow(stream);
    if (state.flowing && !state.reading) stream.read(0);
  }
  Readable2.prototype.pause = function() {
    debug("call pause flowing=%j", this._readableState.flowing);
    if (this._readableState.flowing !== false) {
      debug("pause");
      this._readableState.flowing = false;
      this.emit("pause");
    }
    this._readableState.paused = true;
    return this;
  };
  function flow(stream) {
    var state = stream._readableState;
    debug("flow", state.flowing);
    while (state.flowing && stream.read() !== null) {
    }
  }
  Readable2.prototype.wrap = function(stream) {
    var _this = this;
    var state = this._readableState;
    var paused = false;
    stream.on("end", function() {
      debug("wrapped end");
      if (state.decoder && !state.ended) {
        var chunk = state.decoder.end();
        if (chunk && chunk.length) _this.push(chunk);
      }
      _this.push(null);
    });
    stream.on("data", function(chunk) {
      debug("wrapped data");
      if (state.decoder) chunk = state.decoder.write(chunk);
      if (state.objectMode && (chunk === null || chunk === void 0)) return;
      else if (!state.objectMode && (!chunk || !chunk.length)) return;
      var ret = _this.push(chunk);
      if (!ret) {
        paused = true;
        stream.pause();
      }
    });
    for (var i6 in stream) {
      if (this[i6] === void 0 && typeof stream[i6] === "function") {
        this[i6] = /* @__PURE__ */ (function methodWrap(method) {
          return function methodWrapReturnFunction() {
            return stream[method].apply(stream, arguments);
          };
        })(i6);
      }
    }
    for (var n6 = 0; n6 < kProxyEvents.length; n6++) {
      stream.on(kProxyEvents[n6], this.emit.bind(this, kProxyEvents[n6]));
    }
    this._read = function(n7) {
      debug("wrapped _read", n7);
      if (paused) {
        paused = false;
        stream.resume();
      }
    };
    return this;
  };
  if (typeof Symbol === "function") {
    Readable2.prototype[Symbol.asyncIterator] = function() {
      if (createReadableStreamAsyncIterator === void 0) {
        createReadableStreamAsyncIterator = dew$5();
      }
      return createReadableStreamAsyncIterator(this);
    };
  }
  Object.defineProperty(Readable2.prototype, "readableHighWaterMark", {
    // making it explicit this property is not enumerable
    // because otherwise some prototype manipulation in
    // userland will fail
    enumerable: false,
    get: function get() {
      return this._readableState.highWaterMark;
    }
  });
  Object.defineProperty(Readable2.prototype, "readableBuffer", {
    // making it explicit this property is not enumerable
    // because otherwise some prototype manipulation in
    // userland will fail
    enumerable: false,
    get: function get() {
      return this._readableState && this._readableState.buffer;
    }
  });
  Object.defineProperty(Readable2.prototype, "readableFlowing", {
    // making it explicit this property is not enumerable
    // because otherwise some prototype manipulation in
    // userland will fail
    enumerable: false,
    get: function get() {
      return this._readableState.flowing;
    },
    set: function set(state) {
      if (this._readableState) {
        this._readableState.flowing = state;
      }
    }
  });
  Readable2._fromList = fromList;
  Object.defineProperty(Readable2.prototype, "readableLength", {
    // making it explicit this property is not enumerable
    // because otherwise some prototype manipulation in
    // userland will fail
    enumerable: false,
    get: function get() {
      return this._readableState.length;
    }
  });
  function fromList(n6, state) {
    if (state.length === 0) return null;
    var ret;
    if (state.objectMode) ret = state.buffer.shift();
    else if (!n6 || n6 >= state.length) {
      if (state.decoder) ret = state.buffer.join("");
      else if (state.buffer.length === 1) ret = state.buffer.first();
      else ret = state.buffer.concat(state.length);
      state.buffer.clear();
    } else {
      ret = state.buffer.consume(n6, state.decoder);
    }
    return ret;
  }
  function endReadable(stream) {
    var state = stream._readableState;
    debug("endReadable", state.endEmitted);
    if (!state.endEmitted) {
      state.ended = true;
      process$1.nextTick(endReadableNT, state, stream);
    }
  }
  function endReadableNT(state, stream) {
    debug("endReadableNT", state.endEmitted, state.length);
    if (!state.endEmitted && state.length === 0) {
      state.endEmitted = true;
      stream.readable = false;
      stream.emit("end");
      if (state.autoDestroy) {
        var wState = stream._writableState;
        if (!wState || wState.autoDestroy && wState.finished) {
          stream.destroy();
        }
      }
    }
  }
  if (typeof Symbol === "function") {
    Readable2.from = function(iterable, opts) {
      if (from === void 0) {
        from = dew$4();
      }
      return from(Readable2, iterable, opts);
    };
  }
  function indexOf(xs, x4) {
    for (var i6 = 0, l6 = xs.length; i6 < l6; i6++) {
      if (xs[i6] === x4) return i6;
    }
    return -1;
  }
  return exports$3;
}
function dew$22() {
  if (_dewExec$22) return exports$23;
  _dewExec$22 = true;
  exports$23 = Transform;
  var _require$codes = dew$b().codes, ERR_METHOD_NOT_IMPLEMENTED = _require$codes.ERR_METHOD_NOT_IMPLEMENTED, ERR_MULTIPLE_CALLBACK = _require$codes.ERR_MULTIPLE_CALLBACK, ERR_TRANSFORM_ALREADY_TRANSFORMING = _require$codes.ERR_TRANSFORM_ALREADY_TRANSFORMING, ERR_TRANSFORM_WITH_LENGTH_0 = _require$codes.ERR_TRANSFORM_WITH_LENGTH_0;
  var Duplex = dew$7();
  dew$f()(Transform, Duplex);
  function afterTransform(er, data) {
    var ts = this._transformState;
    ts.transforming = false;
    var cb = ts.writecb;
    if (cb === null) {
      return this.emit("error", new ERR_MULTIPLE_CALLBACK());
    }
    ts.writechunk = null;
    ts.writecb = null;
    if (data != null)
      this.push(data);
    cb(er);
    var rs = this._readableState;
    rs.reading = false;
    if (rs.needReadable || rs.length < rs.highWaterMark) {
      this._read(rs.highWaterMark);
    }
  }
  function Transform(options) {
    if (!(this instanceof Transform)) return new Transform(options);
    Duplex.call(this, options);
    this._transformState = {
      afterTransform: afterTransform.bind(this),
      needTransform: false,
      transforming: false,
      writecb: null,
      writechunk: null,
      writeencoding: null
    };
    this._readableState.needReadable = true;
    this._readableState.sync = false;
    if (options) {
      if (typeof options.transform === "function") this._transform = options.transform;
      if (typeof options.flush === "function") this._flush = options.flush;
    }
    this.on("prefinish", prefinish);
  }
  function prefinish() {
    var _this = this;
    if (typeof this._flush === "function" && !this._readableState.destroyed) {
      this._flush(function(er, data) {
        done(_this, er, data);
      });
    } else {
      done(this, null, null);
    }
  }
  Transform.prototype.push = function(chunk, encoding) {
    this._transformState.needTransform = false;
    return Duplex.prototype.push.call(this, chunk, encoding);
  };
  Transform.prototype._transform = function(chunk, encoding, cb) {
    cb(new ERR_METHOD_NOT_IMPLEMENTED("_transform()"));
  };
  Transform.prototype._write = function(chunk, encoding, cb) {
    var ts = this._transformState;
    ts.writecb = cb;
    ts.writechunk = chunk;
    ts.writeencoding = encoding;
    if (!ts.transforming) {
      var rs = this._readableState;
      if (ts.needTransform || rs.needReadable || rs.length < rs.highWaterMark) this._read(rs.highWaterMark);
    }
  };
  Transform.prototype._read = function(n6) {
    var ts = this._transformState;
    if (ts.writechunk !== null && !ts.transforming) {
      ts.transforming = true;
      this._transform(ts.writechunk, ts.writeencoding, ts.afterTransform);
    } else {
      ts.needTransform = true;
    }
  };
  Transform.prototype._destroy = function(err, cb) {
    Duplex.prototype._destroy.call(this, err, function(err2) {
      cb(err2);
    });
  };
  function done(stream, er, data) {
    if (er) return stream.emit("error", er);
    if (data != null)
      stream.push(data);
    if (stream._writableState.length) throw new ERR_TRANSFORM_WITH_LENGTH_0();
    if (stream._transformState.transforming) throw new ERR_TRANSFORM_ALREADY_TRANSFORMING();
    return stream.push(null);
  }
  return exports$23;
}
function dew$13() {
  if (_dewExec$13) return exports$13;
  _dewExec$13 = true;
  exports$13 = PassThrough;
  var Transform = dew$22();
  dew$f()(PassThrough, Transform);
  function PassThrough(options) {
    if (!(this instanceof PassThrough)) return new PassThrough(options);
    Transform.call(this, options);
  }
  PassThrough.prototype._transform = function(chunk, encoding, cb) {
    cb(null, chunk);
  };
  return exports$13;
}
function dew4() {
  if (_dewExec4) return exports5;
  _dewExec4 = true;
  var eos;
  function once3(callback) {
    var called = false;
    return function() {
      if (called) return;
      called = true;
      callback.apply(void 0, arguments);
    };
  }
  var _require$codes = dew$b().codes, ERR_MISSING_ARGS = _require$codes.ERR_MISSING_ARGS, ERR_STREAM_DESTROYED = _require$codes.ERR_STREAM_DESTROYED;
  function noop3(err) {
    if (err) throw err;
  }
  function isRequest(stream) {
    return stream.setHeader && typeof stream.abort === "function";
  }
  function destroyer(stream, reading, writing, callback) {
    callback = once3(callback);
    var closed = false;
    stream.on("close", function() {
      closed = true;
    });
    if (eos === void 0) eos = dew$6();
    eos(stream, {
      readable: reading,
      writable: writing
    }, function(err) {
      if (err) return callback(err);
      closed = true;
      callback();
    });
    var destroyed = false;
    return function(err) {
      if (closed) return;
      if (destroyed) return;
      destroyed = true;
      if (isRequest(stream)) return stream.abort();
      if (typeof stream.destroy === "function") return stream.destroy();
      callback(err || new ERR_STREAM_DESTROYED("pipe"));
    };
  }
  function call(fn) {
    fn();
  }
  function pipe(from, to) {
    return from.pipe(to);
  }
  function popCallback(streams2) {
    if (!streams2.length) return noop3;
    if (typeof streams2[streams2.length - 1] !== "function") return noop3;
    return streams2.pop();
  }
  function pipeline() {
    for (var _len = arguments.length, streams2 = new Array(_len), _key = 0; _key < _len; _key++) {
      streams2[_key] = arguments[_key];
    }
    var callback = popCallback(streams2);
    if (Array.isArray(streams2[0])) streams2 = streams2[0];
    if (streams2.length < 2) {
      throw new ERR_MISSING_ARGS("streams");
    }
    var error2;
    var destroys = streams2.map(function(stream, i6) {
      var reading = i6 < streams2.length - 1;
      var writing = i6 > 0;
      return destroyer(stream, reading, writing, function(err) {
        if (!error2) error2 = err;
        if (err) destroys.forEach(call);
        if (reading) return;
        destroys.forEach(call);
        callback(error2);
      });
    });
    return streams2.reduce(pipe);
  }
  exports5 = pipeline;
  return exports5;
}
var r$14, t$14, e$24, n$24, o$24, a$14, h$14, a$1$1, e$1$1, n$1$1, i$14, o$1$1, j3, Y3, e5, n5, o5, u5, e$14, s5, i5, exports$2$1, _dewExec$2$1, exports$1$1, _dewExec$1$1, exports$g, _dewExec$g, buffer, exports$f, _dewExec$f, exports$e, _dewExec$e, exports$d, _dewExec$d, exports$c, _dewExec$c, exports$b, _dewExec$b, exports$a, _dewExec$a, exports$9, _dewExec$9, _global$2, exports$8, _dewExec$8, _global$1, exports$7, _dewExec$7, exports$6, _dewExec$6, exports$5, _dewExec$5, exports$4, _dewExec$4, exports$3, _dewExec$3, _global2, exports$23, _dewExec$22, exports$13, _dewExec$13, exports5, _dewExec4;
var init_chunk_B738Er4n = __esm({
  "node_modules/@jspm/core/nodelibs/browser/chunk-B738Er4n.js"() {
    init_dirname();
    init_buffer2();
    init_process2();
    init_chunk_tHuMsdT0();
    init_chunk_D3uu3VYh();
    init_chunk_b0rmRow7();
    for (r$14 = { byteLength: function(r6) {
      var t6 = u$23(r6), e6 = t6[0], n6 = t6[1];
      return 3 * (e6 + n6) / 4 - n6;
    }, toByteArray: function(r6) {
      var t6, o6, a6 = u$23(r6), h6 = a6[0], c6 = a6[1], d5 = new n$24((function(r7, t7, e6) {
        return 3 * (t7 + e6) / 4 - e6;
      })(0, h6, c6)), f6 = 0, A4 = c6 > 0 ? h6 - 4 : h6;
      for (o6 = 0; o6 < A4; o6 += 4) t6 = e$24[r6.charCodeAt(o6)] << 18 | e$24[r6.charCodeAt(o6 + 1)] << 12 | e$24[r6.charCodeAt(o6 + 2)] << 6 | e$24[r6.charCodeAt(o6 + 3)], d5[f6++] = t6 >> 16 & 255, d5[f6++] = t6 >> 8 & 255, d5[f6++] = 255 & t6;
      2 === c6 && (t6 = e$24[r6.charCodeAt(o6)] << 2 | e$24[r6.charCodeAt(o6 + 1)] >> 4, d5[f6++] = 255 & t6);
      1 === c6 && (t6 = e$24[r6.charCodeAt(o6)] << 10 | e$24[r6.charCodeAt(o6 + 1)] << 4 | e$24[r6.charCodeAt(o6 + 2)] >> 2, d5[f6++] = t6 >> 8 & 255, d5[f6++] = 255 & t6);
      return d5;
    }, fromByteArray: function(r6) {
      for (var e6, n6 = r6.length, o6 = n6 % 3, a6 = [], h6 = 0, u6 = n6 - o6; h6 < u6; h6 += 16383) a6.push(c$14(r6, h6, h6 + 16383 > u6 ? u6 : h6 + 16383));
      1 === o6 ? (e6 = r6[n6 - 1], a6.push(t$14[e6 >> 2] + t$14[e6 << 4 & 63] + "==")) : 2 === o6 && (e6 = (r6[n6 - 2] << 8) + r6[n6 - 1], a6.push(t$14[e6 >> 10] + t$14[e6 >> 4 & 63] + t$14[e6 << 2 & 63] + "="));
      return a6.join("");
    } }, t$14 = [], e$24 = [], n$24 = "undefined" != typeof Uint8Array ? Uint8Array : Array, o$24 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/", a$14 = 0, h$14 = o$24.length; a$14 < h$14; ++a$14) t$14[a$14] = o$24[a$14], e$24[o$24.charCodeAt(a$14)] = a$14;
    e$24["-".charCodeAt(0)] = 62, e$24["_".charCodeAt(0)] = 63;
    a$1$1 = { read: function(a6, t6, o6, r6, h6) {
      var M4, f6, p6 = 8 * h6 - r6 - 1, w4 = (1 << p6) - 1, e6 = w4 >> 1, i6 = -7, N4 = o6 ? h6 - 1 : 0, n6 = o6 ? -1 : 1, u6 = a6[t6 + N4];
      for (N4 += n6, M4 = u6 & (1 << -i6) - 1, u6 >>= -i6, i6 += p6; i6 > 0; M4 = 256 * M4 + a6[t6 + N4], N4 += n6, i6 -= 8) ;
      for (f6 = M4 & (1 << -i6) - 1, M4 >>= -i6, i6 += r6; i6 > 0; f6 = 256 * f6 + a6[t6 + N4], N4 += n6, i6 -= 8) ;
      if (0 === M4) M4 = 1 - e6;
      else {
        if (M4 === w4) return f6 ? NaN : 1 / 0 * (u6 ? -1 : 1);
        f6 += Math.pow(2, r6), M4 -= e6;
      }
      return (u6 ? -1 : 1) * f6 * Math.pow(2, M4 - r6);
    }, write: function(a6, t6, o6, r6, h6, M4) {
      var f6, p6, w4, e6 = 8 * M4 - h6 - 1, i6 = (1 << e6) - 1, N4 = i6 >> 1, n6 = 23 === h6 ? Math.pow(2, -24) - Math.pow(2, -77) : 0, u6 = r6 ? 0 : M4 - 1, l6 = r6 ? 1 : -1, s6 = t6 < 0 || 0 === t6 && 1 / t6 < 0 ? 1 : 0;
      for (t6 = Math.abs(t6), isNaN(t6) || t6 === 1 / 0 ? (p6 = isNaN(t6) ? 1 : 0, f6 = i6) : (f6 = Math.floor(Math.log(t6) / Math.LN2), t6 * (w4 = Math.pow(2, -f6)) < 1 && (f6--, w4 *= 2), (t6 += f6 + N4 >= 1 ? n6 / w4 : n6 * Math.pow(2, 1 - N4)) * w4 >= 2 && (f6++, w4 /= 2), f6 + N4 >= i6 ? (p6 = 0, f6 = i6) : f6 + N4 >= 1 ? (p6 = (t6 * w4 - 1) * Math.pow(2, h6), f6 += N4) : (p6 = t6 * Math.pow(2, N4 - 1) * Math.pow(2, h6), f6 = 0)); h6 >= 8; a6[o6 + u6] = 255 & p6, u6 += l6, p6 /= 256, h6 -= 8) ;
      for (f6 = f6 << h6 | p6, e6 += h6; e6 > 0; a6[o6 + u6] = 255 & f6, u6 += l6, f6 /= 256, e6 -= 8) ;
      a6[o6 + u6 - l6] |= 128 * s6;
    } };
    e$1$1 = {};
    n$1$1 = r$14;
    i$14 = a$1$1;
    o$1$1 = "function" == typeof Symbol && "function" == typeof Symbol.for ? /* @__PURE__ */ Symbol.for("nodejs.util.inspect.custom") : null;
    e$1$1.Buffer = u$1$1, e$1$1.SlowBuffer = function(t6) {
      +t6 != t6 && (t6 = 0);
      return u$1$1.alloc(+t6);
    }, e$1$1.INSPECT_MAX_BYTES = 50;
    e$1$1.kMaxLength = 2147483647, u$1$1.TYPED_ARRAY_SUPPORT = (function() {
      try {
        var t6 = new Uint8Array(1), r6 = { foo: function() {
          return 42;
        } };
        return Object.setPrototypeOf(r6, Uint8Array.prototype), Object.setPrototypeOf(t6, r6), 42 === t6.foo();
      } catch (t7) {
        return false;
      }
    })(), u$1$1.TYPED_ARRAY_SUPPORT || "undefined" == typeof console || "function" != typeof console.error || console.error("This browser lacks typed array (Uint8Array) support which is required by `buffer` v5.x. Use `buffer` v4.x if you require old browser support."), Object.defineProperty(u$1$1.prototype, "parent", { enumerable: true, get: function() {
      if (u$1$1.isBuffer(this)) return this.buffer;
    } }), Object.defineProperty(u$1$1.prototype, "offset", { enumerable: true, get: function() {
      if (u$1$1.isBuffer(this)) return this.byteOffset;
    } }), u$1$1.poolSize = 8192, u$1$1.from = function(t6, r6, e6) {
      return s$13(t6, r6, e6);
    }, Object.setPrototypeOf(u$1$1.prototype, Uint8Array.prototype), Object.setPrototypeOf(u$1$1, Uint8Array), u$1$1.alloc = function(t6, r6, e6) {
      return (function(t7, r7, e7) {
        return h$1$1(t7), t7 <= 0 ? f$22(t7) : void 0 !== r7 ? "string" == typeof e7 ? f$22(t7).fill(r7, e7) : f$22(t7).fill(r7) : f$22(t7);
      })(t6, r6, e6);
    }, u$1$1.allocUnsafe = function(t6) {
      return a$22(t6);
    }, u$1$1.allocUnsafeSlow = function(t6) {
      return a$22(t6);
    }, u$1$1.isBuffer = function(t6) {
      return null != t6 && true === t6._isBuffer && t6 !== u$1$1.prototype;
    }, u$1$1.compare = function(t6, r6) {
      if (F3(t6, Uint8Array) && (t6 = u$1$1.from(t6, t6.offset, t6.byteLength)), F3(r6, Uint8Array) && (r6 = u$1$1.from(r6, r6.offset, r6.byteLength)), !u$1$1.isBuffer(t6) || !u$1$1.isBuffer(r6)) throw new TypeError('The "buf1", "buf2" arguments must be one of type Buffer or Uint8Array');
      if (t6 === r6) return 0;
      for (var e6 = t6.length, n6 = r6.length, i6 = 0, o6 = Math.min(e6, n6); i6 < o6; ++i6) if (t6[i6] !== r6[i6]) {
        e6 = t6[i6], n6 = r6[i6];
        break;
      }
      return e6 < n6 ? -1 : n6 < e6 ? 1 : 0;
    }, u$1$1.isEncoding = function(t6) {
      switch (String(t6).toLowerCase()) {
        case "hex":
        case "utf8":
        case "utf-8":
        case "ascii":
        case "latin1":
        case "binary":
        case "base64":
        case "ucs2":
        case "ucs-2":
        case "utf16le":
        case "utf-16le":
          return true;
        default:
          return false;
      }
    }, u$1$1.concat = function(t6, r6) {
      if (!Array.isArray(t6)) throw new TypeError('"list" argument must be an Array of Buffers');
      if (0 === t6.length) return u$1$1.alloc(0);
      var e6;
      if (void 0 === r6) for (r6 = 0, e6 = 0; e6 < t6.length; ++e6) r6 += t6[e6].length;
      var n6 = u$1$1.allocUnsafe(r6), i6 = 0;
      for (e6 = 0; e6 < t6.length; ++e6) {
        var o6 = t6[e6];
        if (F3(o6, Uint8Array) && (o6 = u$1$1.from(o6)), !u$1$1.isBuffer(o6)) throw new TypeError('"list" argument must be an Array of Buffers');
        o6.copy(n6, i6), i6 += o6.length;
      }
      return n6;
    }, u$1$1.byteLength = y5, u$1$1.prototype._isBuffer = true, u$1$1.prototype.swap16 = function() {
      var t6 = this.length;
      if (t6 % 2 != 0) throw new RangeError("Buffer size must be a multiple of 16-bits");
      for (var r6 = 0; r6 < t6; r6 += 2) w3(this, r6, r6 + 1);
      return this;
    }, u$1$1.prototype.swap32 = function() {
      var t6 = this.length;
      if (t6 % 4 != 0) throw new RangeError("Buffer size must be a multiple of 32-bits");
      for (var r6 = 0; r6 < t6; r6 += 4) w3(this, r6, r6 + 3), w3(this, r6 + 1, r6 + 2);
      return this;
    }, u$1$1.prototype.swap64 = function() {
      var t6 = this.length;
      if (t6 % 8 != 0) throw new RangeError("Buffer size must be a multiple of 64-bits");
      for (var r6 = 0; r6 < t6; r6 += 8) w3(this, r6, r6 + 7), w3(this, r6 + 1, r6 + 6), w3(this, r6 + 2, r6 + 5), w3(this, r6 + 3, r6 + 4);
      return this;
    }, u$1$1.prototype.toString = function() {
      var t6 = this.length;
      return 0 === t6 ? "" : 0 === arguments.length ? I3(this, 0, t6) : g4.apply(this, arguments);
    }, u$1$1.prototype.toLocaleString = u$1$1.prototype.toString, u$1$1.prototype.equals = function(t6) {
      if (!u$1$1.isBuffer(t6)) throw new TypeError("Argument must be a Buffer");
      return this === t6 || 0 === u$1$1.compare(this, t6);
    }, u$1$1.prototype.inspect = function() {
      var t6 = "", r6 = e$1$1.INSPECT_MAX_BYTES;
      return t6 = this.toString("hex", 0, r6).replace(/(.{2})/g, "$1 ").trim(), this.length > r6 && (t6 += " ... "), "<Buffer " + t6 + ">";
    }, o$1$1 && (u$1$1.prototype[o$1$1] = u$1$1.prototype.inspect), u$1$1.prototype.compare = function(t6, r6, e6, n6, i6) {
      if (F3(t6, Uint8Array) && (t6 = u$1$1.from(t6, t6.offset, t6.byteLength)), !u$1$1.isBuffer(t6)) throw new TypeError('The "target" argument must be one of type Buffer or Uint8Array. Received type ' + typeof t6);
      if (void 0 === r6 && (r6 = 0), void 0 === e6 && (e6 = t6 ? t6.length : 0), void 0 === n6 && (n6 = 0), void 0 === i6 && (i6 = this.length), r6 < 0 || e6 > t6.length || n6 < 0 || i6 > this.length) throw new RangeError("out of range index");
      if (n6 >= i6 && r6 >= e6) return 0;
      if (n6 >= i6) return -1;
      if (r6 >= e6) return 1;
      if (this === t6) return 0;
      for (var o6 = (i6 >>>= 0) - (n6 >>>= 0), f6 = (e6 >>>= 0) - (r6 >>>= 0), s6 = Math.min(o6, f6), h6 = this.slice(n6, i6), a6 = t6.slice(r6, e6), p6 = 0; p6 < s6; ++p6) if (h6[p6] !== a6[p6]) {
        o6 = h6[p6], f6 = a6[p6];
        break;
      }
      return o6 < f6 ? -1 : f6 < o6 ? 1 : 0;
    }, u$1$1.prototype.includes = function(t6, r6, e6) {
      return -1 !== this.indexOf(t6, r6, e6);
    }, u$1$1.prototype.indexOf = function(t6, r6, e6) {
      return d4(this, t6, r6, e6, true);
    }, u$1$1.prototype.lastIndexOf = function(t6, r6, e6) {
      return d4(this, t6, r6, e6, false);
    }, u$1$1.prototype.write = function(t6, r6, e6, n6) {
      if (void 0 === r6) n6 = "utf8", e6 = this.length, r6 = 0;
      else if (void 0 === e6 && "string" == typeof r6) n6 = r6, e6 = this.length, r6 = 0;
      else {
        if (!isFinite(r6)) throw new Error("Buffer.write(string, encoding, offset[, length]) is no longer supported");
        r6 >>>= 0, isFinite(e6) ? (e6 >>>= 0, void 0 === n6 && (n6 = "utf8")) : (n6 = e6, e6 = void 0);
      }
      var i6 = this.length - r6;
      if ((void 0 === e6 || e6 > i6) && (e6 = i6), t6.length > 0 && (e6 < 0 || r6 < 0) || r6 > this.length) throw new RangeError("Attempt to write outside buffer bounds");
      n6 || (n6 = "utf8");
      for (var o6 = false; ; ) switch (n6) {
        case "hex":
          return b4(this, t6, r6, e6);
        case "utf8":
        case "utf-8":
          return m4(this, t6, r6, e6);
        case "ascii":
          return E3(this, t6, r6, e6);
        case "latin1":
        case "binary":
          return B3(this, t6, r6, e6);
        case "base64":
          return A3(this, t6, r6, e6);
        case "ucs2":
        case "ucs-2":
        case "utf16le":
        case "utf-16le":
          return U3(this, t6, r6, e6);
        default:
          if (o6) throw new TypeError("Unknown encoding: " + n6);
          n6 = ("" + n6).toLowerCase(), o6 = true;
      }
    }, u$1$1.prototype.toJSON = function() {
      return { type: "Buffer", data: Array.prototype.slice.call(this._arr || this, 0) };
    };
    u$1$1.prototype.slice = function(t6, r6) {
      var e6 = this.length;
      (t6 = ~~t6) < 0 ? (t6 += e6) < 0 && (t6 = 0) : t6 > e6 && (t6 = e6), (r6 = void 0 === r6 ? e6 : ~~r6) < 0 ? (r6 += e6) < 0 && (r6 = 0) : r6 > e6 && (r6 = e6), r6 < t6 && (r6 = t6);
      var n6 = this.subarray(t6, r6);
      return Object.setPrototypeOf(n6, u$1$1.prototype), n6;
    }, u$1$1.prototype.readUIntLE = function(t6, r6, e6) {
      t6 >>>= 0, r6 >>>= 0, e6 || x3(t6, r6, this.length);
      for (var n6 = this[t6], i6 = 1, o6 = 0; ++o6 < r6 && (i6 *= 256); ) n6 += this[t6 + o6] * i6;
      return n6;
    }, u$1$1.prototype.readUIntBE = function(t6, r6, e6) {
      t6 >>>= 0, r6 >>>= 0, e6 || x3(t6, r6, this.length);
      for (var n6 = this[t6 + --r6], i6 = 1; r6 > 0 && (i6 *= 256); ) n6 += this[t6 + --r6] * i6;
      return n6;
    }, u$1$1.prototype.readUInt8 = function(t6, r6) {
      return t6 >>>= 0, r6 || x3(t6, 1, this.length), this[t6];
    }, u$1$1.prototype.readUInt16LE = function(t6, r6) {
      return t6 >>>= 0, r6 || x3(t6, 2, this.length), this[t6] | this[t6 + 1] << 8;
    }, u$1$1.prototype.readUInt16BE = function(t6, r6) {
      return t6 >>>= 0, r6 || x3(t6, 2, this.length), this[t6] << 8 | this[t6 + 1];
    }, u$1$1.prototype.readUInt32LE = function(t6, r6) {
      return t6 >>>= 0, r6 || x3(t6, 4, this.length), (this[t6] | this[t6 + 1] << 8 | this[t6 + 2] << 16) + 16777216 * this[t6 + 3];
    }, u$1$1.prototype.readUInt32BE = function(t6, r6) {
      return t6 >>>= 0, r6 || x3(t6, 4, this.length), 16777216 * this[t6] + (this[t6 + 1] << 16 | this[t6 + 2] << 8 | this[t6 + 3]);
    }, u$1$1.prototype.readIntLE = function(t6, r6, e6) {
      t6 >>>= 0, r6 >>>= 0, e6 || x3(t6, r6, this.length);
      for (var n6 = this[t6], i6 = 1, o6 = 0; ++o6 < r6 && (i6 *= 256); ) n6 += this[t6 + o6] * i6;
      return n6 >= (i6 *= 128) && (n6 -= Math.pow(2, 8 * r6)), n6;
    }, u$1$1.prototype.readIntBE = function(t6, r6, e6) {
      t6 >>>= 0, r6 >>>= 0, e6 || x3(t6, r6, this.length);
      for (var n6 = r6, i6 = 1, o6 = this[t6 + --n6]; n6 > 0 && (i6 *= 256); ) o6 += this[t6 + --n6] * i6;
      return o6 >= (i6 *= 128) && (o6 -= Math.pow(2, 8 * r6)), o6;
    }, u$1$1.prototype.readInt8 = function(t6, r6) {
      return t6 >>>= 0, r6 || x3(t6, 1, this.length), 128 & this[t6] ? -1 * (255 - this[t6] + 1) : this[t6];
    }, u$1$1.prototype.readInt16LE = function(t6, r6) {
      t6 >>>= 0, r6 || x3(t6, 2, this.length);
      var e6 = this[t6] | this[t6 + 1] << 8;
      return 32768 & e6 ? 4294901760 | e6 : e6;
    }, u$1$1.prototype.readInt16BE = function(t6, r6) {
      t6 >>>= 0, r6 || x3(t6, 2, this.length);
      var e6 = this[t6 + 1] | this[t6] << 8;
      return 32768 & e6 ? 4294901760 | e6 : e6;
    }, u$1$1.prototype.readInt32LE = function(t6, r6) {
      return t6 >>>= 0, r6 || x3(t6, 4, this.length), this[t6] | this[t6 + 1] << 8 | this[t6 + 2] << 16 | this[t6 + 3] << 24;
    }, u$1$1.prototype.readInt32BE = function(t6, r6) {
      return t6 >>>= 0, r6 || x3(t6, 4, this.length), this[t6] << 24 | this[t6 + 1] << 16 | this[t6 + 2] << 8 | this[t6 + 3];
    }, u$1$1.prototype.readFloatLE = function(t6, r6) {
      return t6 >>>= 0, r6 || x3(t6, 4, this.length), i$14.read(this, t6, true, 23, 4);
    }, u$1$1.prototype.readFloatBE = function(t6, r6) {
      return t6 >>>= 0, r6 || x3(t6, 4, this.length), i$14.read(this, t6, false, 23, 4);
    }, u$1$1.prototype.readDoubleLE = function(t6, r6) {
      return t6 >>>= 0, r6 || x3(t6, 8, this.length), i$14.read(this, t6, true, 52, 8);
    }, u$1$1.prototype.readDoubleBE = function(t6, r6) {
      return t6 >>>= 0, r6 || x3(t6, 8, this.length), i$14.read(this, t6, false, 52, 8);
    }, u$1$1.prototype.writeUIntLE = function(t6, r6, e6, n6) {
      (t6 = +t6, r6 >>>= 0, e6 >>>= 0, n6) || C3(this, t6, r6, e6, Math.pow(2, 8 * e6) - 1, 0);
      var i6 = 1, o6 = 0;
      for (this[r6] = 255 & t6; ++o6 < e6 && (i6 *= 256); ) this[r6 + o6] = t6 / i6 & 255;
      return r6 + e6;
    }, u$1$1.prototype.writeUIntBE = function(t6, r6, e6, n6) {
      (t6 = +t6, r6 >>>= 0, e6 >>>= 0, n6) || C3(this, t6, r6, e6, Math.pow(2, 8 * e6) - 1, 0);
      var i6 = e6 - 1, o6 = 1;
      for (this[r6 + i6] = 255 & t6; --i6 >= 0 && (o6 *= 256); ) this[r6 + i6] = t6 / o6 & 255;
      return r6 + e6;
    }, u$1$1.prototype.writeUInt8 = function(t6, r6, e6) {
      return t6 = +t6, r6 >>>= 0, e6 || C3(this, t6, r6, 1, 255, 0), this[r6] = 255 & t6, r6 + 1;
    }, u$1$1.prototype.writeUInt16LE = function(t6, r6, e6) {
      return t6 = +t6, r6 >>>= 0, e6 || C3(this, t6, r6, 2, 65535, 0), this[r6] = 255 & t6, this[r6 + 1] = t6 >>> 8, r6 + 2;
    }, u$1$1.prototype.writeUInt16BE = function(t6, r6, e6) {
      return t6 = +t6, r6 >>>= 0, e6 || C3(this, t6, r6, 2, 65535, 0), this[r6] = t6 >>> 8, this[r6 + 1] = 255 & t6, r6 + 2;
    }, u$1$1.prototype.writeUInt32LE = function(t6, r6, e6) {
      return t6 = +t6, r6 >>>= 0, e6 || C3(this, t6, r6, 4, 4294967295, 0), this[r6 + 3] = t6 >>> 24, this[r6 + 2] = t6 >>> 16, this[r6 + 1] = t6 >>> 8, this[r6] = 255 & t6, r6 + 4;
    }, u$1$1.prototype.writeUInt32BE = function(t6, r6, e6) {
      return t6 = +t6, r6 >>>= 0, e6 || C3(this, t6, r6, 4, 4294967295, 0), this[r6] = t6 >>> 24, this[r6 + 1] = t6 >>> 16, this[r6 + 2] = t6 >>> 8, this[r6 + 3] = 255 & t6, r6 + 4;
    }, u$1$1.prototype.writeIntLE = function(t6, r6, e6, n6) {
      if (t6 = +t6, r6 >>>= 0, !n6) {
        var i6 = Math.pow(2, 8 * e6 - 1);
        C3(this, t6, r6, e6, i6 - 1, -i6);
      }
      var o6 = 0, f6 = 1, u6 = 0;
      for (this[r6] = 255 & t6; ++o6 < e6 && (f6 *= 256); ) t6 < 0 && 0 === u6 && 0 !== this[r6 + o6 - 1] && (u6 = 1), this[r6 + o6] = (t6 / f6 >> 0) - u6 & 255;
      return r6 + e6;
    }, u$1$1.prototype.writeIntBE = function(t6, r6, e6, n6) {
      if (t6 = +t6, r6 >>>= 0, !n6) {
        var i6 = Math.pow(2, 8 * e6 - 1);
        C3(this, t6, r6, e6, i6 - 1, -i6);
      }
      var o6 = e6 - 1, f6 = 1, u6 = 0;
      for (this[r6 + o6] = 255 & t6; --o6 >= 0 && (f6 *= 256); ) t6 < 0 && 0 === u6 && 0 !== this[r6 + o6 + 1] && (u6 = 1), this[r6 + o6] = (t6 / f6 >> 0) - u6 & 255;
      return r6 + e6;
    }, u$1$1.prototype.writeInt8 = function(t6, r6, e6) {
      return t6 = +t6, r6 >>>= 0, e6 || C3(this, t6, r6, 1, 127, -128), t6 < 0 && (t6 = 255 + t6 + 1), this[r6] = 255 & t6, r6 + 1;
    }, u$1$1.prototype.writeInt16LE = function(t6, r6, e6) {
      return t6 = +t6, r6 >>>= 0, e6 || C3(this, t6, r6, 2, 32767, -32768), this[r6] = 255 & t6, this[r6 + 1] = t6 >>> 8, r6 + 2;
    }, u$1$1.prototype.writeInt16BE = function(t6, r6, e6) {
      return t6 = +t6, r6 >>>= 0, e6 || C3(this, t6, r6, 2, 32767, -32768), this[r6] = t6 >>> 8, this[r6 + 1] = 255 & t6, r6 + 2;
    }, u$1$1.prototype.writeInt32LE = function(t6, r6, e6) {
      return t6 = +t6, r6 >>>= 0, e6 || C3(this, t6, r6, 4, 2147483647, -2147483648), this[r6] = 255 & t6, this[r6 + 1] = t6 >>> 8, this[r6 + 2] = t6 >>> 16, this[r6 + 3] = t6 >>> 24, r6 + 4;
    }, u$1$1.prototype.writeInt32BE = function(t6, r6, e6) {
      return t6 = +t6, r6 >>>= 0, e6 || C3(this, t6, r6, 4, 2147483647, -2147483648), t6 < 0 && (t6 = 4294967295 + t6 + 1), this[r6] = t6 >>> 24, this[r6 + 1] = t6 >>> 16, this[r6 + 2] = t6 >>> 8, this[r6 + 3] = 255 & t6, r6 + 4;
    }, u$1$1.prototype.writeFloatLE = function(t6, r6, e6) {
      return k3(this, t6, r6, true, e6);
    }, u$1$1.prototype.writeFloatBE = function(t6, r6, e6) {
      return k3(this, t6, r6, false, e6);
    }, u$1$1.prototype.writeDoubleLE = function(t6, r6, e6) {
      return M3(this, t6, r6, true, e6);
    }, u$1$1.prototype.writeDoubleBE = function(t6, r6, e6) {
      return M3(this, t6, r6, false, e6);
    }, u$1$1.prototype.copy = function(t6, r6, e6, n6) {
      if (!u$1$1.isBuffer(t6)) throw new TypeError("argument should be a Buffer");
      if (e6 || (e6 = 0), n6 || 0 === n6 || (n6 = this.length), r6 >= t6.length && (r6 = t6.length), r6 || (r6 = 0), n6 > 0 && n6 < e6 && (n6 = e6), n6 === e6) return 0;
      if (0 === t6.length || 0 === this.length) return 0;
      if (r6 < 0) throw new RangeError("targetStart out of bounds");
      if (e6 < 0 || e6 >= this.length) throw new RangeError("Index out of range");
      if (n6 < 0) throw new RangeError("sourceEnd out of bounds");
      n6 > this.length && (n6 = this.length), t6.length - r6 < n6 - e6 && (n6 = t6.length - r6 + e6);
      var i6 = n6 - e6;
      if (this === t6 && "function" == typeof Uint8Array.prototype.copyWithin) this.copyWithin(r6, e6, n6);
      else if (this === t6 && e6 < r6 && r6 < n6) for (var o6 = i6 - 1; o6 >= 0; --o6) t6[o6 + r6] = this[o6 + e6];
      else Uint8Array.prototype.set.call(t6, this.subarray(e6, n6), r6);
      return i6;
    }, u$1$1.prototype.fill = function(t6, r6, e6, n6) {
      if ("string" == typeof t6) {
        if ("string" == typeof r6 ? (n6 = r6, r6 = 0, e6 = this.length) : "string" == typeof e6 && (n6 = e6, e6 = this.length), void 0 !== n6 && "string" != typeof n6) throw new TypeError("encoding must be a string");
        if ("string" == typeof n6 && !u$1$1.isEncoding(n6)) throw new TypeError("Unknown encoding: " + n6);
        if (1 === t6.length) {
          var i6 = t6.charCodeAt(0);
          ("utf8" === n6 && i6 < 128 || "latin1" === n6) && (t6 = i6);
        }
      } else "number" == typeof t6 ? t6 &= 255 : "boolean" == typeof t6 && (t6 = Number(t6));
      if (r6 < 0 || this.length < r6 || this.length < e6) throw new RangeError("Out of range index");
      if (e6 <= r6) return this;
      var o6;
      if (r6 >>>= 0, e6 = void 0 === e6 ? this.length : e6 >>> 0, t6 || (t6 = 0), "number" == typeof t6) for (o6 = r6; o6 < e6; ++o6) this[o6] = t6;
      else {
        var f6 = u$1$1.isBuffer(t6) ? t6 : u$1$1.from(t6, n6), s6 = f6.length;
        if (0 === s6) throw new TypeError('The value "' + t6 + '" is invalid for argument "value"');
        for (o6 = 0; o6 < e6 - r6; ++o6) this[o6 + r6] = f6[o6 % s6];
      }
      return this;
    };
    j3 = /[^+/0-9A-Za-z-_]/g;
    Y3 = (function() {
      for (var t6 = new Array(256), r6 = 0; r6 < 16; ++r6) for (var e6 = 16 * r6, n6 = 0; n6 < 16; ++n6) t6[e6 + n6] = "0123456789abcdef"[r6] + "0123456789abcdef"[n6];
      return t6;
    })();
    e$1$1.Buffer;
    e$1$1.INSPECT_MAX_BYTES;
    e$1$1.kMaxLength;
    e5 = {};
    n5 = e$1$1;
    o5 = n5.Buffer;
    o5.from && o5.alloc && o5.allocUnsafe && o5.allocUnsafeSlow ? e5 = n5 : (t5(n5, e5), e5.Buffer = f5), f5.prototype = Object.create(o5.prototype), t5(o5, f5), f5.from = function(r6, e6, n6) {
      if ("number" == typeof r6) throw new TypeError("Argument must not be a number");
      return o5(r6, e6, n6);
    }, f5.alloc = function(r6, e6, n6) {
      if ("number" != typeof r6) throw new TypeError("Argument must be a number");
      var t6 = o5(r6);
      return void 0 !== e6 ? "string" == typeof n6 ? t6.fill(e6, n6) : t6.fill(e6) : t6.fill(0), t6;
    }, f5.allocUnsafe = function(r6) {
      if ("number" != typeof r6) throw new TypeError("Argument must be a number");
      return o5(r6);
    }, f5.allocUnsafeSlow = function(r6) {
      if ("number" != typeof r6) throw new TypeError("Argument must be a number");
      return n5.SlowBuffer(r6);
    };
    u5 = e5;
    e$14 = {};
    s5 = u5.Buffer;
    i5 = s5.isEncoding || function(t6) {
      switch ((t6 = "" + t6) && t6.toLowerCase()) {
        case "hex":
        case "utf8":
        case "utf-8":
        case "ascii":
        case "binary":
        case "base64":
        case "ucs2":
        case "ucs-2":
        case "utf16le":
        case "utf-16le":
        case "raw":
          return true;
        default:
          return false;
      }
    };
    e$14.StringDecoder = a5, a5.prototype.write = function(t6) {
      if (0 === t6.length) return "";
      var e6, s6;
      if (this.lastNeed) {
        if (void 0 === (e6 = this.fillLast(t6))) return "";
        s6 = this.lastNeed, this.lastNeed = 0;
      } else s6 = 0;
      return s6 < t6.length ? e6 ? e6 + this.text(t6, s6) : this.text(t6, s6) : e6 || "";
    }, a5.prototype.end = function(t6) {
      var e6 = t6 && t6.length ? this.write(t6) : "";
      return this.lastNeed ? e6 + "\uFFFD" : e6;
    }, a5.prototype.text = function(t6, e6) {
      var s6 = (function(t7, e7, s7) {
        var i7 = e7.length - 1;
        if (i7 < s7) return 0;
        var a6 = r5(e7[i7]);
        if (a6 >= 0) return a6 > 0 && (t7.lastNeed = a6 - 1), a6;
        if (--i7 < s7 || -2 === a6) return 0;
        if ((a6 = r5(e7[i7])) >= 0) return a6 > 0 && (t7.lastNeed = a6 - 2), a6;
        if (--i7 < s7 || -2 === a6) return 0;
        if ((a6 = r5(e7[i7])) >= 0) return a6 > 0 && (2 === a6 ? a6 = 0 : t7.lastNeed = a6 - 3), a6;
        return 0;
      })(this, t6, e6);
      if (!this.lastNeed) return t6.toString("utf8", e6);
      this.lastTotal = s6;
      var i6 = t6.length - (s6 - this.lastNeed);
      return t6.copy(this.lastChar, 0, i6), t6.toString("utf8", e6, i6);
    }, a5.prototype.fillLast = function(t6) {
      if (this.lastNeed <= t6.length) return t6.copy(this.lastChar, this.lastTotal - this.lastNeed, 0, this.lastNeed), this.lastChar.toString(this.encoding, 0, this.lastTotal);
      t6.copy(this.lastChar, this.lastTotal - this.lastNeed, 0, t6.length), this.lastNeed -= t6.length;
    };
    exports$2$1 = {};
    _dewExec$2$1 = false;
    exports$1$1 = {};
    _dewExec$1$1 = false;
    exports$g = {};
    _dewExec$g = false;
    buffer = dew$g();
    buffer.Buffer;
    buffer.INSPECT_MAX_BYTES;
    buffer.kMaxLength;
    exports$f = {};
    _dewExec$f = false;
    exports$e = {};
    _dewExec$e = false;
    exports$d = {};
    _dewExec$d = false;
    exports$c = {};
    _dewExec$c = false;
    exports$b = {};
    _dewExec$b = false;
    exports$a = {};
    _dewExec$a = false;
    exports$9 = {};
    _dewExec$9 = false;
    _global$2 = typeof globalThis !== "undefined" ? globalThis : typeof self !== "undefined" ? self : global;
    exports$8 = {};
    _dewExec$8 = false;
    _global$1 = typeof globalThis !== "undefined" ? globalThis : typeof self !== "undefined" ? self : global;
    exports$7 = {};
    _dewExec$7 = false;
    exports$6 = {};
    _dewExec$6 = false;
    exports$5 = {};
    _dewExec$5 = false;
    exports$4 = {};
    _dewExec$4 = false;
    exports$3 = {};
    _dewExec$3 = false;
    _global2 = typeof globalThis !== "undefined" ? globalThis : typeof self !== "undefined" ? self : global;
    exports$23 = {};
    _dewExec$22 = false;
    exports$13 = {};
    _dewExec$13 = false;
    exports5 = {};
    _dewExec4 = false;
  }
});

// node_modules/@jspm/core/nodelibs/browser/chunk-B6-G-Ftj.js
function dew5() {
  if (_dewExec5) return exports$14;
  _dewExec5 = true;
  exports$14 = Stream;
  var EE = y4.EventEmitter;
  var inherits = dew$f();
  inherits(Stream, EE);
  Stream.Readable = dew$3();
  Stream.Writable = dew$8();
  Stream.Duplex = dew$7();
  Stream.Transform = dew$22();
  Stream.PassThrough = dew$13();
  Stream.finished = dew$6();
  Stream.pipeline = dew4();
  Stream.Stream = Stream;
  function Stream() {
    EE.call(this || _global3);
  }
  Stream.prototype.pipe = function(dest, options) {
    var source = this || _global3;
    function ondata(chunk) {
      if (dest.writable) {
        if (false === dest.write(chunk) && source.pause) {
          source.pause();
        }
      }
    }
    source.on("data", ondata);
    function ondrain() {
      if (source.readable && source.resume) {
        source.resume();
      }
    }
    dest.on("drain", ondrain);
    if (!dest._isStdio && (!options || options.end !== false)) {
      source.on("end", onend);
      source.on("close", onclose);
    }
    var didOnEnd = false;
    function onend() {
      if (didOnEnd) return;
      didOnEnd = true;
      dest.end();
    }
    function onclose() {
      if (didOnEnd) return;
      didOnEnd = true;
      if (typeof dest.destroy === "function") dest.destroy();
    }
    function onerror(er) {
      cleanup();
      if (EE.listenerCount(this || _global3, "error") === 0) {
        throw er;
      }
    }
    source.on("error", onerror);
    dest.on("error", onerror);
    function cleanup() {
      source.removeListener("data", ondata);
      dest.removeListener("drain", ondrain);
      source.removeListener("end", onend);
      source.removeListener("close", onclose);
      source.removeListener("error", onerror);
      dest.removeListener("error", onerror);
      source.removeListener("end", cleanup);
      source.removeListener("close", cleanup);
      dest.removeListener("close", cleanup);
    }
    source.on("end", cleanup);
    source.on("close", cleanup);
    dest.on("close", cleanup);
    dest.emit("pipe", source);
    return dest;
  };
  return exports$14;
}
var exports$14, _dewExec5, _global3, exports6, Readable;
var init_chunk_B6_G_Ftj = __esm({
  "node_modules/@jspm/core/nodelibs/browser/chunk-B6-G-Ftj.js"() {
    init_dirname();
    init_buffer2();
    init_process2();
    init_chunk_DtDiafJB();
    init_chunk_B738Er4n();
    init_chunk_tHuMsdT0();
    init_chunk_CbQqNoLO();
    init_chunk_D3uu3VYh();
    init_chunk_b0rmRow7();
    exports$14 = {};
    _dewExec5 = false;
    _global3 = typeof globalThis !== "undefined" ? globalThis : typeof self !== "undefined" ? self : global;
    exports6 = dew5();
    Readable = exports6.Readable;
    Readable.wrap = function(src, options) {
      options = Object.assign({ objectMode: src.readableObjectMode != null || src.objectMode != null || true }, options);
      options.destroy = function(err, callback) {
        src.destroy(err);
        callback(err);
      };
      return new Readable(options).wrap(src);
    };
    exports6.Writable;
    exports6.Duplex;
    exports6.Transform;
    exports6.PassThrough;
    exports6.finished;
    exports6.pipeline;
    exports6.Stream;
    ({
      finished: promisify2(exports6.finished),
      pipeline: promisify2(exports6.pipeline)
    });
  }
});

// node_modules/@jspm/core/nodelibs/browser/punycode.js
function dew6() {
  if (_dewExec6) return exports$15;
  _dewExec6 = true;
  const maxInt = 2147483647;
  const base = 36;
  const tMin = 1;
  const tMax = 26;
  const skew = 38;
  const damp = 700;
  const initialBias = 72;
  const initialN = 128;
  const delimiter = "-";
  const regexPunycode = /^xn--/;
  const regexNonASCII = /[^\0-\x7F]/;
  const regexSeparators = /[\x2E\u3002\uFF0E\uFF61]/g;
  const errors = {
    "overflow": "Overflow: input needs wider integers to process",
    "not-basic": "Illegal input >= 0x80 (not a basic code point)",
    "invalid-input": "Invalid input"
  };
  const baseMinusTMin = base - tMin;
  const floor = Math.floor;
  const stringFromCharCode = String.fromCharCode;
  function error2(type) {
    throw new RangeError(errors[type]);
  }
  function map(array, callback) {
    const result = [];
    let length = array.length;
    while (length--) {
      result[length] = callback(array[length]);
    }
    return result;
  }
  function mapDomain(domain3, callback) {
    const parts = domain3.split("@");
    let result = "";
    if (parts.length > 1) {
      result = parts[0] + "@";
      domain3 = parts[1];
    }
    domain3 = domain3.replace(regexSeparators, ".");
    const labels = domain3.split(".");
    const encoded = map(labels, callback).join(".");
    return result + encoded;
  }
  function ucs2decode(string) {
    const output = [];
    let counter = 0;
    const length = string.length;
    while (counter < length) {
      const value = string.charCodeAt(counter++);
      if (value >= 55296 && value <= 56319 && counter < length) {
        const extra = string.charCodeAt(counter++);
        if ((extra & 64512) == 56320) {
          output.push(((value & 1023) << 10) + (extra & 1023) + 65536);
        } else {
          output.push(value);
          counter--;
        }
      } else {
        output.push(value);
      }
    }
    return output;
  }
  const ucs2encode = (codePoints) => String.fromCodePoint(...codePoints);
  const basicToDigit = function(codePoint) {
    if (codePoint >= 48 && codePoint < 58) {
      return 26 + (codePoint - 48);
    }
    if (codePoint >= 65 && codePoint < 91) {
      return codePoint - 65;
    }
    if (codePoint >= 97 && codePoint < 123) {
      return codePoint - 97;
    }
    return base;
  };
  const digitToBasic = function(digit, flag) {
    return digit + 22 + 75 * (digit < 26) - ((flag != 0) << 5);
  };
  const adapt = function(delta, numPoints, firstTime) {
    let k4 = 0;
    delta = firstTime ? floor(delta / damp) : delta >> 1;
    delta += floor(delta / numPoints);
    for (; delta > baseMinusTMin * tMax >> 1; k4 += base) {
      delta = floor(delta / baseMinusTMin);
    }
    return floor(k4 + (baseMinusTMin + 1) * delta / (delta + skew));
  };
  const decode2 = function(input) {
    const output = [];
    const inputLength = input.length;
    let i6 = 0;
    let n6 = initialN;
    let bias = initialBias;
    let basic = input.lastIndexOf(delimiter);
    if (basic < 0) {
      basic = 0;
    }
    for (let j4 = 0; j4 < basic; ++j4) {
      if (input.charCodeAt(j4) >= 128) {
        error2("not-basic");
      }
      output.push(input.charCodeAt(j4));
    }
    for (let index = basic > 0 ? basic + 1 : 0; index < inputLength; ) {
      const oldi = i6;
      for (let w4 = 1, k4 = base; ; k4 += base) {
        if (index >= inputLength) {
          error2("invalid-input");
        }
        const digit = basicToDigit(input.charCodeAt(index++));
        if (digit >= base) {
          error2("invalid-input");
        }
        if (digit > floor((maxInt - i6) / w4)) {
          error2("overflow");
        }
        i6 += digit * w4;
        const t6 = k4 <= bias ? tMin : k4 >= bias + tMax ? tMax : k4 - bias;
        if (digit < t6) {
          break;
        }
        const baseMinusT = base - t6;
        if (w4 > floor(maxInt / baseMinusT)) {
          error2("overflow");
        }
        w4 *= baseMinusT;
      }
      const out = output.length + 1;
      bias = adapt(i6 - oldi, out, oldi == 0);
      if (floor(i6 / out) > maxInt - n6) {
        error2("overflow");
      }
      n6 += floor(i6 / out);
      i6 %= out;
      output.splice(i6++, 0, n6);
    }
    return String.fromCodePoint(...output);
  };
  const encode2 = function(input) {
    const output = [];
    input = ucs2decode(input);
    const inputLength = input.length;
    let n6 = initialN;
    let delta = 0;
    let bias = initialBias;
    for (const currentValue of input) {
      if (currentValue < 128) {
        output.push(stringFromCharCode(currentValue));
      }
    }
    const basicLength = output.length;
    let handledCPCount = basicLength;
    if (basicLength) {
      output.push(delimiter);
    }
    while (handledCPCount < inputLength) {
      let m5 = maxInt;
      for (const currentValue of input) {
        if (currentValue >= n6 && currentValue < m5) {
          m5 = currentValue;
        }
      }
      const handledCPCountPlusOne = handledCPCount + 1;
      if (m5 - n6 > floor((maxInt - delta) / handledCPCountPlusOne)) {
        error2("overflow");
      }
      delta += (m5 - n6) * handledCPCountPlusOne;
      n6 = m5;
      for (const currentValue of input) {
        if (currentValue < n6 && ++delta > maxInt) {
          error2("overflow");
        }
        if (currentValue === n6) {
          let q3 = delta;
          for (let k4 = base; ; k4 += base) {
            const t6 = k4 <= bias ? tMin : k4 >= bias + tMax ? tMax : k4 - bias;
            if (q3 < t6) {
              break;
            }
            const qMinusT = q3 - t6;
            const baseMinusT = base - t6;
            output.push(stringFromCharCode(digitToBasic(t6 + qMinusT % baseMinusT, 0)));
            q3 = floor(qMinusT / baseMinusT);
          }
          output.push(stringFromCharCode(digitToBasic(q3, 0)));
          bias = adapt(delta, handledCPCountPlusOne, handledCPCount === basicLength);
          delta = 0;
          ++handledCPCount;
        }
      }
      ++delta;
      ++n6;
    }
    return output.join("");
  };
  const toUnicode2 = function(input) {
    return mapDomain(input, function(string) {
      return regexPunycode.test(string) ? decode2(string.slice(4).toLowerCase()) : string;
    });
  };
  const toASCII2 = function(input) {
    return mapDomain(input, function(string) {
      return regexNonASCII.test(string) ? "xn--" + encode2(string) : string;
    });
  };
  const punycode = {
    /**
     * A string representing the current Punycode.js version number.
     * @memberOf punycode
     * @type String
     */
    "version": "2.3.1",
    /**
     * An object of methods to convert from JavaScript's internal character
     * representation (UCS-2) to Unicode code points, and back.
     * @see <https://mathiasbynens.be/notes/javascript-encoding>
     * @memberOf punycode
     * @type Object
     */
    "ucs2": {
      "decode": ucs2decode,
      "encode": ucs2encode
    },
    "decode": decode2,
    "encode": encode2,
    "toASCII": toASCII2,
    "toUnicode": toUnicode2
  };
  exports$15 = punycode;
  return exports$15;
}
var exports$15, _dewExec6, exports7, decode, encode, toASCII, toUnicode, ucs2, version3;
var init_punycode = __esm({
  "node_modules/@jspm/core/nodelibs/browser/punycode.js"() {
    init_dirname();
    init_buffer2();
    init_process2();
    exports$15 = {};
    _dewExec6 = false;
    exports7 = dew6();
    decode = exports7.decode;
    encode = exports7.encode;
    toASCII = exports7.toASCII;
    toUnicode = exports7.toUnicode;
    ucs2 = exports7.ucs2;
    version3 = exports7.version;
  }
});

// node_modules/@jspm/core/nodelibs/browser/chunk-DtcTpLWz.js
function dew$k() {
  if (_dewExec$k) return exports$k;
  _dewExec$k = true;
  exports$k = function hasSymbols() {
    if (typeof Symbol !== "function" || typeof Object.getOwnPropertySymbols !== "function") {
      return false;
    }
    if (typeof Symbol.iterator === "symbol") {
      return true;
    }
    var obj = {};
    var sym = /* @__PURE__ */ Symbol("test");
    var symObj = Object(sym);
    if (typeof sym === "string") {
      return false;
    }
    if (Object.prototype.toString.call(sym) !== "[object Symbol]") {
      return false;
    }
    if (Object.prototype.toString.call(symObj) !== "[object Symbol]") {
      return false;
    }
    var symVal = 42;
    obj[sym] = symVal;
    for (sym in obj) {
      return false;
    }
    if (typeof Object.keys === "function" && Object.keys(obj).length !== 0) {
      return false;
    }
    if (typeof Object.getOwnPropertyNames === "function" && Object.getOwnPropertyNames(obj).length !== 0) {
      return false;
    }
    var syms = Object.getOwnPropertySymbols(obj);
    if (syms.length !== 1 || syms[0] !== sym) {
      return false;
    }
    if (!Object.prototype.propertyIsEnumerable.call(obj, sym)) {
      return false;
    }
    if (typeof Object.getOwnPropertyDescriptor === "function") {
      var descriptor = Object.getOwnPropertyDescriptor(obj, sym);
      if (descriptor.value !== symVal || descriptor.enumerable !== true) {
        return false;
      }
    }
    return true;
  };
  return exports$k;
}
function dew$j() {
  if (_dewExec$j) return exports$j;
  _dewExec$j = true;
  exports$j = Error;
  return exports$j;
}
function dew$i() {
  if (_dewExec$i) return exports$i;
  _dewExec$i = true;
  exports$i = EvalError;
  return exports$i;
}
function dew$h() {
  if (_dewExec$h) return exports$h;
  _dewExec$h = true;
  exports$h = RangeError;
  return exports$h;
}
function dew$g2() {
  if (_dewExec$g2) return exports$g2;
  _dewExec$g2 = true;
  exports$g2 = ReferenceError;
  return exports$g2;
}
function dew$f2() {
  if (_dewExec$f2) return exports$f2;
  _dewExec$f2 = true;
  exports$f2 = SyntaxError;
  return exports$f2;
}
function dew$e2() {
  if (_dewExec$e2) return exports$e2;
  _dewExec$e2 = true;
  exports$e2 = TypeError;
  return exports$e2;
}
function dew$d2() {
  if (_dewExec$d2) return exports$d2;
  _dewExec$d2 = true;
  exports$d2 = URIError;
  return exports$d2;
}
function dew$c2() {
  if (_dewExec$c2) return exports$c2;
  _dewExec$c2 = true;
  var origSymbol = typeof Symbol !== "undefined" && Symbol;
  var hasSymbolSham = dew$k();
  exports$c2 = function hasNativeSymbols() {
    if (typeof origSymbol !== "function") {
      return false;
    }
    if (typeof Symbol !== "function") {
      return false;
    }
    if (typeof origSymbol("foo") !== "symbol") {
      return false;
    }
    if (typeof /* @__PURE__ */ Symbol("bar") !== "symbol") {
      return false;
    }
    return hasSymbolSham();
  };
  return exports$c2;
}
function dew$b2() {
  if (_dewExec$b2) return exports$b2;
  _dewExec$b2 = true;
  var test = {
    __proto__: null,
    foo: {}
  };
  var $Object = Object;
  exports$b2 = function hasProto() {
    return {
      __proto__: test
    }.foo === test.foo && !(test instanceof $Object);
  };
  return exports$b2;
}
function dew$a2() {
  if (_dewExec$a2) return exports$a2;
  _dewExec$a2 = true;
  var ERROR_MESSAGE = "Function.prototype.bind called on incompatible ";
  var toStr = Object.prototype.toString;
  var max = Math.max;
  var funcType = "[object Function]";
  var concatty = function concatty2(a6, b5) {
    var arr = [];
    for (var i6 = 0; i6 < a6.length; i6 += 1) {
      arr[i6] = a6[i6];
    }
    for (var j4 = 0; j4 < b5.length; j4 += 1) {
      arr[j4 + a6.length] = b5[j4];
    }
    return arr;
  };
  var slicy = function slicy2(arrLike, offset) {
    var arr = [];
    for (var i6 = offset, j4 = 0; i6 < arrLike.length; i6 += 1, j4 += 1) {
      arr[j4] = arrLike[i6];
    }
    return arr;
  };
  var joiny = function(arr, joiner) {
    var str = "";
    for (var i6 = 0; i6 < arr.length; i6 += 1) {
      str += arr[i6];
      if (i6 + 1 < arr.length) {
        str += joiner;
      }
    }
    return str;
  };
  exports$a2 = function bind(that) {
    var target = this;
    if (typeof target !== "function" || toStr.apply(target) !== funcType) {
      throw new TypeError(ERROR_MESSAGE + target);
    }
    var args = slicy(arguments, 1);
    var bound;
    var binder = function() {
      if (this instanceof bound) {
        var result = target.apply(this, concatty(args, arguments));
        if (Object(result) === result) {
          return result;
        }
        return this;
      }
      return target.apply(that, concatty(args, arguments));
    };
    var boundLength = max(0, target.length - args.length);
    var boundArgs = [];
    for (var i6 = 0; i6 < boundLength; i6++) {
      boundArgs[i6] = "$" + i6;
    }
    bound = Function("binder", "return function (" + joiny(boundArgs, ",") + "){ return binder.apply(this,arguments); }")(binder);
    if (target.prototype) {
      var Empty = function Empty2() {
      };
      Empty.prototype = target.prototype;
      bound.prototype = new Empty();
      Empty.prototype = null;
    }
    return bound;
  };
  return exports$a2;
}
function dew$92() {
  if (_dewExec$92) return exports$92;
  _dewExec$92 = true;
  var implementation = dew$a2();
  exports$92 = Function.prototype.bind || implementation;
  return exports$92;
}
function dew$82() {
  if (_dewExec$82) return exports$82;
  _dewExec$82 = true;
  var call = Function.prototype.call;
  var $hasOwn = Object.prototype.hasOwnProperty;
  var bind = dew$92();
  exports$82 = bind.call(call, $hasOwn);
  return exports$82;
}
function dew$72() {
  if (_dewExec$72) return exports$72;
  _dewExec$72 = true;
  var undefined$1;
  var $Error = dew$j();
  var $EvalError = dew$i();
  var $RangeError = dew$h();
  var $ReferenceError = dew$g2();
  var $SyntaxError = dew$f2();
  var $TypeError = dew$e2();
  var $URIError = dew$d2();
  var $Function = Function;
  var getEvalledConstructor = function(expressionSyntax) {
    try {
      return $Function('"use strict"; return (' + expressionSyntax + ").constructor;")();
    } catch (e6) {
    }
  };
  var $gOPD = Object.getOwnPropertyDescriptor;
  if ($gOPD) {
    try {
      $gOPD({}, "");
    } catch (e6) {
      $gOPD = null;
    }
  }
  var throwTypeError = function() {
    throw new $TypeError();
  };
  var ThrowTypeError = $gOPD ? (function() {
    try {
      arguments.callee;
      return throwTypeError;
    } catch (calleeThrows) {
      try {
        return $gOPD(arguments, "callee").get;
      } catch (gOPDthrows) {
        return throwTypeError;
      }
    }
  })() : throwTypeError;
  var hasSymbols = dew$c2()();
  var hasProto = dew$b2()();
  var getProto = Object.getPrototypeOf || (hasProto ? function(x4) {
    return x4.__proto__;
  } : null);
  var needsEval = {};
  var TypedArray = typeof Uint8Array === "undefined" || !getProto ? undefined$1 : getProto(Uint8Array);
  var INTRINSICS = {
    __proto__: null,
    "%AggregateError%": typeof AggregateError === "undefined" ? undefined$1 : AggregateError,
    "%Array%": Array,
    "%ArrayBuffer%": typeof ArrayBuffer === "undefined" ? undefined$1 : ArrayBuffer,
    "%ArrayIteratorPrototype%": hasSymbols && getProto ? getProto([][Symbol.iterator]()) : undefined$1,
    "%AsyncFromSyncIteratorPrototype%": undefined$1,
    "%AsyncFunction%": needsEval,
    "%AsyncGenerator%": needsEval,
    "%AsyncGeneratorFunction%": needsEval,
    "%AsyncIteratorPrototype%": needsEval,
    "%Atomics%": typeof Atomics === "undefined" ? undefined$1 : Atomics,
    "%BigInt%": typeof BigInt === "undefined" ? undefined$1 : BigInt,
    "%BigInt64Array%": typeof BigInt64Array === "undefined" ? undefined$1 : BigInt64Array,
    "%BigUint64Array%": typeof BigUint64Array === "undefined" ? undefined$1 : BigUint64Array,
    "%Boolean%": Boolean,
    "%DataView%": typeof DataView === "undefined" ? undefined$1 : DataView,
    "%Date%": Date,
    "%decodeURI%": decodeURI,
    "%decodeURIComponent%": decodeURIComponent,
    "%encodeURI%": encodeURI,
    "%encodeURIComponent%": encodeURIComponent,
    "%Error%": $Error,
    "%eval%": eval,
    // eslint-disable-line no-eval
    "%EvalError%": $EvalError,
    "%Float32Array%": typeof Float32Array === "undefined" ? undefined$1 : Float32Array,
    "%Float64Array%": typeof Float64Array === "undefined" ? undefined$1 : Float64Array,
    "%FinalizationRegistry%": typeof FinalizationRegistry === "undefined" ? undefined$1 : FinalizationRegistry,
    "%Function%": $Function,
    "%GeneratorFunction%": needsEval,
    "%Int8Array%": typeof Int8Array === "undefined" ? undefined$1 : Int8Array,
    "%Int16Array%": typeof Int16Array === "undefined" ? undefined$1 : Int16Array,
    "%Int32Array%": typeof Int32Array === "undefined" ? undefined$1 : Int32Array,
    "%isFinite%": isFinite,
    "%isNaN%": isNaN,
    "%IteratorPrototype%": hasSymbols && getProto ? getProto(getProto([][Symbol.iterator]())) : undefined$1,
    "%JSON%": typeof JSON === "object" ? JSON : undefined$1,
    "%Map%": typeof Map === "undefined" ? undefined$1 : Map,
    "%MapIteratorPrototype%": typeof Map === "undefined" || !hasSymbols || !getProto ? undefined$1 : getProto((/* @__PURE__ */ new Map())[Symbol.iterator]()),
    "%Math%": Math,
    "%Number%": Number,
    "%Object%": Object,
    "%parseFloat%": parseFloat,
    "%parseInt%": parseInt,
    "%Promise%": typeof Promise === "undefined" ? undefined$1 : Promise,
    "%Proxy%": typeof Proxy === "undefined" ? undefined$1 : Proxy,
    "%RangeError%": $RangeError,
    "%ReferenceError%": $ReferenceError,
    "%Reflect%": typeof Reflect === "undefined" ? undefined$1 : Reflect,
    "%RegExp%": RegExp,
    "%Set%": typeof Set === "undefined" ? undefined$1 : Set,
    "%SetIteratorPrototype%": typeof Set === "undefined" || !hasSymbols || !getProto ? undefined$1 : getProto((/* @__PURE__ */ new Set())[Symbol.iterator]()),
    "%SharedArrayBuffer%": typeof SharedArrayBuffer === "undefined" ? undefined$1 : SharedArrayBuffer,
    "%String%": String,
    "%StringIteratorPrototype%": hasSymbols && getProto ? getProto(""[Symbol.iterator]()) : undefined$1,
    "%Symbol%": hasSymbols ? Symbol : undefined$1,
    "%SyntaxError%": $SyntaxError,
    "%ThrowTypeError%": ThrowTypeError,
    "%TypedArray%": TypedArray,
    "%TypeError%": $TypeError,
    "%Uint8Array%": typeof Uint8Array === "undefined" ? undefined$1 : Uint8Array,
    "%Uint8ClampedArray%": typeof Uint8ClampedArray === "undefined" ? undefined$1 : Uint8ClampedArray,
    "%Uint16Array%": typeof Uint16Array === "undefined" ? undefined$1 : Uint16Array,
    "%Uint32Array%": typeof Uint32Array === "undefined" ? undefined$1 : Uint32Array,
    "%URIError%": $URIError,
    "%WeakMap%": typeof WeakMap === "undefined" ? undefined$1 : WeakMap,
    "%WeakRef%": typeof WeakRef === "undefined" ? undefined$1 : WeakRef,
    "%WeakSet%": typeof WeakSet === "undefined" ? undefined$1 : WeakSet
  };
  if (getProto) {
    try {
      null.error;
    } catch (e6) {
      var errorProto = getProto(getProto(e6));
      INTRINSICS["%Error.prototype%"] = errorProto;
    }
  }
  var doEval = function doEval2(name2) {
    var value;
    if (name2 === "%AsyncFunction%") {
      value = getEvalledConstructor("async function () {}");
    } else if (name2 === "%GeneratorFunction%") {
      value = getEvalledConstructor("function* () {}");
    } else if (name2 === "%AsyncGeneratorFunction%") {
      value = getEvalledConstructor("async function* () {}");
    } else if (name2 === "%AsyncGenerator%") {
      var fn = doEval2("%AsyncGeneratorFunction%");
      if (fn) {
        value = fn.prototype;
      }
    } else if (name2 === "%AsyncIteratorPrototype%") {
      var gen = doEval2("%AsyncGenerator%");
      if (gen && getProto) {
        value = getProto(gen.prototype);
      }
    }
    INTRINSICS[name2] = value;
    return value;
  };
  var LEGACY_ALIASES = {
    __proto__: null,
    "%ArrayBufferPrototype%": ["ArrayBuffer", "prototype"],
    "%ArrayPrototype%": ["Array", "prototype"],
    "%ArrayProto_entries%": ["Array", "prototype", "entries"],
    "%ArrayProto_forEach%": ["Array", "prototype", "forEach"],
    "%ArrayProto_keys%": ["Array", "prototype", "keys"],
    "%ArrayProto_values%": ["Array", "prototype", "values"],
    "%AsyncFunctionPrototype%": ["AsyncFunction", "prototype"],
    "%AsyncGenerator%": ["AsyncGeneratorFunction", "prototype"],
    "%AsyncGeneratorPrototype%": ["AsyncGeneratorFunction", "prototype", "prototype"],
    "%BooleanPrototype%": ["Boolean", "prototype"],
    "%DataViewPrototype%": ["DataView", "prototype"],
    "%DatePrototype%": ["Date", "prototype"],
    "%ErrorPrototype%": ["Error", "prototype"],
    "%EvalErrorPrototype%": ["EvalError", "prototype"],
    "%Float32ArrayPrototype%": ["Float32Array", "prototype"],
    "%Float64ArrayPrototype%": ["Float64Array", "prototype"],
    "%FunctionPrototype%": ["Function", "prototype"],
    "%Generator%": ["GeneratorFunction", "prototype"],
    "%GeneratorPrototype%": ["GeneratorFunction", "prototype", "prototype"],
    "%Int8ArrayPrototype%": ["Int8Array", "prototype"],
    "%Int16ArrayPrototype%": ["Int16Array", "prototype"],
    "%Int32ArrayPrototype%": ["Int32Array", "prototype"],
    "%JSONParse%": ["JSON", "parse"],
    "%JSONStringify%": ["JSON", "stringify"],
    "%MapPrototype%": ["Map", "prototype"],
    "%NumberPrototype%": ["Number", "prototype"],
    "%ObjectPrototype%": ["Object", "prototype"],
    "%ObjProto_toString%": ["Object", "prototype", "toString"],
    "%ObjProto_valueOf%": ["Object", "prototype", "valueOf"],
    "%PromisePrototype%": ["Promise", "prototype"],
    "%PromiseProto_then%": ["Promise", "prototype", "then"],
    "%Promise_all%": ["Promise", "all"],
    "%Promise_reject%": ["Promise", "reject"],
    "%Promise_resolve%": ["Promise", "resolve"],
    "%RangeErrorPrototype%": ["RangeError", "prototype"],
    "%ReferenceErrorPrototype%": ["ReferenceError", "prototype"],
    "%RegExpPrototype%": ["RegExp", "prototype"],
    "%SetPrototype%": ["Set", "prototype"],
    "%SharedArrayBufferPrototype%": ["SharedArrayBuffer", "prototype"],
    "%StringPrototype%": ["String", "prototype"],
    "%SymbolPrototype%": ["Symbol", "prototype"],
    "%SyntaxErrorPrototype%": ["SyntaxError", "prototype"],
    "%TypedArrayPrototype%": ["TypedArray", "prototype"],
    "%TypeErrorPrototype%": ["TypeError", "prototype"],
    "%Uint8ArrayPrototype%": ["Uint8Array", "prototype"],
    "%Uint8ClampedArrayPrototype%": ["Uint8ClampedArray", "prototype"],
    "%Uint16ArrayPrototype%": ["Uint16Array", "prototype"],
    "%Uint32ArrayPrototype%": ["Uint32Array", "prototype"],
    "%URIErrorPrototype%": ["URIError", "prototype"],
    "%WeakMapPrototype%": ["WeakMap", "prototype"],
    "%WeakSetPrototype%": ["WeakSet", "prototype"]
  };
  var bind = dew$92();
  var hasOwn = dew$82();
  var $concat = bind.call(Function.call, Array.prototype.concat);
  var $spliceApply = bind.call(Function.apply, Array.prototype.splice);
  var $replace = bind.call(Function.call, String.prototype.replace);
  var $strSlice = bind.call(Function.call, String.prototype.slice);
  var $exec = bind.call(Function.call, RegExp.prototype.exec);
  var rePropName = /[^%.[\]]+|\[(?:(-?\d+(?:\.\d+)?)|(["'])((?:(?!\2)[^\\]|\\.)*?)\2)\]|(?=(?:\.|\[\])(?:\.|\[\]|%$))/g;
  var reEscapeChar = /\\(\\)?/g;
  var stringToPath = function stringToPath2(string) {
    var first = $strSlice(string, 0, 1);
    var last = $strSlice(string, -1);
    if (first === "%" && last !== "%") {
      throw new $SyntaxError("invalid intrinsic syntax, expected closing `%`");
    } else if (last === "%" && first !== "%") {
      throw new $SyntaxError("invalid intrinsic syntax, expected opening `%`");
    }
    var result = [];
    $replace(string, rePropName, function(match, number, quote, subString) {
      result[result.length] = quote ? $replace(subString, reEscapeChar, "$1") : number || match;
    });
    return result;
  };
  var getBaseIntrinsic = function getBaseIntrinsic2(name2, allowMissing) {
    var intrinsicName = name2;
    var alias;
    if (hasOwn(LEGACY_ALIASES, intrinsicName)) {
      alias = LEGACY_ALIASES[intrinsicName];
      intrinsicName = "%" + alias[0] + "%";
    }
    if (hasOwn(INTRINSICS, intrinsicName)) {
      var value = INTRINSICS[intrinsicName];
      if (value === needsEval) {
        value = doEval(intrinsicName);
      }
      if (typeof value === "undefined" && !allowMissing) {
        throw new $TypeError("intrinsic " + name2 + " exists, but is not available. Please file an issue!");
      }
      return {
        alias,
        name: intrinsicName,
        value
      };
    }
    throw new $SyntaxError("intrinsic " + name2 + " does not exist!");
  };
  exports$72 = function GetIntrinsic(name2, allowMissing) {
    if (typeof name2 !== "string" || name2.length === 0) {
      throw new $TypeError("intrinsic name must be a non-empty string");
    }
    if (arguments.length > 1 && typeof allowMissing !== "boolean") {
      throw new $TypeError('"allowMissing" argument must be a boolean');
    }
    if ($exec(/^%?[^%]*%?$/, name2) === null) {
      throw new $SyntaxError("`%` may not be present anywhere but at the beginning and end of the intrinsic name");
    }
    var parts = stringToPath(name2);
    var intrinsicBaseName = parts.length > 0 ? parts[0] : "";
    var intrinsic = getBaseIntrinsic("%" + intrinsicBaseName + "%", allowMissing);
    var intrinsicRealName = intrinsic.name;
    var value = intrinsic.value;
    var skipFurtherCaching = false;
    var alias = intrinsic.alias;
    if (alias) {
      intrinsicBaseName = alias[0];
      $spliceApply(parts, $concat([0, 1], alias));
    }
    for (var i6 = 1, isOwn = true; i6 < parts.length; i6 += 1) {
      var part = parts[i6];
      var first = $strSlice(part, 0, 1);
      var last = $strSlice(part, -1);
      if ((first === '"' || first === "'" || first === "`" || last === '"' || last === "'" || last === "`") && first !== last) {
        throw new $SyntaxError("property names with quotes must have matching quotes");
      }
      if (part === "constructor" || !isOwn) {
        skipFurtherCaching = true;
      }
      intrinsicBaseName += "." + part;
      intrinsicRealName = "%" + intrinsicBaseName + "%";
      if (hasOwn(INTRINSICS, intrinsicRealName)) {
        value = INTRINSICS[intrinsicRealName];
      } else if (value != null) {
        if (!(part in value)) {
          if (!allowMissing) {
            throw new $TypeError("base intrinsic for " + name2 + " exists, but the property is not available.");
          }
          return void undefined$1;
        }
        if ($gOPD && i6 + 1 >= parts.length) {
          var desc = $gOPD(value, part);
          isOwn = !!desc;
          if (isOwn && "get" in desc && !("originalValue" in desc.get)) {
            value = desc.get;
          } else {
            value = value[part];
          }
        } else {
          isOwn = hasOwn(value, part);
          value = value[part];
        }
        if (isOwn && !skipFurtherCaching) {
          INTRINSICS[intrinsicRealName] = value;
        }
      }
    }
    return value;
  };
  return exports$72;
}
function dew$62() {
  if (_dewExec$62) return exports$62;
  _dewExec$62 = true;
  var GetIntrinsic = dew$72();
  var $defineProperty = GetIntrinsic("%Object.defineProperty%", true) || false;
  if ($defineProperty) {
    try {
      $defineProperty({}, "a", {
        value: 1
      });
    } catch (e6) {
      $defineProperty = false;
    }
  }
  exports$62 = $defineProperty;
  return exports$62;
}
function dew$52() {
  if (_dewExec$52) return exports$52;
  _dewExec$52 = true;
  var GetIntrinsic = dew$72();
  var $gOPD = GetIntrinsic("%Object.getOwnPropertyDescriptor%", true);
  if ($gOPD) {
    try {
      $gOPD([], "length");
    } catch (e6) {
      $gOPD = null;
    }
  }
  exports$52 = $gOPD;
  return exports$52;
}
function dew$42() {
  if (_dewExec$42) return exports$42;
  _dewExec$42 = true;
  var $defineProperty = dew$62();
  var $SyntaxError = dew$f2();
  var $TypeError = dew$e2();
  var gopd = dew$52();
  exports$42 = function defineDataProperty(obj, property, value) {
    if (!obj || typeof obj !== "object" && typeof obj !== "function") {
      throw new $TypeError("`obj` must be an object or a function`");
    }
    if (typeof property !== "string" && typeof property !== "symbol") {
      throw new $TypeError("`property` must be a string or a symbol`");
    }
    if (arguments.length > 3 && typeof arguments[3] !== "boolean" && arguments[3] !== null) {
      throw new $TypeError("`nonEnumerable`, if provided, must be a boolean or null");
    }
    if (arguments.length > 4 && typeof arguments[4] !== "boolean" && arguments[4] !== null) {
      throw new $TypeError("`nonWritable`, if provided, must be a boolean or null");
    }
    if (arguments.length > 5 && typeof arguments[5] !== "boolean" && arguments[5] !== null) {
      throw new $TypeError("`nonConfigurable`, if provided, must be a boolean or null");
    }
    if (arguments.length > 6 && typeof arguments[6] !== "boolean") {
      throw new $TypeError("`loose`, if provided, must be a boolean");
    }
    var nonEnumerable = arguments.length > 3 ? arguments[3] : null;
    var nonWritable = arguments.length > 4 ? arguments[4] : null;
    var nonConfigurable = arguments.length > 5 ? arguments[5] : null;
    var loose = arguments.length > 6 ? arguments[6] : false;
    var desc = !!gopd && gopd(obj, property);
    if ($defineProperty) {
      $defineProperty(obj, property, {
        configurable: nonConfigurable === null && desc ? desc.configurable : !nonConfigurable,
        enumerable: nonEnumerable === null && desc ? desc.enumerable : !nonEnumerable,
        value,
        writable: nonWritable === null && desc ? desc.writable : !nonWritable
      });
    } else if (loose || !nonEnumerable && !nonWritable && !nonConfigurable) {
      obj[property] = value;
    } else {
      throw new $SyntaxError("This environment does not support defining a property as non-configurable, non-writable, or non-enumerable.");
    }
  };
  return exports$42;
}
function dew$32() {
  if (_dewExec$32) return exports$32;
  _dewExec$32 = true;
  var $defineProperty = dew$62();
  var hasPropertyDescriptors = function hasPropertyDescriptors2() {
    return !!$defineProperty;
  };
  hasPropertyDescriptors.hasArrayLengthDefineBug = function hasArrayLengthDefineBug() {
    if (!$defineProperty) {
      return null;
    }
    try {
      return $defineProperty([], "length", {
        value: 1
      }).length !== 1;
    } catch (e6) {
      return true;
    }
  };
  exports$32 = hasPropertyDescriptors;
  return exports$32;
}
function dew$23() {
  if (_dewExec$23) return exports$24;
  _dewExec$23 = true;
  var GetIntrinsic = dew$72();
  var define = dew$42();
  var hasDescriptors = dew$32()();
  var gOPD = dew$52();
  var $TypeError = dew$e2();
  var $floor = GetIntrinsic("%Math.floor%");
  exports$24 = function setFunctionLength(fn, length) {
    if (typeof fn !== "function") {
      throw new $TypeError("`fn` is not a function");
    }
    if (typeof length !== "number" || length < 0 || length > 4294967295 || $floor(length) !== length) {
      throw new $TypeError("`length` must be a positive 32-bit integer");
    }
    var loose = arguments.length > 2 && !!arguments[2];
    var functionLengthIsConfigurable = true;
    var functionLengthIsWritable = true;
    if ("length" in fn && gOPD) {
      var desc = gOPD(fn, "length");
      if (desc && !desc.configurable) {
        functionLengthIsConfigurable = false;
      }
      if (desc && !desc.writable) {
        functionLengthIsWritable = false;
      }
    }
    if (functionLengthIsConfigurable || functionLengthIsWritable || !loose) {
      if (hasDescriptors) {
        define(
          /** @type {Parameters<define>[0]} */
          fn,
          "length",
          length,
          true,
          true
        );
      } else {
        define(
          /** @type {Parameters<define>[0]} */
          fn,
          "length",
          length
        );
      }
    }
    return fn;
  };
  return exports$24;
}
function dew$14() {
  if (_dewExec$14) return exports$16;
  _dewExec$14 = true;
  var bind = dew$92();
  var GetIntrinsic = dew$72();
  var setFunctionLength = dew$23();
  var $TypeError = dew$e2();
  var $apply = GetIntrinsic("%Function.prototype.apply%");
  var $call = GetIntrinsic("%Function.prototype.call%");
  var $reflectApply = GetIntrinsic("%Reflect.apply%", true) || bind.call($call, $apply);
  var $defineProperty = dew$62();
  var $max = GetIntrinsic("%Math.max%");
  exports$16 = function callBind(originalFunction) {
    if (typeof originalFunction !== "function") {
      throw new $TypeError("a function is required");
    }
    var func = $reflectApply(bind, $call, arguments);
    return setFunctionLength(func, 1 + $max(0, originalFunction.length - (arguments.length - 1)), true);
  };
  var applyBind = function applyBind2() {
    return $reflectApply(bind, $apply, arguments);
  };
  if ($defineProperty) {
    $defineProperty(exports$16, "apply", {
      value: applyBind
    });
  } else {
    exports$16.apply = applyBind;
  }
  return exports$16;
}
function dew7() {
  if (_dewExec7) return exports8;
  _dewExec7 = true;
  var GetIntrinsic = dew$72();
  var callBind = dew$14();
  var $indexOf = callBind(GetIntrinsic("String.prototype.indexOf"));
  exports8 = function callBoundIntrinsic(name2, allowMissing) {
    var intrinsic = GetIntrinsic(name2, !!allowMissing);
    if (typeof intrinsic === "function" && $indexOf(name2, ".prototype.") > -1) {
      return callBind(intrinsic);
    }
    return intrinsic;
  };
  return exports8;
}
var exports$k, _dewExec$k, exports$j, _dewExec$j, exports$i, _dewExec$i, exports$h, _dewExec$h, exports$g2, _dewExec$g2, exports$f2, _dewExec$f2, exports$e2, _dewExec$e2, exports$d2, _dewExec$d2, exports$c2, _dewExec$c2, exports$b2, _dewExec$b2, exports$a2, _dewExec$a2, exports$92, _dewExec$92, exports$82, _dewExec$82, exports$72, _dewExec$72, exports$62, _dewExec$62, exports$52, _dewExec$52, exports$42, _dewExec$42, exports$32, _dewExec$32, exports$24, _dewExec$23, exports$16, _dewExec$14, exports8, _dewExec7;
var init_chunk_DtcTpLWz = __esm({
  "node_modules/@jspm/core/nodelibs/browser/chunk-DtcTpLWz.js"() {
    init_dirname();
    init_buffer2();
    init_process2();
    exports$k = {};
    _dewExec$k = false;
    exports$j = {};
    _dewExec$j = false;
    exports$i = {};
    _dewExec$i = false;
    exports$h = {};
    _dewExec$h = false;
    exports$g2 = {};
    _dewExec$g2 = false;
    exports$f2 = {};
    _dewExec$f2 = false;
    exports$e2 = {};
    _dewExec$e2 = false;
    exports$d2 = {};
    _dewExec$d2 = false;
    exports$c2 = {};
    _dewExec$c2 = false;
    exports$b2 = {};
    _dewExec$b2 = false;
    exports$a2 = {};
    _dewExec$a2 = false;
    exports$92 = {};
    _dewExec$92 = false;
    exports$82 = {};
    _dewExec$82 = false;
    exports$72 = {};
    _dewExec$72 = false;
    exports$62 = {};
    _dewExec$62 = false;
    exports$52 = {};
    _dewExec$52 = false;
    exports$42 = {};
    _dewExec$42 = false;
    exports$32 = {};
    _dewExec$32 = false;
    exports$24 = {};
    _dewExec$23 = false;
    exports$16 = {};
    _dewExec$14 = false;
    exports8 = {};
    _dewExec7 = false;
  }
});

// node_modules/@jspm/core/nodelibs/browser/chunk-BlJi4mNy.js
function dew8() {
  if (_dewExec8) return exports$17;
  _dewExec8 = true;
  var process$1 = process3;
  function assertPath(path2) {
    if (typeof path2 !== "string") {
      throw new TypeError("Path must be a string. Received " + JSON.stringify(path2));
    }
  }
  function normalizeStringPosix(path2, allowAboveRoot) {
    var res = "";
    var lastSegmentLength = 0;
    var lastSlash = -1;
    var dots = 0;
    var code;
    for (var i6 = 0; i6 <= path2.length; ++i6) {
      if (i6 < path2.length) code = path2.charCodeAt(i6);
      else if (code === 47) break;
      else code = 47;
      if (code === 47) {
        if (lastSlash === i6 - 1 || dots === 1) ;
        else if (lastSlash !== i6 - 1 && dots === 2) {
          if (res.length < 2 || lastSegmentLength !== 2 || res.charCodeAt(res.length - 1) !== 46 || res.charCodeAt(res.length - 2) !== 46) {
            if (res.length > 2) {
              var lastSlashIndex = res.lastIndexOf("/");
              if (lastSlashIndex !== res.length - 1) {
                if (lastSlashIndex === -1) {
                  res = "";
                  lastSegmentLength = 0;
                } else {
                  res = res.slice(0, lastSlashIndex);
                  lastSegmentLength = res.length - 1 - res.lastIndexOf("/");
                }
                lastSlash = i6;
                dots = 0;
                continue;
              }
            } else if (res.length === 2 || res.length === 1) {
              res = "";
              lastSegmentLength = 0;
              lastSlash = i6;
              dots = 0;
              continue;
            }
          }
          if (allowAboveRoot) {
            if (res.length > 0) res += "/..";
            else res = "..";
            lastSegmentLength = 2;
          }
        } else {
          if (res.length > 0) res += "/" + path2.slice(lastSlash + 1, i6);
          else res = path2.slice(lastSlash + 1, i6);
          lastSegmentLength = i6 - lastSlash - 1;
        }
        lastSlash = i6;
        dots = 0;
      } else if (code === 46 && dots !== -1) {
        ++dots;
      } else {
        dots = -1;
      }
    }
    return res;
  }
  function _format(sep, pathObject) {
    var dir = pathObject.dir || pathObject.root;
    var base = pathObject.base || (pathObject.name || "") + (pathObject.ext || "");
    if (!dir) {
      return base;
    }
    if (dir === pathObject.root) {
      return dir + base;
    }
    return dir + sep + base;
  }
  var posix = {
    // path.resolve([from ...], to)
    resolve: function resolve2() {
      var resolvedPath = "";
      var resolvedAbsolute = false;
      var cwd3;
      for (var i6 = arguments.length - 1; i6 >= -1 && !resolvedAbsolute; i6--) {
        var path2;
        if (i6 >= 0) path2 = arguments[i6];
        else {
          if (cwd3 === void 0) cwd3 = process$1.cwd();
          path2 = cwd3;
        }
        assertPath(path2);
        if (path2.length === 0) {
          continue;
        }
        resolvedPath = path2 + "/" + resolvedPath;
        resolvedAbsolute = path2.charCodeAt(0) === 47;
      }
      resolvedPath = normalizeStringPosix(resolvedPath, !resolvedAbsolute);
      if (resolvedAbsolute) {
        if (resolvedPath.length > 0) return "/" + resolvedPath;
        else return "/";
      } else if (resolvedPath.length > 0) {
        return resolvedPath;
      } else {
        return ".";
      }
    },
    normalize: function normalize(path2) {
      assertPath(path2);
      if (path2.length === 0) return ".";
      var isAbsolute = path2.charCodeAt(0) === 47;
      var trailingSeparator = path2.charCodeAt(path2.length - 1) === 47;
      path2 = normalizeStringPosix(path2, !isAbsolute);
      if (path2.length === 0 && !isAbsolute) path2 = ".";
      if (path2.length > 0 && trailingSeparator) path2 += "/";
      if (isAbsolute) return "/" + path2;
      return path2;
    },
    isAbsolute: function isAbsolute(path2) {
      assertPath(path2);
      return path2.length > 0 && path2.charCodeAt(0) === 47;
    },
    join: function join() {
      if (arguments.length === 0) return ".";
      var joined;
      for (var i6 = 0; i6 < arguments.length; ++i6) {
        var arg = arguments[i6];
        assertPath(arg);
        if (arg.length > 0) {
          if (joined === void 0) joined = arg;
          else joined += "/" + arg;
        }
      }
      if (joined === void 0) return ".";
      return posix.normalize(joined);
    },
    relative: function relative(from, to) {
      assertPath(from);
      assertPath(to);
      if (from === to) return "";
      from = posix.resolve(from);
      to = posix.resolve(to);
      if (from === to) return "";
      var fromStart = 1;
      for (; fromStart < from.length; ++fromStart) {
        if (from.charCodeAt(fromStart) !== 47) break;
      }
      var fromEnd = from.length;
      var fromLen = fromEnd - fromStart;
      var toStart = 1;
      for (; toStart < to.length; ++toStart) {
        if (to.charCodeAt(toStart) !== 47) break;
      }
      var toEnd = to.length;
      var toLen = toEnd - toStart;
      var length = fromLen < toLen ? fromLen : toLen;
      var lastCommonSep = -1;
      var i6 = 0;
      for (; i6 <= length; ++i6) {
        if (i6 === length) {
          if (toLen > length) {
            if (to.charCodeAt(toStart + i6) === 47) {
              return to.slice(toStart + i6 + 1);
            } else if (i6 === 0) {
              return to.slice(toStart + i6);
            }
          } else if (fromLen > length) {
            if (from.charCodeAt(fromStart + i6) === 47) {
              lastCommonSep = i6;
            } else if (i6 === 0) {
              lastCommonSep = 0;
            }
          }
          break;
        }
        var fromCode = from.charCodeAt(fromStart + i6);
        var toCode = to.charCodeAt(toStart + i6);
        if (fromCode !== toCode) break;
        else if (fromCode === 47) lastCommonSep = i6;
      }
      var out = "";
      for (i6 = fromStart + lastCommonSep + 1; i6 <= fromEnd; ++i6) {
        if (i6 === fromEnd || from.charCodeAt(i6) === 47) {
          if (out.length === 0) out += "..";
          else out += "/..";
        }
      }
      if (out.length > 0) return out + to.slice(toStart + lastCommonSep);
      else {
        toStart += lastCommonSep;
        if (to.charCodeAt(toStart) === 47) ++toStart;
        return to.slice(toStart);
      }
    },
    _makeLong: function _makeLong(path2) {
      return path2;
    },
    dirname: function dirname(path2) {
      assertPath(path2);
      if (path2.length === 0) return ".";
      var code = path2.charCodeAt(0);
      var hasRoot = code === 47;
      var end = -1;
      var matchedSlash = true;
      for (var i6 = path2.length - 1; i6 >= 1; --i6) {
        code = path2.charCodeAt(i6);
        if (code === 47) {
          if (!matchedSlash) {
            end = i6;
            break;
          }
        } else {
          matchedSlash = false;
        }
      }
      if (end === -1) return hasRoot ? "/" : ".";
      if (hasRoot && end === 1) return "//";
      return path2.slice(0, end);
    },
    basename: function basename(path2, ext) {
      if (ext !== void 0 && typeof ext !== "string") throw new TypeError('"ext" argument must be a string');
      assertPath(path2);
      var start = 0;
      var end = -1;
      var matchedSlash = true;
      var i6;
      if (ext !== void 0 && ext.length > 0 && ext.length <= path2.length) {
        if (ext.length === path2.length && ext === path2) return "";
        var extIdx = ext.length - 1;
        var firstNonSlashEnd = -1;
        for (i6 = path2.length - 1; i6 >= 0; --i6) {
          var code = path2.charCodeAt(i6);
          if (code === 47) {
            if (!matchedSlash) {
              start = i6 + 1;
              break;
            }
          } else {
            if (firstNonSlashEnd === -1) {
              matchedSlash = false;
              firstNonSlashEnd = i6 + 1;
            }
            if (extIdx >= 0) {
              if (code === ext.charCodeAt(extIdx)) {
                if (--extIdx === -1) {
                  end = i6;
                }
              } else {
                extIdx = -1;
                end = firstNonSlashEnd;
              }
            }
          }
        }
        if (start === end) end = firstNonSlashEnd;
        else if (end === -1) end = path2.length;
        return path2.slice(start, end);
      } else {
        for (i6 = path2.length - 1; i6 >= 0; --i6) {
          if (path2.charCodeAt(i6) === 47) {
            if (!matchedSlash) {
              start = i6 + 1;
              break;
            }
          } else if (end === -1) {
            matchedSlash = false;
            end = i6 + 1;
          }
        }
        if (end === -1) return "";
        return path2.slice(start, end);
      }
    },
    extname: function extname(path2) {
      assertPath(path2);
      var startDot = -1;
      var startPart = 0;
      var end = -1;
      var matchedSlash = true;
      var preDotState = 0;
      for (var i6 = path2.length - 1; i6 >= 0; --i6) {
        var code = path2.charCodeAt(i6);
        if (code === 47) {
          if (!matchedSlash) {
            startPart = i6 + 1;
            break;
          }
          continue;
        }
        if (end === -1) {
          matchedSlash = false;
          end = i6 + 1;
        }
        if (code === 46) {
          if (startDot === -1) startDot = i6;
          else if (preDotState !== 1) preDotState = 1;
        } else if (startDot !== -1) {
          preDotState = -1;
        }
      }
      if (startDot === -1 || end === -1 || // We saw a non-dot character immediately before the dot
      preDotState === 0 || // The (right-most) trimmed path component is exactly '..'
      preDotState === 1 && startDot === end - 1 && startDot === startPart + 1) {
        return "";
      }
      return path2.slice(startDot, end);
    },
    format: function format2(pathObject) {
      if (pathObject === null || typeof pathObject !== "object") {
        throw new TypeError('The "pathObject" argument must be of type Object. Received type ' + typeof pathObject);
      }
      return _format("/", pathObject);
    },
    parse: function parse2(path2) {
      assertPath(path2);
      var ret = {
        root: "",
        dir: "",
        base: "",
        ext: "",
        name: ""
      };
      if (path2.length === 0) return ret;
      var code = path2.charCodeAt(0);
      var isAbsolute = code === 47;
      var start;
      if (isAbsolute) {
        ret.root = "/";
        start = 1;
      } else {
        start = 0;
      }
      var startDot = -1;
      var startPart = 0;
      var end = -1;
      var matchedSlash = true;
      var i6 = path2.length - 1;
      var preDotState = 0;
      for (; i6 >= start; --i6) {
        code = path2.charCodeAt(i6);
        if (code === 47) {
          if (!matchedSlash) {
            startPart = i6 + 1;
            break;
          }
          continue;
        }
        if (end === -1) {
          matchedSlash = false;
          end = i6 + 1;
        }
        if (code === 46) {
          if (startDot === -1) startDot = i6;
          else if (preDotState !== 1) preDotState = 1;
        } else if (startDot !== -1) {
          preDotState = -1;
        }
      }
      if (startDot === -1 || end === -1 || // We saw a non-dot character immediately before the dot
      preDotState === 0 || // The (right-most) trimmed path component is exactly '..'
      preDotState === 1 && startDot === end - 1 && startDot === startPart + 1) {
        if (end !== -1) {
          if (startPart === 0 && isAbsolute) ret.base = ret.name = path2.slice(1, end);
          else ret.base = ret.name = path2.slice(startPart, end);
        }
      } else {
        if (startPart === 0 && isAbsolute) {
          ret.name = path2.slice(1, startDot);
          ret.base = path2.slice(1, end);
        } else {
          ret.name = path2.slice(startPart, startDot);
          ret.base = path2.slice(startPart, end);
        }
        ret.ext = path2.slice(startDot, end);
      }
      if (startPart > 0) ret.dir = path2.slice(0, startPart - 1);
      else if (isAbsolute) ret.dir = "/";
      return ret;
    },
    sep: "/",
    delimiter: ":",
    win32: null,
    posix: null
  };
  posix.posix = posix;
  exports$17 = posix;
  return exports$17;
}
var exports$17, _dewExec8, exports9;
var init_chunk_BlJi4mNy = __esm({
  "node_modules/@jspm/core/nodelibs/browser/chunk-BlJi4mNy.js"() {
    init_dirname();
    init_buffer2();
    init_process2();
    init_chunk_DEMDiNwt();
    exports$17 = {};
    _dewExec8 = false;
    exports9 = dew8();
  }
});

// node_modules/@jspm/core/nodelibs/browser/url.js
function dew$73() {
  if (_dewExec$73) return exports$83;
  _dewExec$73 = true;
  var hasMap = typeof Map === "function" && Map.prototype;
  var mapSizeDescriptor = Object.getOwnPropertyDescriptor && hasMap ? Object.getOwnPropertyDescriptor(Map.prototype, "size") : null;
  var mapSize = hasMap && mapSizeDescriptor && typeof mapSizeDescriptor.get === "function" ? mapSizeDescriptor.get : null;
  var mapForEach = hasMap && Map.prototype.forEach;
  var hasSet = typeof Set === "function" && Set.prototype;
  var setSizeDescriptor = Object.getOwnPropertyDescriptor && hasSet ? Object.getOwnPropertyDescriptor(Set.prototype, "size") : null;
  var setSize = hasSet && setSizeDescriptor && typeof setSizeDescriptor.get === "function" ? setSizeDescriptor.get : null;
  var setForEach = hasSet && Set.prototype.forEach;
  var hasWeakMap = typeof WeakMap === "function" && WeakMap.prototype;
  var weakMapHas = hasWeakMap ? WeakMap.prototype.has : null;
  var hasWeakSet = typeof WeakSet === "function" && WeakSet.prototype;
  var weakSetHas = hasWeakSet ? WeakSet.prototype.has : null;
  var hasWeakRef = typeof WeakRef === "function" && WeakRef.prototype;
  var weakRefDeref = hasWeakRef ? WeakRef.prototype.deref : null;
  var booleanValueOf = Boolean.prototype.valueOf;
  var objectToString = Object.prototype.toString;
  var functionToString = Function.prototype.toString;
  var $match = String.prototype.match;
  var $slice = String.prototype.slice;
  var $replace = String.prototype.replace;
  var $toUpperCase = String.prototype.toUpperCase;
  var $toLowerCase = String.prototype.toLowerCase;
  var $test = RegExp.prototype.test;
  var $concat = Array.prototype.concat;
  var $join = Array.prototype.join;
  var $arrSlice = Array.prototype.slice;
  var $floor = Math.floor;
  var bigIntValueOf = typeof BigInt === "function" ? BigInt.prototype.valueOf : null;
  var gOPS = Object.getOwnPropertySymbols;
  var symToString = typeof Symbol === "function" && typeof Symbol.iterator === "symbol" ? Symbol.prototype.toString : null;
  var hasShammedSymbols = typeof Symbol === "function" && typeof Symbol.iterator === "object";
  var toStringTag = typeof Symbol === "function" && Symbol.toStringTag && (typeof Symbol.toStringTag === hasShammedSymbols ? "object" : "symbol") ? Symbol.toStringTag : null;
  var isEnumerable = Object.prototype.propertyIsEnumerable;
  var gPO = (typeof Reflect === "function" ? Reflect.getPrototypeOf : Object.getPrototypeOf) || ([].__proto__ === Array.prototype ? function(O5) {
    return O5.__proto__;
  } : null);
  function addNumericSeparator(num, str) {
    if (num === Infinity || num === -Infinity || num !== num || num && num > -1e3 && num < 1e3 || $test.call(/e/, str)) {
      return str;
    }
    var sepRegex = /[0-9](?=(?:[0-9]{3})+(?![0-9]))/g;
    if (typeof num === "number") {
      var int = num < 0 ? -$floor(-num) : $floor(num);
      if (int !== num) {
        var intStr = String(int);
        var dec = $slice.call(str, intStr.length + 1);
        return $replace.call(intStr, sepRegex, "$&_") + "." + $replace.call($replace.call(dec, /([0-9]{3})/g, "$&_"), /_$/, "");
      }
    }
    return $replace.call(str, sepRegex, "$&_");
  }
  var utilInspect = empty;
  var inspectCustom = utilInspect.custom;
  var inspectSymbol = isSymbol(inspectCustom) ? inspectCustom : null;
  exports$83 = function inspect_(obj, options, depth, seen) {
    var opts = options || {};
    if (has(opts, "quoteStyle") && opts.quoteStyle !== "single" && opts.quoteStyle !== "double") {
      throw new TypeError('option "quoteStyle" must be "single" or "double"');
    }
    if (has(opts, "maxStringLength") && (typeof opts.maxStringLength === "number" ? opts.maxStringLength < 0 && opts.maxStringLength !== Infinity : opts.maxStringLength !== null)) {
      throw new TypeError('option "maxStringLength", if provided, must be a positive integer, Infinity, or `null`');
    }
    var customInspect = has(opts, "customInspect") ? opts.customInspect : true;
    if (typeof customInspect !== "boolean" && customInspect !== "symbol") {
      throw new TypeError("option \"customInspect\", if provided, must be `true`, `false`, or `'symbol'`");
    }
    if (has(opts, "indent") && opts.indent !== null && opts.indent !== "	" && !(parseInt(opts.indent, 10) === opts.indent && opts.indent > 0)) {
      throw new TypeError('option "indent" must be "\\t", an integer > 0, or `null`');
    }
    if (has(opts, "numericSeparator") && typeof opts.numericSeparator !== "boolean") {
      throw new TypeError('option "numericSeparator", if provided, must be `true` or `false`');
    }
    var numericSeparator = opts.numericSeparator;
    if (typeof obj === "undefined") {
      return "undefined";
    }
    if (obj === null) {
      return "null";
    }
    if (typeof obj === "boolean") {
      return obj ? "true" : "false";
    }
    if (typeof obj === "string") {
      return inspectString(obj, opts);
    }
    if (typeof obj === "number") {
      if (obj === 0) {
        return Infinity / obj > 0 ? "0" : "-0";
      }
      var str = String(obj);
      return numericSeparator ? addNumericSeparator(obj, str) : str;
    }
    if (typeof obj === "bigint") {
      var bigIntStr = String(obj) + "n";
      return numericSeparator ? addNumericSeparator(obj, bigIntStr) : bigIntStr;
    }
    var maxDepth = typeof opts.depth === "undefined" ? 5 : opts.depth;
    if (typeof depth === "undefined") {
      depth = 0;
    }
    if (depth >= maxDepth && maxDepth > 0 && typeof obj === "object") {
      return isArray(obj) ? "[Array]" : "[Object]";
    }
    var indent = getIndent(opts, depth);
    if (typeof seen === "undefined") {
      seen = [];
    } else if (indexOf(seen, obj) >= 0) {
      return "[Circular]";
    }
    function inspect(value, from, noIndent) {
      if (from) {
        seen = $arrSlice.call(seen);
        seen.push(from);
      }
      if (noIndent) {
        var newOpts = {
          depth: opts.depth
        };
        if (has(opts, "quoteStyle")) {
          newOpts.quoteStyle = opts.quoteStyle;
        }
        return inspect_(value, newOpts, depth + 1, seen);
      }
      return inspect_(value, opts, depth + 1, seen);
    }
    if (typeof obj === "function" && !isRegExp(obj)) {
      var name2 = nameOf(obj);
      var keys = arrObjKeys(obj, inspect);
      return "[Function" + (name2 ? ": " + name2 : " (anonymous)") + "]" + (keys.length > 0 ? " { " + $join.call(keys, ", ") + " }" : "");
    }
    if (isSymbol(obj)) {
      var symString = hasShammedSymbols ? $replace.call(String(obj), /^(Symbol\(.*\))_[^)]*$/, "$1") : symToString.call(obj);
      return typeof obj === "object" && !hasShammedSymbols ? markBoxed(symString) : symString;
    }
    if (isElement(obj)) {
      var s6 = "<" + $toLowerCase.call(String(obj.nodeName));
      var attrs = obj.attributes || [];
      for (var i6 = 0; i6 < attrs.length; i6++) {
        s6 += " " + attrs[i6].name + "=" + wrapQuotes(quote(attrs[i6].value), "double", opts);
      }
      s6 += ">";
      if (obj.childNodes && obj.childNodes.length) {
        s6 += "...";
      }
      s6 += "</" + $toLowerCase.call(String(obj.nodeName)) + ">";
      return s6;
    }
    if (isArray(obj)) {
      if (obj.length === 0) {
        return "[]";
      }
      var xs = arrObjKeys(obj, inspect);
      if (indent && !singleLineValues(xs)) {
        return "[" + indentedJoin(xs, indent) + "]";
      }
      return "[ " + $join.call(xs, ", ") + " ]";
    }
    if (isError(obj)) {
      var parts = arrObjKeys(obj, inspect);
      if (!("cause" in Error.prototype) && "cause" in obj && !isEnumerable.call(obj, "cause")) {
        return "{ [" + String(obj) + "] " + $join.call($concat.call("[cause]: " + inspect(obj.cause), parts), ", ") + " }";
      }
      if (parts.length === 0) {
        return "[" + String(obj) + "]";
      }
      return "{ [" + String(obj) + "] " + $join.call(parts, ", ") + " }";
    }
    if (typeof obj === "object" && customInspect) {
      if (inspectSymbol && typeof obj[inspectSymbol] === "function" && utilInspect) {
        return utilInspect(obj, {
          depth: maxDepth - depth
        });
      } else if (customInspect !== "symbol" && typeof obj.inspect === "function") {
        return obj.inspect();
      }
    }
    if (isMap(obj)) {
      var mapParts = [];
      if (mapForEach) {
        mapForEach.call(obj, function(value, key) {
          mapParts.push(inspect(key, obj, true) + " => " + inspect(value, obj));
        });
      }
      return collectionOf("Map", mapSize.call(obj), mapParts, indent);
    }
    if (isSet(obj)) {
      var setParts = [];
      if (setForEach) {
        setForEach.call(obj, function(value) {
          setParts.push(inspect(value, obj));
        });
      }
      return collectionOf("Set", setSize.call(obj), setParts, indent);
    }
    if (isWeakMap(obj)) {
      return weakCollectionOf("WeakMap");
    }
    if (isWeakSet(obj)) {
      return weakCollectionOf("WeakSet");
    }
    if (isWeakRef(obj)) {
      return weakCollectionOf("WeakRef");
    }
    if (isNumber(obj)) {
      return markBoxed(inspect(Number(obj)));
    }
    if (isBigInt(obj)) {
      return markBoxed(inspect(bigIntValueOf.call(obj)));
    }
    if (isBoolean(obj)) {
      return markBoxed(booleanValueOf.call(obj));
    }
    if (isString(obj)) {
      return markBoxed(inspect(String(obj)));
    }
    if (typeof window !== "undefined" && obj === window) {
      return "{ [object Window] }";
    }
    if (typeof globalThis !== "undefined" && obj === globalThis || typeof _global4 !== "undefined" && obj === _global4) {
      return "{ [object globalThis] }";
    }
    if (!isDate(obj) && !isRegExp(obj)) {
      var ys = arrObjKeys(obj, inspect);
      var isPlainObject = gPO ? gPO(obj) === Object.prototype : obj instanceof Object || obj.constructor === Object;
      var protoTag = obj instanceof Object ? "" : "null prototype";
      var stringTag = !isPlainObject && toStringTag && Object(obj) === obj && toStringTag in obj ? $slice.call(toStr(obj), 8, -1) : protoTag ? "Object" : "";
      var constructorTag = isPlainObject || typeof obj.constructor !== "function" ? "" : obj.constructor.name ? obj.constructor.name + " " : "";
      var tag = constructorTag + (stringTag || protoTag ? "[" + $join.call($concat.call([], stringTag || [], protoTag || []), ": ") + "] " : "");
      if (ys.length === 0) {
        return tag + "{}";
      }
      if (indent) {
        return tag + "{" + indentedJoin(ys, indent) + "}";
      }
      return tag + "{ " + $join.call(ys, ", ") + " }";
    }
    return String(obj);
  };
  function wrapQuotes(s6, defaultStyle, opts) {
    var quoteChar = (opts.quoteStyle || defaultStyle) === "double" ? '"' : "'";
    return quoteChar + s6 + quoteChar;
  }
  function quote(s6) {
    return $replace.call(String(s6), /"/g, "&quot;");
  }
  function isArray(obj) {
    return toStr(obj) === "[object Array]" && (!toStringTag || !(typeof obj === "object" && toStringTag in obj));
  }
  function isDate(obj) {
    return toStr(obj) === "[object Date]" && (!toStringTag || !(typeof obj === "object" && toStringTag in obj));
  }
  function isRegExp(obj) {
    return toStr(obj) === "[object RegExp]" && (!toStringTag || !(typeof obj === "object" && toStringTag in obj));
  }
  function isError(obj) {
    return toStr(obj) === "[object Error]" && (!toStringTag || !(typeof obj === "object" && toStringTag in obj));
  }
  function isString(obj) {
    return toStr(obj) === "[object String]" && (!toStringTag || !(typeof obj === "object" && toStringTag in obj));
  }
  function isNumber(obj) {
    return toStr(obj) === "[object Number]" && (!toStringTag || !(typeof obj === "object" && toStringTag in obj));
  }
  function isBoolean(obj) {
    return toStr(obj) === "[object Boolean]" && (!toStringTag || !(typeof obj === "object" && toStringTag in obj));
  }
  function isSymbol(obj) {
    if (hasShammedSymbols) {
      return obj && typeof obj === "object" && obj instanceof Symbol;
    }
    if (typeof obj === "symbol") {
      return true;
    }
    if (!obj || typeof obj !== "object" || !symToString) {
      return false;
    }
    try {
      symToString.call(obj);
      return true;
    } catch (e6) {
    }
    return false;
  }
  function isBigInt(obj) {
    if (!obj || typeof obj !== "object" || !bigIntValueOf) {
      return false;
    }
    try {
      bigIntValueOf.call(obj);
      return true;
    } catch (e6) {
    }
    return false;
  }
  var hasOwn = Object.prototype.hasOwnProperty || function(key) {
    return key in (this || _global4);
  };
  function has(obj, key) {
    return hasOwn.call(obj, key);
  }
  function toStr(obj) {
    return objectToString.call(obj);
  }
  function nameOf(f6) {
    if (f6.name) {
      return f6.name;
    }
    var m5 = $match.call(functionToString.call(f6), /^function\s*([\w$]+)/);
    if (m5) {
      return m5[1];
    }
    return null;
  }
  function indexOf(xs, x4) {
    if (xs.indexOf) {
      return xs.indexOf(x4);
    }
    for (var i6 = 0, l6 = xs.length; i6 < l6; i6++) {
      if (xs[i6] === x4) {
        return i6;
      }
    }
    return -1;
  }
  function isMap(x4) {
    if (!mapSize || !x4 || typeof x4 !== "object") {
      return false;
    }
    try {
      mapSize.call(x4);
      try {
        setSize.call(x4);
      } catch (s6) {
        return true;
      }
      return x4 instanceof Map;
    } catch (e6) {
    }
    return false;
  }
  function isWeakMap(x4) {
    if (!weakMapHas || !x4 || typeof x4 !== "object") {
      return false;
    }
    try {
      weakMapHas.call(x4, weakMapHas);
      try {
        weakSetHas.call(x4, weakSetHas);
      } catch (s6) {
        return true;
      }
      return x4 instanceof WeakMap;
    } catch (e6) {
    }
    return false;
  }
  function isWeakRef(x4) {
    if (!weakRefDeref || !x4 || typeof x4 !== "object") {
      return false;
    }
    try {
      weakRefDeref.call(x4);
      return true;
    } catch (e6) {
    }
    return false;
  }
  function isSet(x4) {
    if (!setSize || !x4 || typeof x4 !== "object") {
      return false;
    }
    try {
      setSize.call(x4);
      try {
        mapSize.call(x4);
      } catch (m5) {
        return true;
      }
      return x4 instanceof Set;
    } catch (e6) {
    }
    return false;
  }
  function isWeakSet(x4) {
    if (!weakSetHas || !x4 || typeof x4 !== "object") {
      return false;
    }
    try {
      weakSetHas.call(x4, weakSetHas);
      try {
        weakMapHas.call(x4, weakMapHas);
      } catch (s6) {
        return true;
      }
      return x4 instanceof WeakSet;
    } catch (e6) {
    }
    return false;
  }
  function isElement(x4) {
    if (!x4 || typeof x4 !== "object") {
      return false;
    }
    if (typeof HTMLElement !== "undefined" && x4 instanceof HTMLElement) {
      return true;
    }
    return typeof x4.nodeName === "string" && typeof x4.getAttribute === "function";
  }
  function inspectString(str, opts) {
    if (str.length > opts.maxStringLength) {
      var remaining = str.length - opts.maxStringLength;
      var trailer = "... " + remaining + " more character" + (remaining > 1 ? "s" : "");
      return inspectString($slice.call(str, 0, opts.maxStringLength), opts) + trailer;
    }
    var s6 = $replace.call($replace.call(str, /(['\\])/g, "\\$1"), /[\x00-\x1f]/g, lowbyte);
    return wrapQuotes(s6, "single", opts);
  }
  function lowbyte(c6) {
    var n6 = c6.charCodeAt(0);
    var x4 = {
      8: "b",
      9: "t",
      10: "n",
      12: "f",
      13: "r"
    }[n6];
    if (x4) {
      return "\\" + x4;
    }
    return "\\x" + (n6 < 16 ? "0" : "") + $toUpperCase.call(n6.toString(16));
  }
  function markBoxed(str) {
    return "Object(" + str + ")";
  }
  function weakCollectionOf(type) {
    return type + " { ? }";
  }
  function collectionOf(type, size, entries, indent) {
    var joinedEntries = indent ? indentedJoin(entries, indent) : $join.call(entries, ", ");
    return type + " (" + size + ") {" + joinedEntries + "}";
  }
  function singleLineValues(xs) {
    for (var i6 = 0; i6 < xs.length; i6++) {
      if (indexOf(xs[i6], "\n") >= 0) {
        return false;
      }
    }
    return true;
  }
  function getIndent(opts, depth) {
    var baseIndent;
    if (opts.indent === "	") {
      baseIndent = "	";
    } else if (typeof opts.indent === "number" && opts.indent > 0) {
      baseIndent = $join.call(Array(opts.indent + 1), " ");
    } else {
      return null;
    }
    return {
      base: baseIndent,
      prev: $join.call(Array(depth + 1), baseIndent)
    };
  }
  function indentedJoin(xs, indent) {
    if (xs.length === 0) {
      return "";
    }
    var lineJoiner = "\n" + indent.prev + indent.base;
    return lineJoiner + $join.call(xs, "," + lineJoiner) + "\n" + indent.prev;
  }
  function arrObjKeys(obj, inspect) {
    var isArr = isArray(obj);
    var xs = [];
    if (isArr) {
      xs.length = obj.length;
      for (var i6 = 0; i6 < obj.length; i6++) {
        xs[i6] = has(obj, i6) ? inspect(obj[i6], obj) : "";
      }
    }
    var syms = typeof gOPS === "function" ? gOPS(obj) : [];
    var symMap;
    if (hasShammedSymbols) {
      symMap = {};
      for (var k4 = 0; k4 < syms.length; k4++) {
        symMap["$" + syms[k4]] = syms[k4];
      }
    }
    for (var key in obj) {
      if (!has(obj, key)) {
        continue;
      }
      if (isArr && String(Number(key)) === key && key < obj.length) {
        continue;
      }
      if (hasShammedSymbols && symMap["$" + key] instanceof Symbol) {
        continue;
      } else if ($test.call(/[^\w$]/, key)) {
        xs.push(inspect(key, obj) + ": " + inspect(obj[key], obj));
      } else {
        xs.push(key + ": " + inspect(obj[key], obj));
      }
    }
    if (typeof gOPS === "function") {
      for (var j4 = 0; j4 < syms.length; j4++) {
        if (isEnumerable.call(obj, syms[j4])) {
          xs.push("[" + inspect(syms[j4]) + "]: " + inspect(obj[syms[j4]], obj));
        }
      }
    }
    return xs;
  }
  return exports$83;
}
function dew$63() {
  if (_dewExec$63) return exports$73;
  _dewExec$63 = true;
  var GetIntrinsic = dew$72();
  var callBound = dew7();
  var inspect = dew$73();
  var $TypeError = dew$e2();
  var $WeakMap = GetIntrinsic("%WeakMap%", true);
  var $Map = GetIntrinsic("%Map%", true);
  var $weakMapGet = callBound("WeakMap.prototype.get", true);
  var $weakMapSet = callBound("WeakMap.prototype.set", true);
  var $weakMapHas = callBound("WeakMap.prototype.has", true);
  var $mapGet = callBound("Map.prototype.get", true);
  var $mapSet = callBound("Map.prototype.set", true);
  var $mapHas = callBound("Map.prototype.has", true);
  var listGetNode = function(list, key) {
    var prev = list;
    var curr;
    for (; (curr = prev.next) !== null; prev = curr) {
      if (curr.key === key) {
        prev.next = curr.next;
        curr.next = /** @type {NonNullable<typeof list.next>} */
        list.next;
        list.next = curr;
        return curr;
      }
    }
  };
  var listGet = function(objects, key) {
    var node = listGetNode(objects, key);
    return node && node.value;
  };
  var listSet = function(objects, key, value) {
    var node = listGetNode(objects, key);
    if (node) {
      node.value = value;
    } else {
      objects.next = /** @type {import('.').ListNode<typeof value>} */
      {
        // eslint-disable-line no-param-reassign, no-extra-parens
        key,
        next: objects.next,
        value
      };
    }
  };
  var listHas = function(objects, key) {
    return !!listGetNode(objects, key);
  };
  exports$73 = function getSideChannel() {
    var $wm;
    var $m;
    var $o;
    var channel = {
      assert: function(key) {
        if (!channel.has(key)) {
          throw new $TypeError("Side channel does not contain " + inspect(key));
        }
      },
      get: function(key) {
        if ($WeakMap && key && (typeof key === "object" || typeof key === "function")) {
          if ($wm) {
            return $weakMapGet($wm, key);
          }
        } else if ($Map) {
          if ($m) {
            return $mapGet($m, key);
          }
        } else {
          if ($o) {
            return listGet($o, key);
          }
        }
      },
      has: function(key) {
        if ($WeakMap && key && (typeof key === "object" || typeof key === "function")) {
          if ($wm) {
            return $weakMapHas($wm, key);
          }
        } else if ($Map) {
          if ($m) {
            return $mapHas($m, key);
          }
        } else {
          if ($o) {
            return listHas($o, key);
          }
        }
        return false;
      },
      set: function(key, value) {
        if ($WeakMap && key && (typeof key === "object" || typeof key === "function")) {
          if (!$wm) {
            $wm = new $WeakMap();
          }
          $weakMapSet($wm, key, value);
        } else if ($Map) {
          if (!$m) {
            $m = new $Map();
          }
          $mapSet($m, key, value);
        } else {
          if (!$o) {
            $o = {
              key: {},
              next: null
            };
          }
          listSet($o, key, value);
        }
      }
    };
    return channel;
  };
  return exports$73;
}
function dew$53() {
  if (_dewExec$53) return exports$63;
  _dewExec$53 = true;
  var replace = String.prototype.replace;
  var percentTwenties = /%20/g;
  var Format = {
    RFC1738: "RFC1738",
    RFC3986: "RFC3986"
  };
  exports$63 = {
    "default": Format.RFC3986,
    formatters: {
      RFC1738: function(value) {
        return replace.call(value, percentTwenties, "+");
      },
      RFC3986: function(value) {
        return String(value);
      }
    },
    RFC1738: Format.RFC1738,
    RFC3986: Format.RFC3986
  };
  return exports$63;
}
function dew$43() {
  if (_dewExec$43) return exports$53;
  _dewExec$43 = true;
  var formats = dew$53();
  var has = Object.prototype.hasOwnProperty;
  var isArray = Array.isArray;
  var hexTable = (function() {
    var array = [];
    for (var i6 = 0; i6 < 256; ++i6) {
      array.push("%" + ((i6 < 16 ? "0" : "") + i6.toString(16)).toUpperCase());
    }
    return array;
  })();
  var compactQueue = function compactQueue2(queue3) {
    while (queue3.length > 1) {
      var item = queue3.pop();
      var obj = item.obj[item.prop];
      if (isArray(obj)) {
        var compacted = [];
        for (var j4 = 0; j4 < obj.length; ++j4) {
          if (typeof obj[j4] !== "undefined") {
            compacted.push(obj[j4]);
          }
        }
        item.obj[item.prop] = compacted;
      }
    }
  };
  var arrayToObject = function arrayToObject2(source, options) {
    var obj = options && options.plainObjects ? /* @__PURE__ */ Object.create(null) : {};
    for (var i6 = 0; i6 < source.length; ++i6) {
      if (typeof source[i6] !== "undefined") {
        obj[i6] = source[i6];
      }
    }
    return obj;
  };
  var merge = function merge2(target, source, options) {
    if (!source) {
      return target;
    }
    if (typeof source !== "object") {
      if (isArray(target)) {
        target.push(source);
      } else if (target && typeof target === "object") {
        if (options && (options.plainObjects || options.allowPrototypes) || !has.call(Object.prototype, source)) {
          target[source] = true;
        }
      } else {
        return [target, source];
      }
      return target;
    }
    if (!target || typeof target !== "object") {
      return [target].concat(source);
    }
    var mergeTarget = target;
    if (isArray(target) && !isArray(source)) {
      mergeTarget = arrayToObject(target, options);
    }
    if (isArray(target) && isArray(source)) {
      source.forEach(function(item, i6) {
        if (has.call(target, i6)) {
          var targetItem = target[i6];
          if (targetItem && typeof targetItem === "object" && item && typeof item === "object") {
            target[i6] = merge2(targetItem, item, options);
          } else {
            target.push(item);
          }
        } else {
          target[i6] = item;
        }
      });
      return target;
    }
    return Object.keys(source).reduce(function(acc, key) {
      var value = source[key];
      if (has.call(acc, key)) {
        acc[key] = merge2(acc[key], value, options);
      } else {
        acc[key] = value;
      }
      return acc;
    }, mergeTarget);
  };
  var assign = function assignSingleSource(target, source) {
    return Object.keys(source).reduce(function(acc, key) {
      acc[key] = source[key];
      return acc;
    }, target);
  };
  var decode2 = function(str, decoder, charset) {
    var strWithoutPlus = str.replace(/\+/g, " ");
    if (charset === "iso-8859-1") {
      return strWithoutPlus.replace(/%[0-9a-f]{2}/gi, unescape);
    }
    try {
      return decodeURIComponent(strWithoutPlus);
    } catch (e6) {
      return strWithoutPlus;
    }
  };
  var limit = 1024;
  var encode2 = function encode3(str, defaultEncoder, charset, kind, format2) {
    if (str.length === 0) {
      return str;
    }
    var string = str;
    if (typeof str === "symbol") {
      string = Symbol.prototype.toString.call(str);
    } else if (typeof str !== "string") {
      string = String(str);
    }
    if (charset === "iso-8859-1") {
      return escape(string).replace(/%u[0-9a-f]{4}/gi, function($0) {
        return "%26%23" + parseInt($0.slice(2), 16) + "%3B";
      });
    }
    var out = "";
    for (var j4 = 0; j4 < string.length; j4 += limit) {
      var segment = string.length >= limit ? string.slice(j4, j4 + limit) : string;
      var arr = [];
      for (var i6 = 0; i6 < segment.length; ++i6) {
        var c6 = segment.charCodeAt(i6);
        if (c6 === 45 || c6 === 46 || c6 === 95 || c6 === 126 || c6 >= 48 && c6 <= 57 || c6 >= 65 && c6 <= 90 || c6 >= 97 && c6 <= 122 || format2 === formats.RFC1738 && (c6 === 40 || c6 === 41)) {
          arr[arr.length] = segment.charAt(i6);
          continue;
        }
        if (c6 < 128) {
          arr[arr.length] = hexTable[c6];
          continue;
        }
        if (c6 < 2048) {
          arr[arr.length] = hexTable[192 | c6 >> 6] + hexTable[128 | c6 & 63];
          continue;
        }
        if (c6 < 55296 || c6 >= 57344) {
          arr[arr.length] = hexTable[224 | c6 >> 12] + hexTable[128 | c6 >> 6 & 63] + hexTable[128 | c6 & 63];
          continue;
        }
        i6 += 1;
        c6 = 65536 + ((c6 & 1023) << 10 | segment.charCodeAt(i6) & 1023);
        arr[arr.length] = hexTable[240 | c6 >> 18] + hexTable[128 | c6 >> 12 & 63] + hexTable[128 | c6 >> 6 & 63] + hexTable[128 | c6 & 63];
      }
      out += arr.join("");
    }
    return out;
  };
  var compact = function compact2(value) {
    var queue3 = [{
      obj: {
        o: value
      },
      prop: "o"
    }];
    var refs = [];
    for (var i6 = 0; i6 < queue3.length; ++i6) {
      var item = queue3[i6];
      var obj = item.obj[item.prop];
      var keys = Object.keys(obj);
      for (var j4 = 0; j4 < keys.length; ++j4) {
        var key = keys[j4];
        var val = obj[key];
        if (typeof val === "object" && val !== null && refs.indexOf(val) === -1) {
          queue3.push({
            obj,
            prop: key
          });
          refs.push(val);
        }
      }
    }
    compactQueue(queue3);
    return value;
  };
  var isRegExp = function isRegExp2(obj) {
    return Object.prototype.toString.call(obj) === "[object RegExp]";
  };
  var isBuffer = function isBuffer2(obj) {
    if (!obj || typeof obj !== "object") {
      return false;
    }
    return !!(obj.constructor && obj.constructor.isBuffer && obj.constructor.isBuffer(obj));
  };
  var combine = function combine2(a6, b5) {
    return [].concat(a6, b5);
  };
  var maybeMap = function maybeMap2(val, fn) {
    if (isArray(val)) {
      var mapped = [];
      for (var i6 = 0; i6 < val.length; i6 += 1) {
        mapped.push(fn(val[i6]));
      }
      return mapped;
    }
    return fn(val);
  };
  exports$53 = {
    arrayToObject,
    assign,
    combine,
    compact,
    decode: decode2,
    encode: encode2,
    isBuffer,
    isRegExp,
    maybeMap,
    merge
  };
  return exports$53;
}
function dew$33() {
  if (_dewExec$33) return exports$43;
  _dewExec$33 = true;
  var getSideChannel = dew$63();
  var utils = dew$43();
  var formats = dew$53();
  var has = Object.prototype.hasOwnProperty;
  var arrayPrefixGenerators = {
    brackets: function brackets(prefix) {
      return prefix + "[]";
    },
    comma: "comma",
    indices: function indices(prefix, key) {
      return prefix + "[" + key + "]";
    },
    repeat: function repeat(prefix) {
      return prefix;
    }
  };
  var isArray = Array.isArray;
  var push = Array.prototype.push;
  var pushToArray = function(arr, valueOrArray) {
    push.apply(arr, isArray(valueOrArray) ? valueOrArray : [valueOrArray]);
  };
  var toISO = Date.prototype.toISOString;
  var defaultFormat = formats["default"];
  var defaults = {
    addQueryPrefix: false,
    allowDots: false,
    allowEmptyArrays: false,
    arrayFormat: "indices",
    charset: "utf-8",
    charsetSentinel: false,
    delimiter: "&",
    encode: true,
    encodeDotInKeys: false,
    encoder: utils.encode,
    encodeValuesOnly: false,
    format: defaultFormat,
    formatter: formats.formatters[defaultFormat],
    // deprecated
    indices: false,
    serializeDate: function serializeDate(date) {
      return toISO.call(date);
    },
    skipNulls: false,
    strictNullHandling: false
  };
  var isNonNullishPrimitive = function isNonNullishPrimitive2(v6) {
    return typeof v6 === "string" || typeof v6 === "number" || typeof v6 === "boolean" || typeof v6 === "symbol" || typeof v6 === "bigint";
  };
  var sentinel = {};
  var stringify = function stringify2(object, prefix, generateArrayPrefix, commaRoundTrip, allowEmptyArrays, strictNullHandling, skipNulls, encodeDotInKeys, encoder, filter, sort, allowDots, serializeDate, format2, formatter, encodeValuesOnly, charset, sideChannel) {
    var obj = object;
    var tmpSc = sideChannel;
    var step = 0;
    var findFlag = false;
    while ((tmpSc = tmpSc.get(sentinel)) !== void 0 && !findFlag) {
      var pos = tmpSc.get(object);
      step += 1;
      if (typeof pos !== "undefined") {
        if (pos === step) {
          throw new RangeError("Cyclic object value");
        } else {
          findFlag = true;
        }
      }
      if (typeof tmpSc.get(sentinel) === "undefined") {
        step = 0;
      }
    }
    if (typeof filter === "function") {
      obj = filter(prefix, obj);
    } else if (obj instanceof Date) {
      obj = serializeDate(obj);
    } else if (generateArrayPrefix === "comma" && isArray(obj)) {
      obj = utils.maybeMap(obj, function(value2) {
        if (value2 instanceof Date) {
          return serializeDate(value2);
        }
        return value2;
      });
    }
    if (obj === null) {
      if (strictNullHandling) {
        return encoder && !encodeValuesOnly ? encoder(prefix, defaults.encoder, charset, "key", format2) : prefix;
      }
      obj = "";
    }
    if (isNonNullishPrimitive(obj) || utils.isBuffer(obj)) {
      if (encoder) {
        var keyValue = encodeValuesOnly ? prefix : encoder(prefix, defaults.encoder, charset, "key", format2);
        return [formatter(keyValue) + "=" + formatter(encoder(obj, defaults.encoder, charset, "value", format2))];
      }
      return [formatter(prefix) + "=" + formatter(String(obj))];
    }
    var values = [];
    if (typeof obj === "undefined") {
      return values;
    }
    var objKeys;
    if (generateArrayPrefix === "comma" && isArray(obj)) {
      if (encodeValuesOnly && encoder) {
        obj = utils.maybeMap(obj, encoder);
      }
      objKeys = [{
        value: obj.length > 0 ? obj.join(",") || null : void 0
      }];
    } else if (isArray(filter)) {
      objKeys = filter;
    } else {
      var keys = Object.keys(obj);
      objKeys = sort ? keys.sort(sort) : keys;
    }
    var encodedPrefix = encodeDotInKeys ? prefix.replace(/\./g, "%2E") : prefix;
    var adjustedPrefix = commaRoundTrip && isArray(obj) && obj.length === 1 ? encodedPrefix + "[]" : encodedPrefix;
    if (allowEmptyArrays && isArray(obj) && obj.length === 0) {
      return adjustedPrefix + "[]";
    }
    for (var j4 = 0; j4 < objKeys.length; ++j4) {
      var key = objKeys[j4];
      var value = typeof key === "object" && typeof key.value !== "undefined" ? key.value : obj[key];
      if (skipNulls && value === null) {
        continue;
      }
      var encodedKey = allowDots && encodeDotInKeys ? key.replace(/\./g, "%2E") : key;
      var keyPrefix = isArray(obj) ? typeof generateArrayPrefix === "function" ? generateArrayPrefix(adjustedPrefix, encodedKey) : adjustedPrefix : adjustedPrefix + (allowDots ? "." + encodedKey : "[" + encodedKey + "]");
      sideChannel.set(object, step);
      var valueSideChannel = getSideChannel();
      valueSideChannel.set(sentinel, sideChannel);
      pushToArray(values, stringify2(value, keyPrefix, generateArrayPrefix, commaRoundTrip, allowEmptyArrays, strictNullHandling, skipNulls, encodeDotInKeys, generateArrayPrefix === "comma" && encodeValuesOnly && isArray(obj) ? null : encoder, filter, sort, allowDots, serializeDate, format2, formatter, encodeValuesOnly, charset, valueSideChannel));
    }
    return values;
  };
  var normalizeStringifyOptions = function normalizeStringifyOptions2(opts) {
    if (!opts) {
      return defaults;
    }
    if (typeof opts.allowEmptyArrays !== "undefined" && typeof opts.allowEmptyArrays !== "boolean") {
      throw new TypeError("`allowEmptyArrays` option can only be `true` or `false`, when provided");
    }
    if (typeof opts.encodeDotInKeys !== "undefined" && typeof opts.encodeDotInKeys !== "boolean") {
      throw new TypeError("`encodeDotInKeys` option can only be `true` or `false`, when provided");
    }
    if (opts.encoder !== null && typeof opts.encoder !== "undefined" && typeof opts.encoder !== "function") {
      throw new TypeError("Encoder has to be a function.");
    }
    var charset = opts.charset || defaults.charset;
    if (typeof opts.charset !== "undefined" && opts.charset !== "utf-8" && opts.charset !== "iso-8859-1") {
      throw new TypeError("The charset option must be either utf-8, iso-8859-1, or undefined");
    }
    var format2 = formats["default"];
    if (typeof opts.format !== "undefined") {
      if (!has.call(formats.formatters, opts.format)) {
        throw new TypeError("Unknown format option provided.");
      }
      format2 = opts.format;
    }
    var formatter = formats.formatters[format2];
    var filter = defaults.filter;
    if (typeof opts.filter === "function" || isArray(opts.filter)) {
      filter = opts.filter;
    }
    var arrayFormat;
    if (opts.arrayFormat in arrayPrefixGenerators) {
      arrayFormat = opts.arrayFormat;
    } else if ("indices" in opts) {
      arrayFormat = opts.indices ? "indices" : "repeat";
    } else {
      arrayFormat = defaults.arrayFormat;
    }
    if ("commaRoundTrip" in opts && typeof opts.commaRoundTrip !== "boolean") {
      throw new TypeError("`commaRoundTrip` must be a boolean, or absent");
    }
    var allowDots = typeof opts.allowDots === "undefined" ? opts.encodeDotInKeys === true ? true : defaults.allowDots : !!opts.allowDots;
    return {
      addQueryPrefix: typeof opts.addQueryPrefix === "boolean" ? opts.addQueryPrefix : defaults.addQueryPrefix,
      allowDots,
      allowEmptyArrays: typeof opts.allowEmptyArrays === "boolean" ? !!opts.allowEmptyArrays : defaults.allowEmptyArrays,
      arrayFormat,
      charset,
      charsetSentinel: typeof opts.charsetSentinel === "boolean" ? opts.charsetSentinel : defaults.charsetSentinel,
      commaRoundTrip: opts.commaRoundTrip,
      delimiter: typeof opts.delimiter === "undefined" ? defaults.delimiter : opts.delimiter,
      encode: typeof opts.encode === "boolean" ? opts.encode : defaults.encode,
      encodeDotInKeys: typeof opts.encodeDotInKeys === "boolean" ? opts.encodeDotInKeys : defaults.encodeDotInKeys,
      encoder: typeof opts.encoder === "function" ? opts.encoder : defaults.encoder,
      encodeValuesOnly: typeof opts.encodeValuesOnly === "boolean" ? opts.encodeValuesOnly : defaults.encodeValuesOnly,
      filter,
      format: format2,
      formatter,
      serializeDate: typeof opts.serializeDate === "function" ? opts.serializeDate : defaults.serializeDate,
      skipNulls: typeof opts.skipNulls === "boolean" ? opts.skipNulls : defaults.skipNulls,
      sort: typeof opts.sort === "function" ? opts.sort : null,
      strictNullHandling: typeof opts.strictNullHandling === "boolean" ? opts.strictNullHandling : defaults.strictNullHandling
    };
  };
  exports$43 = function(object, opts) {
    var obj = object;
    var options = normalizeStringifyOptions(opts);
    var objKeys;
    var filter;
    if (typeof options.filter === "function") {
      filter = options.filter;
      obj = filter("", obj);
    } else if (isArray(options.filter)) {
      filter = options.filter;
      objKeys = filter;
    }
    var keys = [];
    if (typeof obj !== "object" || obj === null) {
      return "";
    }
    var generateArrayPrefix = arrayPrefixGenerators[options.arrayFormat];
    var commaRoundTrip = generateArrayPrefix === "comma" && options.commaRoundTrip;
    if (!objKeys) {
      objKeys = Object.keys(obj);
    }
    if (options.sort) {
      objKeys.sort(options.sort);
    }
    var sideChannel = getSideChannel();
    for (var i6 = 0; i6 < objKeys.length; ++i6) {
      var key = objKeys[i6];
      if (options.skipNulls && obj[key] === null) {
        continue;
      }
      pushToArray(keys, stringify(obj[key], key, generateArrayPrefix, commaRoundTrip, options.allowEmptyArrays, options.strictNullHandling, options.skipNulls, options.encodeDotInKeys, options.encode ? options.encoder : null, options.filter, options.sort, options.allowDots, options.serializeDate, options.format, options.formatter, options.encodeValuesOnly, options.charset, sideChannel));
    }
    var joined = keys.join(options.delimiter);
    var prefix = options.addQueryPrefix === true ? "?" : "";
    if (options.charsetSentinel) {
      if (options.charset === "iso-8859-1") {
        prefix += "utf8=%26%2310003%3B&";
      } else {
        prefix += "utf8=%E2%9C%93&";
      }
    }
    return joined.length > 0 ? prefix + joined : "";
  };
  return exports$43;
}
function dew$24() {
  if (_dewExec$24) return exports$33;
  _dewExec$24 = true;
  var utils = dew$43();
  var has = Object.prototype.hasOwnProperty;
  var isArray = Array.isArray;
  var defaults = {
    allowDots: false,
    allowEmptyArrays: false,
    allowPrototypes: false,
    allowSparse: false,
    arrayLimit: 20,
    charset: "utf-8",
    charsetSentinel: false,
    comma: false,
    decodeDotInKeys: false,
    decoder: utils.decode,
    delimiter: "&",
    depth: 5,
    duplicates: "combine",
    ignoreQueryPrefix: false,
    interpretNumericEntities: false,
    parameterLimit: 1e3,
    parseArrays: true,
    plainObjects: false,
    strictDepth: false,
    strictNullHandling: false
  };
  var interpretNumericEntities = function(str) {
    return str.replace(/&#(\d+);/g, function($0, numberStr) {
      return String.fromCharCode(parseInt(numberStr, 10));
    });
  };
  var parseArrayValue = function(val, options) {
    if (val && typeof val === "string" && options.comma && val.indexOf(",") > -1) {
      return val.split(",");
    }
    return val;
  };
  var isoSentinel = "utf8=%26%2310003%3B";
  var charsetSentinel = "utf8=%E2%9C%93";
  var parseValues = function parseQueryStringValues(str, options) {
    var obj = {
      __proto__: null
    };
    var cleanStr = options.ignoreQueryPrefix ? str.replace(/^\?/, "") : str;
    cleanStr = cleanStr.replace(/%5B/gi, "[").replace(/%5D/gi, "]");
    var limit = options.parameterLimit === Infinity ? void 0 : options.parameterLimit;
    var parts = cleanStr.split(options.delimiter, limit);
    var skipIndex = -1;
    var i6;
    var charset = options.charset;
    if (options.charsetSentinel) {
      for (i6 = 0; i6 < parts.length; ++i6) {
        if (parts[i6].indexOf("utf8=") === 0) {
          if (parts[i6] === charsetSentinel) {
            charset = "utf-8";
          } else if (parts[i6] === isoSentinel) {
            charset = "iso-8859-1";
          }
          skipIndex = i6;
          i6 = parts.length;
        }
      }
    }
    for (i6 = 0; i6 < parts.length; ++i6) {
      if (i6 === skipIndex) {
        continue;
      }
      var part = parts[i6];
      var bracketEqualsPos = part.indexOf("]=");
      var pos = bracketEqualsPos === -1 ? part.indexOf("=") : bracketEqualsPos + 1;
      var key, val;
      if (pos === -1) {
        key = options.decoder(part, defaults.decoder, charset, "key");
        val = options.strictNullHandling ? null : "";
      } else {
        key = options.decoder(part.slice(0, pos), defaults.decoder, charset, "key");
        val = utils.maybeMap(parseArrayValue(part.slice(pos + 1), options), function(encodedVal) {
          return options.decoder(encodedVal, defaults.decoder, charset, "value");
        });
      }
      if (val && options.interpretNumericEntities && charset === "iso-8859-1") {
        val = interpretNumericEntities(val);
      }
      if (part.indexOf("[]=") > -1) {
        val = isArray(val) ? [val] : val;
      }
      var existing = has.call(obj, key);
      if (existing && options.duplicates === "combine") {
        obj[key] = utils.combine(obj[key], val);
      } else if (!existing || options.duplicates === "last") {
        obj[key] = val;
      }
    }
    return obj;
  };
  var parseObject = function(chain, val, options, valuesParsed) {
    var leaf = valuesParsed ? val : parseArrayValue(val, options);
    for (var i6 = chain.length - 1; i6 >= 0; --i6) {
      var obj;
      var root = chain[i6];
      if (root === "[]" && options.parseArrays) {
        obj = options.allowEmptyArrays && (leaf === "" || options.strictNullHandling && leaf === null) ? [] : [].concat(leaf);
      } else {
        obj = options.plainObjects ? /* @__PURE__ */ Object.create(null) : {};
        var cleanRoot = root.charAt(0) === "[" && root.charAt(root.length - 1) === "]" ? root.slice(1, -1) : root;
        var decodedRoot = options.decodeDotInKeys ? cleanRoot.replace(/%2E/g, ".") : cleanRoot;
        var index = parseInt(decodedRoot, 10);
        if (!options.parseArrays && decodedRoot === "") {
          obj = {
            0: leaf
          };
        } else if (!isNaN(index) && root !== decodedRoot && String(index) === decodedRoot && index >= 0 && options.parseArrays && index <= options.arrayLimit) {
          obj = [];
          obj[index] = leaf;
        } else if (decodedRoot !== "__proto__") {
          obj[decodedRoot] = leaf;
        }
      }
      leaf = obj;
    }
    return leaf;
  };
  var parseKeys = function parseQueryStringKeys(givenKey, val, options, valuesParsed) {
    if (!givenKey) {
      return;
    }
    var key = options.allowDots ? givenKey.replace(/\.([^.[]+)/g, "[$1]") : givenKey;
    var brackets = /(\[[^[\]]*])/;
    var child = /(\[[^[\]]*])/g;
    var segment = options.depth > 0 && brackets.exec(key);
    var parent = segment ? key.slice(0, segment.index) : key;
    var keys = [];
    if (parent) {
      if (!options.plainObjects && has.call(Object.prototype, parent)) {
        if (!options.allowPrototypes) {
          return;
        }
      }
      keys.push(parent);
    }
    var i6 = 0;
    while (options.depth > 0 && (segment = child.exec(key)) !== null && i6 < options.depth) {
      i6 += 1;
      if (!options.plainObjects && has.call(Object.prototype, segment[1].slice(1, -1))) {
        if (!options.allowPrototypes) {
          return;
        }
      }
      keys.push(segment[1]);
    }
    if (segment) {
      if (options.strictDepth === true) {
        throw new RangeError("Input depth exceeded depth option of " + options.depth + " and strictDepth is true");
      }
      keys.push("[" + key.slice(segment.index) + "]");
    }
    return parseObject(keys, val, options, valuesParsed);
  };
  var normalizeParseOptions = function normalizeParseOptions2(opts) {
    if (!opts) {
      return defaults;
    }
    if (typeof opts.allowEmptyArrays !== "undefined" && typeof opts.allowEmptyArrays !== "boolean") {
      throw new TypeError("`allowEmptyArrays` option can only be `true` or `false`, when provided");
    }
    if (typeof opts.decodeDotInKeys !== "undefined" && typeof opts.decodeDotInKeys !== "boolean") {
      throw new TypeError("`decodeDotInKeys` option can only be `true` or `false`, when provided");
    }
    if (opts.decoder !== null && typeof opts.decoder !== "undefined" && typeof opts.decoder !== "function") {
      throw new TypeError("Decoder has to be a function.");
    }
    if (typeof opts.charset !== "undefined" && opts.charset !== "utf-8" && opts.charset !== "iso-8859-1") {
      throw new TypeError("The charset option must be either utf-8, iso-8859-1, or undefined");
    }
    var charset = typeof opts.charset === "undefined" ? defaults.charset : opts.charset;
    var duplicates = typeof opts.duplicates === "undefined" ? defaults.duplicates : opts.duplicates;
    if (duplicates !== "combine" && duplicates !== "first" && duplicates !== "last") {
      throw new TypeError("The duplicates option must be either combine, first, or last");
    }
    var allowDots = typeof opts.allowDots === "undefined" ? opts.decodeDotInKeys === true ? true : defaults.allowDots : !!opts.allowDots;
    return {
      allowDots,
      allowEmptyArrays: typeof opts.allowEmptyArrays === "boolean" ? !!opts.allowEmptyArrays : defaults.allowEmptyArrays,
      allowPrototypes: typeof opts.allowPrototypes === "boolean" ? opts.allowPrototypes : defaults.allowPrototypes,
      allowSparse: typeof opts.allowSparse === "boolean" ? opts.allowSparse : defaults.allowSparse,
      arrayLimit: typeof opts.arrayLimit === "number" ? opts.arrayLimit : defaults.arrayLimit,
      charset,
      charsetSentinel: typeof opts.charsetSentinel === "boolean" ? opts.charsetSentinel : defaults.charsetSentinel,
      comma: typeof opts.comma === "boolean" ? opts.comma : defaults.comma,
      decodeDotInKeys: typeof opts.decodeDotInKeys === "boolean" ? opts.decodeDotInKeys : defaults.decodeDotInKeys,
      decoder: typeof opts.decoder === "function" ? opts.decoder : defaults.decoder,
      delimiter: typeof opts.delimiter === "string" || utils.isRegExp(opts.delimiter) ? opts.delimiter : defaults.delimiter,
      // eslint-disable-next-line no-implicit-coercion, no-extra-parens
      depth: typeof opts.depth === "number" || opts.depth === false ? +opts.depth : defaults.depth,
      duplicates,
      ignoreQueryPrefix: opts.ignoreQueryPrefix === true,
      interpretNumericEntities: typeof opts.interpretNumericEntities === "boolean" ? opts.interpretNumericEntities : defaults.interpretNumericEntities,
      parameterLimit: typeof opts.parameterLimit === "number" ? opts.parameterLimit : defaults.parameterLimit,
      parseArrays: opts.parseArrays !== false,
      plainObjects: typeof opts.plainObjects === "boolean" ? opts.plainObjects : defaults.plainObjects,
      strictDepth: typeof opts.strictDepth === "boolean" ? !!opts.strictDepth : defaults.strictDepth,
      strictNullHandling: typeof opts.strictNullHandling === "boolean" ? opts.strictNullHandling : defaults.strictNullHandling
    };
  };
  exports$33 = function(str, opts) {
    var options = normalizeParseOptions(opts);
    if (str === "" || str === null || typeof str === "undefined") {
      return options.plainObjects ? /* @__PURE__ */ Object.create(null) : {};
    }
    var tempObj = typeof str === "string" ? parseValues(str, options) : str;
    var obj = options.plainObjects ? /* @__PURE__ */ Object.create(null) : {};
    var keys = Object.keys(tempObj);
    for (var i6 = 0; i6 < keys.length; ++i6) {
      var key = keys[i6];
      var newObj = parseKeys(key, tempObj[key], options, typeof str === "string");
      obj = utils.merge(obj, newObj, options);
    }
    if (options.allowSparse === true) {
      return obj;
    }
    return utils.compact(obj);
  };
  return exports$33;
}
function dew$15() {
  if (_dewExec$15) return exports$25;
  _dewExec$15 = true;
  var stringify = dew$33();
  var parse2 = dew$24();
  var formats = dew$53();
  exports$25 = {
    formats,
    parse: parse2,
    stringify
  };
  return exports$25;
}
function dew9() {
  if (_dewExec9) return exports$18;
  _dewExec9 = true;
  var punycode = exports7;
  function Url2() {
    this.protocol = null;
    this.slashes = null;
    this.auth = null;
    this.host = null;
    this.port = null;
    this.hostname = null;
    this.hash = null;
    this.search = null;
    this.query = null;
    this.pathname = null;
    this.path = null;
    this.href = null;
  }
  var protocolPattern = /^([a-z0-9.+-]+:)/i, portPattern = /:[0-9]*$/, simplePathPattern = /^(\/\/?(?!\/)[^?\s]*)(\?[^\s]*)?$/, delims = ["<", ">", '"', "`", " ", "\r", "\n", "	"], unwise = ["{", "}", "|", "\\", "^", "`"].concat(delims), autoEscape = ["'"].concat(unwise), nonHostChars = ["%", "/", "?", ";", "#"].concat(autoEscape), hostEndingChars = ["/", "?", "#"], hostnameMaxLen = 255, hostnamePartPattern = /^[+a-z0-9A-Z_-]{0,63}$/, hostnamePartStart = /^([+a-z0-9A-Z_-]{0,63})(.*)$/, unsafeProtocol = {
    javascript: true,
    "javascript:": true
  }, hostlessProtocol = {
    javascript: true,
    "javascript:": true
  }, slashedProtocol = {
    http: true,
    https: true,
    ftp: true,
    gopher: true,
    file: true,
    "http:": true,
    "https:": true,
    "ftp:": true,
    "gopher:": true,
    "file:": true
  }, querystring = dew$15();
  function urlParse(url, parseQueryString, slashesDenoteHost) {
    if (url && typeof url === "object" && url instanceof Url2) {
      return url;
    }
    var u6 = new Url2();
    u6.parse(url, parseQueryString, slashesDenoteHost);
    return u6;
  }
  Url2.prototype.parse = function(url, parseQueryString, slashesDenoteHost) {
    if (typeof url !== "string") {
      throw new TypeError("Parameter 'url' must be a string, not " + typeof url);
    }
    var queryIndex = url.indexOf("?"), splitter = queryIndex !== -1 && queryIndex < url.indexOf("#") ? "?" : "#", uSplit = url.split(splitter), slashRegex = /\\/g;
    uSplit[0] = uSplit[0].replace(slashRegex, "/");
    url = uSplit.join(splitter);
    var rest = url;
    rest = rest.trim();
    if (!slashesDenoteHost && url.split("#").length === 1) {
      var simplePath = simplePathPattern.exec(rest);
      if (simplePath) {
        this.path = rest;
        this.href = rest;
        this.pathname = simplePath[1];
        if (simplePath[2]) {
          this.search = simplePath[2];
          if (parseQueryString) {
            this.query = querystring.parse(this.search.substr(1));
          } else {
            this.query = this.search.substr(1);
          }
        } else if (parseQueryString) {
          this.search = "";
          this.query = {};
        }
        return this;
      }
    }
    var proto = protocolPattern.exec(rest);
    if (proto) {
      proto = proto[0];
      var lowerProto = proto.toLowerCase();
      this.protocol = lowerProto;
      rest = rest.substr(proto.length);
    }
    if (slashesDenoteHost || proto || rest.match(/^\/\/[^@/]+@[^@/]+/)) {
      var slashes = rest.substr(0, 2) === "//";
      if (slashes && !(proto && hostlessProtocol[proto])) {
        rest = rest.substr(2);
        this.slashes = true;
      }
    }
    if (!hostlessProtocol[proto] && (slashes || proto && !slashedProtocol[proto])) {
      var hostEnd = -1;
      for (var i6 = 0; i6 < hostEndingChars.length; i6++) {
        var hec = rest.indexOf(hostEndingChars[i6]);
        if (hec !== -1 && (hostEnd === -1 || hec < hostEnd)) {
          hostEnd = hec;
        }
      }
      var auth, atSign;
      if (hostEnd === -1) {
        atSign = rest.lastIndexOf("@");
      } else {
        atSign = rest.lastIndexOf("@", hostEnd);
      }
      if (atSign !== -1) {
        auth = rest.slice(0, atSign);
        rest = rest.slice(atSign + 1);
        this.auth = decodeURIComponent(auth);
      }
      hostEnd = -1;
      for (var i6 = 0; i6 < nonHostChars.length; i6++) {
        var hec = rest.indexOf(nonHostChars[i6]);
        if (hec !== -1 && (hostEnd === -1 || hec < hostEnd)) {
          hostEnd = hec;
        }
      }
      if (hostEnd === -1) {
        hostEnd = rest.length;
      }
      this.host = rest.slice(0, hostEnd);
      rest = rest.slice(hostEnd);
      this.parseHost();
      this.hostname = this.hostname || "";
      var ipv6Hostname = this.hostname[0] === "[" && this.hostname[this.hostname.length - 1] === "]";
      if (!ipv6Hostname) {
        var hostparts = this.hostname.split(/\./);
        for (var i6 = 0, l6 = hostparts.length; i6 < l6; i6++) {
          var part = hostparts[i6];
          if (!part) {
            continue;
          }
          if (!part.match(hostnamePartPattern)) {
            var newpart = "";
            for (var j4 = 0, k4 = part.length; j4 < k4; j4++) {
              if (part.charCodeAt(j4) > 127) {
                newpart += "x";
              } else {
                newpart += part[j4];
              }
            }
            if (!newpart.match(hostnamePartPattern)) {
              var validParts = hostparts.slice(0, i6);
              var notHost = hostparts.slice(i6 + 1);
              var bit = part.match(hostnamePartStart);
              if (bit) {
                validParts.push(bit[1]);
                notHost.unshift(bit[2]);
              }
              if (notHost.length) {
                rest = "/" + notHost.join(".") + rest;
              }
              this.hostname = validParts.join(".");
              break;
            }
          }
        }
      }
      if (this.hostname.length > hostnameMaxLen) {
        this.hostname = "";
      } else {
        this.hostname = this.hostname.toLowerCase();
      }
      if (!ipv6Hostname) {
        this.hostname = punycode.toASCII(this.hostname);
      }
      var p6 = this.port ? ":" + this.port : "";
      var h6 = this.hostname || "";
      this.host = h6 + p6;
      this.href += this.host;
      if (ipv6Hostname) {
        this.hostname = this.hostname.substr(1, this.hostname.length - 2);
        if (rest[0] !== "/") {
          rest = "/" + rest;
        }
      }
    }
    if (!unsafeProtocol[lowerProto]) {
      for (var i6 = 0, l6 = autoEscape.length; i6 < l6; i6++) {
        var ae2 = autoEscape[i6];
        if (rest.indexOf(ae2) === -1) {
          continue;
        }
        var esc = encodeURIComponent(ae2);
        if (esc === ae2) {
          esc = escape(ae2);
        }
        rest = rest.split(ae2).join(esc);
      }
    }
    var hash = rest.indexOf("#");
    if (hash !== -1) {
      this.hash = rest.substr(hash);
      rest = rest.slice(0, hash);
    }
    var qm = rest.indexOf("?");
    if (qm !== -1) {
      this.search = rest.substr(qm);
      this.query = rest.substr(qm + 1);
      if (parseQueryString) {
        this.query = querystring.parse(this.query);
      }
      rest = rest.slice(0, qm);
    } else if (parseQueryString) {
      this.search = "";
      this.query = {};
    }
    if (rest) {
      this.pathname = rest;
    }
    if (slashedProtocol[lowerProto] && this.hostname && !this.pathname) {
      this.pathname = "/";
    }
    if (this.pathname || this.search) {
      var p6 = this.pathname || "";
      var s6 = this.search || "";
      this.path = p6 + s6;
    }
    this.href = this.format();
    return this;
  };
  function urlFormat(obj) {
    if (typeof obj === "string") {
      obj = urlParse(obj);
    }
    if (!(obj instanceof Url2)) {
      return Url2.prototype.format.call(obj);
    }
    return obj.format();
  }
  Url2.prototype.format = function() {
    var auth = this.auth || "";
    if (auth) {
      auth = encodeURIComponent(auth);
      auth = auth.replace(/%3A/i, ":");
      auth += "@";
    }
    var protocol = this.protocol || "", pathname = this.pathname || "", hash = this.hash || "", host = false, query = "";
    if (this.host) {
      host = auth + this.host;
    } else if (this.hostname) {
      host = auth + (this.hostname.indexOf(":") === -1 ? this.hostname : "[" + this.hostname + "]");
      if (this.port) {
        host += ":" + this.port;
      }
    }
    if (this.query && typeof this.query === "object" && Object.keys(this.query).length) {
      query = querystring.stringify(this.query, {
        arrayFormat: "repeat",
        addQueryPrefix: false
      });
    }
    var search = this.search || query && "?" + query || "";
    if (protocol && protocol.substr(-1) !== ":") {
      protocol += ":";
    }
    if (this.slashes || (!protocol || slashedProtocol[protocol]) && host !== false) {
      host = "//" + (host || "");
      if (pathname && pathname.charAt(0) !== "/") {
        pathname = "/" + pathname;
      }
    } else if (!host) {
      host = "";
    }
    if (hash && hash.charAt(0) !== "#") {
      hash = "#" + hash;
    }
    if (search && search.charAt(0) !== "?") {
      search = "?" + search;
    }
    pathname = pathname.replace(/[?#]/g, function(match) {
      return encodeURIComponent(match);
    });
    search = search.replace("#", "%23");
    return protocol + host + pathname + search + hash;
  };
  function urlResolve(source, relative) {
    return urlParse(source, false, true).resolve(relative);
  }
  Url2.prototype.resolve = function(relative) {
    return this.resolveObject(urlParse(relative, false, true)).format();
  };
  function urlResolveObject(source, relative) {
    if (!source) {
      return relative;
    }
    return urlParse(source, false, true).resolveObject(relative);
  }
  Url2.prototype.resolveObject = function(relative) {
    if (typeof relative === "string") {
      var rel = new Url2();
      rel.parse(relative, false, true);
      relative = rel;
    }
    var result = new Url2();
    var tkeys = Object.keys(this);
    for (var tk = 0; tk < tkeys.length; tk++) {
      var tkey = tkeys[tk];
      result[tkey] = this[tkey];
    }
    result.hash = relative.hash;
    if (relative.href === "") {
      result.href = result.format();
      return result;
    }
    if (relative.slashes && !relative.protocol) {
      var rkeys = Object.keys(relative);
      for (var rk = 0; rk < rkeys.length; rk++) {
        var rkey = rkeys[rk];
        if (rkey !== "protocol") {
          result[rkey] = relative[rkey];
        }
      }
      if (slashedProtocol[result.protocol] && result.hostname && !result.pathname) {
        result.pathname = "/";
        result.path = result.pathname;
      }
      result.href = result.format();
      return result;
    }
    if (relative.protocol && relative.protocol !== result.protocol) {
      if (!slashedProtocol[relative.protocol]) {
        var keys = Object.keys(relative);
        for (var v6 = 0; v6 < keys.length; v6++) {
          var k4 = keys[v6];
          result[k4] = relative[k4];
        }
        result.href = result.format();
        return result;
      }
      result.protocol = relative.protocol;
      if (!relative.host && !hostlessProtocol[relative.protocol]) {
        var relPath = (relative.pathname || "").split("/");
        while (relPath.length && !(relative.host = relPath.shift())) {
        }
        if (!relative.host) {
          relative.host = "";
        }
        if (!relative.hostname) {
          relative.hostname = "";
        }
        if (relPath[0] !== "") {
          relPath.unshift("");
        }
        if (relPath.length < 2) {
          relPath.unshift("");
        }
        result.pathname = relPath.join("/");
      } else {
        result.pathname = relative.pathname;
      }
      result.search = relative.search;
      result.query = relative.query;
      result.host = relative.host || "";
      result.auth = relative.auth;
      result.hostname = relative.hostname || relative.host;
      result.port = relative.port;
      if (result.pathname || result.search) {
        var p6 = result.pathname || "";
        var s6 = result.search || "";
        result.path = p6 + s6;
      }
      result.slashes = result.slashes || relative.slashes;
      result.href = result.format();
      return result;
    }
    var isSourceAbs = result.pathname && result.pathname.charAt(0) === "/", isRelAbs = relative.host || relative.pathname && relative.pathname.charAt(0) === "/", mustEndAbs = isRelAbs || isSourceAbs || result.host && relative.pathname, removeAllDots = mustEndAbs, srcPath = result.pathname && result.pathname.split("/") || [], relPath = relative.pathname && relative.pathname.split("/") || [], psychotic = result.protocol && !slashedProtocol[result.protocol];
    if (psychotic) {
      result.hostname = "";
      result.port = null;
      if (result.host) {
        if (srcPath[0] === "") {
          srcPath[0] = result.host;
        } else {
          srcPath.unshift(result.host);
        }
      }
      result.host = "";
      if (relative.protocol) {
        relative.hostname = null;
        relative.port = null;
        if (relative.host) {
          if (relPath[0] === "") {
            relPath[0] = relative.host;
          } else {
            relPath.unshift(relative.host);
          }
        }
        relative.host = null;
      }
      mustEndAbs = mustEndAbs && (relPath[0] === "" || srcPath[0] === "");
    }
    if (isRelAbs) {
      result.host = relative.host || relative.host === "" ? relative.host : result.host;
      result.hostname = relative.hostname || relative.hostname === "" ? relative.hostname : result.hostname;
      result.search = relative.search;
      result.query = relative.query;
      srcPath = relPath;
    } else if (relPath.length) {
      if (!srcPath) {
        srcPath = [];
      }
      srcPath.pop();
      srcPath = srcPath.concat(relPath);
      result.search = relative.search;
      result.query = relative.query;
    } else if (relative.search != null) {
      if (psychotic) {
        result.host = srcPath.shift();
        result.hostname = result.host;
        var authInHost = result.host && result.host.indexOf("@") > 0 ? result.host.split("@") : false;
        if (authInHost) {
          result.auth = authInHost.shift();
          result.hostname = authInHost.shift();
          result.host = result.hostname;
        }
      }
      result.search = relative.search;
      result.query = relative.query;
      if (result.pathname !== null || result.search !== null) {
        result.path = (result.pathname ? result.pathname : "") + (result.search ? result.search : "");
      }
      result.href = result.format();
      return result;
    }
    if (!srcPath.length) {
      result.pathname = null;
      if (result.search) {
        result.path = "/" + result.search;
      } else {
        result.path = null;
      }
      result.href = result.format();
      return result;
    }
    var last = srcPath.slice(-1)[0];
    var hasTrailingSlash = (result.host || relative.host || srcPath.length > 1) && (last === "." || last === "..") || last === "";
    var up = 0;
    for (var i6 = srcPath.length; i6 >= 0; i6--) {
      last = srcPath[i6];
      if (last === ".") {
        srcPath.splice(i6, 1);
      } else if (last === "..") {
        srcPath.splice(i6, 1);
        up++;
      } else if (up) {
        srcPath.splice(i6, 1);
        up--;
      }
    }
    if (!mustEndAbs && !removeAllDots) {
      for (; up--; up) {
        srcPath.unshift("..");
      }
    }
    if (mustEndAbs && srcPath[0] !== "" && (!srcPath[0] || srcPath[0].charAt(0) !== "/")) {
      srcPath.unshift("");
    }
    if (hasTrailingSlash && srcPath.join("/").substr(-1) !== "/") {
      srcPath.push("");
    }
    var isAbsolute = srcPath[0] === "" || srcPath[0] && srcPath[0].charAt(0) === "/";
    if (psychotic) {
      result.hostname = isAbsolute ? "" : srcPath.length ? srcPath.shift() : "";
      result.host = result.hostname;
      var authInHost = result.host && result.host.indexOf("@") > 0 ? result.host.split("@") : false;
      if (authInHost) {
        result.auth = authInHost.shift();
        result.hostname = authInHost.shift();
        result.host = result.hostname;
      }
    }
    mustEndAbs = mustEndAbs || result.host && srcPath.length;
    if (mustEndAbs && !isAbsolute) {
      srcPath.unshift("");
    }
    if (srcPath.length > 0) {
      result.pathname = srcPath.join("/");
    } else {
      result.pathname = null;
      result.path = null;
    }
    if (result.pathname !== null || result.search !== null) {
      result.path = (result.pathname ? result.pathname : "") + (result.search ? result.search : "");
    }
    result.auth = relative.auth || result.auth;
    result.slashes = result.slashes || relative.slashes;
    result.href = result.format();
    return result;
  };
  Url2.prototype.parseHost = function() {
    var host = this.host;
    var port = portPattern.exec(host);
    if (port) {
      port = port[0];
      if (port !== ":") {
        this.port = port.substr(1);
      }
      host = host.substr(0, host.length - port.length);
    }
    if (host) {
      this.hostname = host;
    }
  };
  exports$18.parse = urlParse;
  exports$18.resolve = urlResolve;
  exports$18.resolveObject = urlResolveObject;
  exports$18.format = urlFormat;
  exports$18.Url = Url2;
  return exports$18;
}
function fileURLToPath2(path2) {
  if (typeof path2 === "string") path2 = new URL(path2);
  else if (!(path2 instanceof URL)) {
    throw new Deno.errors.InvalidData(
      "invalid argument path , must be a string or URL"
    );
  }
  if (path2.protocol !== "file:") {
    throw new Deno.errors.InvalidData("invalid url scheme");
  }
  return isWindows2 ? getPathFromURLWin2(path2) : getPathFromURLPosix2(path2);
}
function getPathFromURLWin2(url) {
  const hostname = url.hostname;
  let pathname = url.pathname;
  for (let n6 = 0; n6 < pathname.length; n6++) {
    if (pathname[n6] === "%") {
      const third = pathname.codePointAt(n6 + 2) || 32;
      if (pathname[n6 + 1] === "2" && third === 102 || // 2f 2F /
      pathname[n6 + 1] === "5" && third === 99) {
        throw new Deno.errors.InvalidData(
          "must not include encoded \\ or / characters"
        );
      }
    }
  }
  pathname = pathname.replace(forwardSlashRegEx2, "\\");
  pathname = decodeURIComponent(pathname);
  if (hostname !== "") {
    return `\\\\${hostname}${pathname}`;
  } else {
    const letter = pathname.codePointAt(1) | 32;
    const sep = pathname[2];
    if (letter < CHAR_LOWERCASE_A2 || letter > CHAR_LOWERCASE_Z2 || // a..z A..Z
    sep !== ":") {
      throw new Deno.errors.InvalidData("file url path must be absolute");
    }
    return pathname.slice(1);
  }
}
function getPathFromURLPosix2(url) {
  if (url.hostname !== "") {
    throw new Deno.errors.InvalidData("invalid file url hostname");
  }
  const pathname = url.pathname;
  for (let n6 = 0; n6 < pathname.length; n6++) {
    if (pathname[n6] === "%") {
      const third = pathname.codePointAt(n6 + 2) || 32;
      if (pathname[n6 + 1] === "2" && third === 102) {
        throw new Deno.errors.InvalidData(
          "must not include encoded / characters"
        );
      }
    }
  }
  return decodeURIComponent(pathname);
}
function pathToFileURL2(filepath) {
  let resolved = exports9.resolve(filepath);
  const filePathLast = filepath.charCodeAt(filepath.length - 1);
  if ((filePathLast === CHAR_FORWARD_SLASH2 || isWindows2 && filePathLast === CHAR_BACKWARD_SLASH2) && resolved[resolved.length - 1] !== exports9.sep) {
    resolved += "/";
  }
  const outURL = new URL("file://");
  if (resolved.includes("%")) resolved = resolved.replace(percentRegEx2, "%25");
  if (!isWindows2 && resolved.includes("\\")) {
    resolved = resolved.replace(backslashRegEx2, "%5C");
  }
  if (resolved.includes("\n")) resolved = resolved.replace(newlineRegEx2, "%0A");
  if (resolved.includes("\r")) {
    resolved = resolved.replace(carriageReturnRegEx2, "%0D");
  }
  if (resolved.includes("	")) resolved = resolved.replace(tabRegEx2, "%09");
  outURL.pathname = resolved;
  return outURL;
}
var empty, exports$83, _dewExec$73, _global4, exports$73, _dewExec$63, exports$63, _dewExec$53, exports$53, _dewExec$43, exports$43, _dewExec$33, exports$33, _dewExec$24, exports$25, _dewExec$15, exports$18, _dewExec9, exports10, processPlatform2, Url, format, resolve, resolveObject, parse, _URL, CHAR_BACKWARD_SLASH2, CHAR_FORWARD_SLASH2, CHAR_LOWERCASE_A2, CHAR_LOWERCASE_Z2, isWindows2, forwardSlashRegEx2, percentRegEx2, backslashRegEx2, newlineRegEx2, carriageReturnRegEx2, tabRegEx2;
var init_url = __esm({
  "node_modules/@jspm/core/nodelibs/browser/url.js"() {
    init_dirname();
    init_buffer2();
    init_process2();
    init_punycode();
    init_chunk_DtcTpLWz();
    init_chunk_BlJi4mNy();
    init_chunk_DEMDiNwt();
    empty = Object.freeze(/* @__PURE__ */ Object.create(null));
    exports$83 = {};
    _dewExec$73 = false;
    _global4 = typeof globalThis !== "undefined" ? globalThis : typeof self !== "undefined" ? self : global;
    exports$73 = {};
    _dewExec$63 = false;
    exports$63 = {};
    _dewExec$53 = false;
    exports$53 = {};
    _dewExec$43 = false;
    exports$43 = {};
    _dewExec$33 = false;
    exports$33 = {};
    _dewExec$24 = false;
    exports$25 = {};
    _dewExec$15 = false;
    exports$18 = {};
    _dewExec9 = false;
    exports10 = dew9();
    exports10["parse"];
    exports10["resolve"];
    exports10["resolveObject"];
    exports10["format"];
    exports10["Url"];
    processPlatform2 = typeof Deno !== "undefined" ? Deno.build.os === "windows" ? "win32" : Deno.build.os : void 0;
    exports10.URL = typeof URL !== "undefined" ? URL : null;
    exports10.pathToFileURL = pathToFileURL2;
    exports10.fileURLToPath = fileURLToPath2;
    Url = exports10.Url;
    format = exports10.format;
    resolve = exports10.resolve;
    resolveObject = exports10.resolveObject;
    parse = exports10.parse;
    _URL = exports10.URL;
    CHAR_BACKWARD_SLASH2 = 92;
    CHAR_FORWARD_SLASH2 = 47;
    CHAR_LOWERCASE_A2 = 97;
    CHAR_LOWERCASE_Z2 = 122;
    isWindows2 = processPlatform2 === "win32";
    forwardSlashRegEx2 = /\//g;
    percentRegEx2 = /%/g;
    backslashRegEx2 = /\\/g;
    newlineRegEx2 = /\n/g;
    carriageReturnRegEx2 = /\r/g;
    tabRegEx2 = /\t/g;
  }
});

// node_modules/@jspm/core/nodelibs/browser/fs.js
function dew$f3() {
  if (_dewExec$f3) return exports$h2;
  _dewExec$f3 = true;
  Object.defineProperty(exports$h2, "__esModule", {
    value: true
  });
  exports$h2.constants = void 0;
  exports$h2.constants = {
    O_RDONLY: 0,
    O_WRONLY: 1,
    O_RDWR: 2,
    S_IFMT: 61440,
    S_IFREG: 32768,
    S_IFDIR: 16384,
    S_IFCHR: 8192,
    S_IFBLK: 24576,
    S_IFIFO: 4096,
    S_IFLNK: 40960,
    S_IFSOCK: 49152,
    O_CREAT: 64,
    O_EXCL: 128,
    O_NOCTTY: 256,
    O_TRUNC: 512,
    O_APPEND: 1024,
    O_DIRECTORY: 65536,
    O_NOATIME: 262144,
    O_NOFOLLOW: 131072,
    O_SYNC: 1052672,
    O_DIRECT: 16384,
    O_NONBLOCK: 2048,
    S_IRWXU: 448,
    S_IRUSR: 256,
    S_IWUSR: 128,
    S_IXUSR: 64,
    S_IRWXG: 56,
    S_IRGRP: 32,
    S_IWGRP: 16,
    S_IXGRP: 8,
    S_IRWXO: 7,
    S_IROTH: 4,
    S_IWOTH: 2,
    S_IXOTH: 1,
    F_OK: 0,
    R_OK: 4,
    W_OK: 2,
    X_OK: 1,
    UV_FS_SYMLINK_DIR: 1,
    UV_FS_SYMLINK_JUNCTION: 2,
    UV_FS_COPYFILE_EXCL: 1,
    UV_FS_COPYFILE_FICLONE: 2,
    UV_FS_COPYFILE_FICLONE_FORCE: 4,
    COPYFILE_EXCL: 1,
    COPYFILE_FICLONE: 2,
    COPYFILE_FICLONE_FORCE: 4
  };
  return exports$h2;
}
function dew$e3() {
  if (_dewExec$e3) return exports$g3;
  _dewExec$e3 = true;
  if (typeof BigInt === "function") exports$g3.default = BigInt;
  else exports$g3.default = function BigIntNotSupported() {
    throw new Error("BigInt is not supported in this environment.");
  };
  return exports$g3;
}
function dew$d3() {
  if (_dewExec$d3) return exports$f3;
  _dewExec$d3 = true;
  Object.defineProperty(exports$f3, "__esModule", {
    value: true
  });
  exports$f3.Stats = void 0;
  var constants_1 = dew$f3();
  var getBigInt_1 = dew$e3();
  var S_IFMT = constants_1.constants.S_IFMT, S_IFDIR = constants_1.constants.S_IFDIR, S_IFREG = constants_1.constants.S_IFREG, S_IFBLK = constants_1.constants.S_IFBLK, S_IFCHR = constants_1.constants.S_IFCHR, S_IFLNK = constants_1.constants.S_IFLNK, S_IFIFO = constants_1.constants.S_IFIFO, S_IFSOCK = constants_1.constants.S_IFSOCK;
  var Stats2 = (
    /** @class */
    (function() {
      function Stats3() {
      }
      Stats3.build = function(node, bigint) {
        if (bigint === void 0) {
          bigint = false;
        }
        var stats = new Stats3();
        var uid = node.uid, gid = node.gid, atime = node.atime, mtime = node.mtime, ctime = node.ctime;
        var getStatNumber = !bigint ? function(number) {
          return number;
        } : getBigInt_1.default;
        stats.uid = getStatNumber(uid);
        stats.gid = getStatNumber(gid);
        stats.rdev = getStatNumber(0);
        stats.blksize = getStatNumber(4096);
        stats.ino = getStatNumber(node.ino);
        stats.size = getStatNumber(node.getSize());
        stats.blocks = getStatNumber(1);
        stats.atime = atime;
        stats.mtime = mtime;
        stats.ctime = ctime;
        stats.birthtime = ctime;
        stats.atimeMs = getStatNumber(atime.getTime());
        stats.mtimeMs = getStatNumber(mtime.getTime());
        var ctimeMs = getStatNumber(ctime.getTime());
        stats.ctimeMs = ctimeMs;
        stats.birthtimeMs = ctimeMs;
        stats.dev = getStatNumber(0);
        stats.mode = getStatNumber(node.mode);
        stats.nlink = getStatNumber(node.nlink);
        return stats;
      };
      Stats3.prototype._checkModeProperty = function(property) {
        return (Number(this.mode) & S_IFMT) === property;
      };
      Stats3.prototype.isDirectory = function() {
        return this._checkModeProperty(S_IFDIR);
      };
      Stats3.prototype.isFile = function() {
        return this._checkModeProperty(S_IFREG);
      };
      Stats3.prototype.isBlockDevice = function() {
        return this._checkModeProperty(S_IFBLK);
      };
      Stats3.prototype.isCharacterDevice = function() {
        return this._checkModeProperty(S_IFCHR);
      };
      Stats3.prototype.isSymbolicLink = function() {
        return this._checkModeProperty(S_IFLNK);
      };
      Stats3.prototype.isFIFO = function() {
        return this._checkModeProperty(S_IFIFO);
      };
      Stats3.prototype.isSocket = function() {
        return this._checkModeProperty(S_IFSOCK);
      };
      return Stats3;
    })()
  );
  exports$f3.Stats = Stats2;
  exports$f3.default = Stats2;
  return exports$f3;
}
function dew$c3() {
  if (_dewExec$c3) return exports$e3;
  _dewExec$c3 = true;
  var __spreadArray = exports$e3 && exports$e3.__spreadArray || function(to, from, pack) {
    if (pack || arguments.length === 2) for (var i6 = 0, l6 = from.length, ar; i6 < l6; i6++) {
      if (ar || !(i6 in from)) {
        if (!ar) ar = Array.prototype.slice.call(from, 0, i6);
        ar[i6] = from[i6];
      }
    }
    return to.concat(ar || Array.prototype.slice.call(from));
  };
  Object.defineProperty(exports$e3, "__esModule", {
    value: true
  });
  exports$e3.bufferFrom = exports$e3.bufferAllocUnsafe = exports$e3.Buffer = void 0;
  var buffer_1 = dew();
  Object.defineProperty(exports$e3, "Buffer", {
    enumerable: true,
    get: function() {
      return buffer_1.Buffer;
    }
  });
  function bufferV0P12Ponyfill(arg0) {
    var args = [];
    for (var _i = 1; _i < arguments.length; _i++) {
      args[_i - 1] = arguments[_i];
    }
    return new (buffer_1.Buffer.bind.apply(buffer_1.Buffer, __spreadArray([void 0, arg0], args, false)))();
  }
  var bufferAllocUnsafe = buffer_1.Buffer.allocUnsafe || bufferV0P12Ponyfill;
  exports$e3.bufferAllocUnsafe = bufferAllocUnsafe;
  var bufferFrom = buffer_1.Buffer.from || bufferV0P12Ponyfill;
  exports$e3.bufferFrom = bufferFrom;
  return exports$e3;
}
function dew$b3() {
  if (_dewExec$b3) return exports$d3;
  _dewExec$b3 = true;
  var __extends = exports$d3 && exports$d3.__extends || /* @__PURE__ */ (function() {
    var extendStatics = function(d5, b5) {
      extendStatics = Object.setPrototypeOf || {
        __proto__: []
      } instanceof Array && function(d6, b6) {
        d6.__proto__ = b6;
      } || function(d6, b6) {
        for (var p6 in b6) if (Object.prototype.hasOwnProperty.call(b6, p6)) d6[p6] = b6[p6];
      };
      return extendStatics(d5, b5);
    };
    return function(d5, b5) {
      if (typeof b5 !== "function" && b5 !== null) throw new TypeError("Class extends value " + String(b5) + " is not a constructor or null");
      extendStatics(d5, b5);
      function __() {
        this.constructor = d5;
      }
      d5.prototype = b5 === null ? Object.create(b5) : (__.prototype = b5.prototype, new __());
    };
  })();
  Object.defineProperty(exports$d3, "__esModule", {
    value: true
  });
  exports$d3.E = exports$d3.AssertionError = exports$d3.message = exports$d3.RangeError = exports$d3.TypeError = exports$d3.Error = void 0;
  var assert3 = et;
  var util = X;
  var kCode = typeof Symbol === "undefined" ? "_kCode" : /* @__PURE__ */ Symbol("code");
  var messages = {};
  function makeNodeError(Base) {
    return (
      /** @class */
      (function(_super) {
        __extends(NodeError, _super);
        function NodeError(key) {
          var args = [];
          for (var _i = 1; _i < arguments.length; _i++) {
            args[_i - 1] = arguments[_i];
          }
          var _this = _super.call(this, message(key, args)) || this;
          _this.code = key;
          _this[kCode] = key;
          _this.name = "".concat(_super.prototype.name, " [").concat(_this[kCode], "]");
          return _this;
        }
        return NodeError;
      })(Base)
    );
  }
  var g5 = typeof globalThis !== "undefined" ? globalThis : _global$3;
  var AssertionError = (
    /** @class */
    (function(_super) {
      __extends(AssertionError2, _super);
      function AssertionError2(options) {
        var _this = this;
        if (typeof options !== "object" || options === null) {
          throw new exports$d3.TypeError("ERR_INVALID_ARG_TYPE", "options", "object");
        }
        if (options.message) {
          _this = _super.call(this, options.message) || this;
        } else {
          _this = _super.call(this, "".concat(util.inspect(options.actual).slice(0, 128), " ") + "".concat(options.operator, " ").concat(util.inspect(options.expected).slice(0, 128))) || this;
        }
        _this.generatedMessage = !options.message;
        _this.name = "AssertionError [ERR_ASSERTION]";
        _this.code = "ERR_ASSERTION";
        _this.actual = options.actual;
        _this.expected = options.expected;
        _this.operator = options.operator;
        exports$d3.Error.captureStackTrace(_this, options.stackStartFunction);
        return _this;
      }
      return AssertionError2;
    })(g5.Error)
  );
  exports$d3.AssertionError = AssertionError;
  function message(key, args) {
    assert3.strictEqual(typeof key, "string");
    var msg = messages[key];
    assert3(msg, "An invalid error message key was used: ".concat(key, "."));
    var fmt;
    if (typeof msg === "function") {
      fmt = msg;
    } else {
      fmt = util.format;
      if (args === void 0 || args.length === 0) return msg;
      args.unshift(msg);
    }
    return String(fmt.apply(null, args));
  }
  exports$d3.message = message;
  function E4(sym, val) {
    messages[sym] = typeof val === "function" ? val : String(val);
  }
  exports$d3.E = E4;
  exports$d3.Error = makeNodeError(g5.Error);
  exports$d3.TypeError = makeNodeError(g5.TypeError);
  exports$d3.RangeError = makeNodeError(g5.RangeError);
  E4("ERR_ARG_NOT_ITERABLE", "%s must be iterable");
  E4("ERR_ASSERTION", "%s");
  E4("ERR_BUFFER_OUT_OF_BOUNDS", bufferOutOfBounds);
  E4("ERR_CHILD_CLOSED_BEFORE_REPLY", "Child closed before reply received");
  E4("ERR_CONSOLE_WRITABLE_STREAM", "Console expects a writable stream instance for %s");
  E4("ERR_CPU_USAGE", "Unable to obtain cpu usage %s");
  E4("ERR_DNS_SET_SERVERS_FAILED", function(err, servers) {
    return 'c-ares failed to set servers: "'.concat(err, '" [').concat(servers, "]");
  });
  E4("ERR_FALSY_VALUE_REJECTION", "Promise was rejected with falsy value");
  E4("ERR_ENCODING_NOT_SUPPORTED", function(enc) {
    return 'The "'.concat(enc, '" encoding is not supported');
  });
  E4("ERR_ENCODING_INVALID_ENCODED_DATA", function(enc) {
    return "The encoded data was not valid for encoding ".concat(enc);
  });
  E4("ERR_HTTP_HEADERS_SENT", "Cannot render headers after they are sent to the client");
  E4("ERR_HTTP_INVALID_STATUS_CODE", "Invalid status code: %s");
  E4("ERR_HTTP_TRAILER_INVALID", "Trailers are invalid with this transfer encoding");
  E4("ERR_INDEX_OUT_OF_RANGE", "Index out of range");
  E4("ERR_INVALID_ARG_TYPE", invalidArgType);
  E4("ERR_INVALID_ARRAY_LENGTH", function(name2, len, actual) {
    assert3.strictEqual(typeof actual, "number");
    return 'The array "'.concat(name2, '" (length ').concat(actual, ") must be of length ").concat(len, ".");
  });
  E4("ERR_INVALID_BUFFER_SIZE", "Buffer size must be a multiple of %s");
  E4("ERR_INVALID_CALLBACK", "Callback must be a function");
  E4("ERR_INVALID_CHAR", "Invalid character in %s");
  E4("ERR_INVALID_CURSOR_POS", "Cannot set cursor row without setting its column");
  E4("ERR_INVALID_FD", '"fd" must be a positive integer: %s');
  E4("ERR_INVALID_FILE_URL_HOST", 'File URL host must be "localhost" or empty on %s');
  E4("ERR_INVALID_FILE_URL_PATH", "File URL path %s");
  E4("ERR_INVALID_HANDLE_TYPE", "This handle type cannot be sent");
  E4("ERR_INVALID_IP_ADDRESS", "Invalid IP address: %s");
  E4("ERR_INVALID_OPT_VALUE", function(name2, value) {
    return 'The value "'.concat(String(value), '" is invalid for option "').concat(name2, '"');
  });
  E4("ERR_INVALID_OPT_VALUE_ENCODING", function(value) {
    return 'The value "'.concat(String(value), '" is invalid for option "encoding"');
  });
  E4("ERR_INVALID_REPL_EVAL_CONFIG", 'Cannot specify both "breakEvalOnSigint" and "eval" for REPL');
  E4("ERR_INVALID_SYNC_FORK_INPUT", "Asynchronous forks do not support Buffer, Uint8Array or string input: %s");
  E4("ERR_INVALID_THIS", 'Value of "this" must be of type %s');
  E4("ERR_INVALID_TUPLE", "%s must be an iterable %s tuple");
  E4("ERR_INVALID_URL", "Invalid URL: %s");
  E4("ERR_INVALID_URL_SCHEME", function(expected) {
    return "The URL must be ".concat(oneOf(expected, "scheme"));
  });
  E4("ERR_IPC_CHANNEL_CLOSED", "Channel closed");
  E4("ERR_IPC_DISCONNECTED", "IPC channel is already disconnected");
  E4("ERR_IPC_ONE_PIPE", "Child process can have only one IPC pipe");
  E4("ERR_IPC_SYNC_FORK", "IPC cannot be used with synchronous forks");
  E4("ERR_MISSING_ARGS", missingArgs);
  E4("ERR_MULTIPLE_CALLBACK", "Callback called multiple times");
  E4("ERR_NAPI_CONS_FUNCTION", "Constructor must be a function");
  E4("ERR_NAPI_CONS_PROTOTYPE_OBJECT", "Constructor.prototype must be an object");
  E4("ERR_NO_CRYPTO", "Node.js is not compiled with OpenSSL crypto support");
  E4("ERR_NO_LONGER_SUPPORTED", "%s is no longer supported");
  E4("ERR_PARSE_HISTORY_DATA", "Could not parse history data in %s");
  E4("ERR_SOCKET_ALREADY_BOUND", "Socket is already bound");
  E4("ERR_SOCKET_BAD_PORT", "Port should be > 0 and < 65536");
  E4("ERR_SOCKET_BAD_TYPE", "Bad socket type specified. Valid types are: udp4, udp6");
  E4("ERR_SOCKET_CANNOT_SEND", "Unable to send data");
  E4("ERR_SOCKET_CLOSED", "Socket is closed");
  E4("ERR_SOCKET_DGRAM_NOT_RUNNING", "Not running");
  E4("ERR_STDERR_CLOSE", "process.stderr cannot be closed");
  E4("ERR_STDOUT_CLOSE", "process.stdout cannot be closed");
  E4("ERR_STREAM_WRAP", "Stream has StringDecoder set or is in objectMode");
  E4("ERR_TLS_CERT_ALTNAME_INVALID", "Hostname/IP does not match certificate's altnames: %s");
  E4("ERR_TLS_DH_PARAM_SIZE", function(size) {
    return "DH parameter size ".concat(size, " is less than 2048");
  });
  E4("ERR_TLS_HANDSHAKE_TIMEOUT", "TLS handshake timeout");
  E4("ERR_TLS_RENEGOTIATION_FAILED", "Failed to renegotiate");
  E4("ERR_TLS_REQUIRED_SERVER_NAME", '"servername" is required parameter for Server.addContext');
  E4("ERR_TLS_SESSION_ATTACK", "TSL session renegotiation attack detected");
  E4("ERR_TRANSFORM_ALREADY_TRANSFORMING", "Calling transform done when still transforming");
  E4("ERR_TRANSFORM_WITH_LENGTH_0", "Calling transform done when writableState.length != 0");
  E4("ERR_UNKNOWN_ENCODING", "Unknown encoding: %s");
  E4("ERR_UNKNOWN_SIGNAL", "Unknown signal: %s");
  E4("ERR_UNKNOWN_STDIN_TYPE", "Unknown stdin file type");
  E4("ERR_UNKNOWN_STREAM_TYPE", "Unknown stream file type");
  E4("ERR_V8BREAKITERATOR", "Full ICU data not installed. See https://github.com/nodejs/node/wiki/Intl");
  function invalidArgType(name2, expected, actual) {
    assert3(name2, "name is required");
    var determiner;
    if (expected.includes("not ")) {
      determiner = "must not be";
      expected = expected.split("not ")[1];
    } else {
      determiner = "must be";
    }
    var msg;
    if (Array.isArray(name2)) {
      var names = name2.map(function(val) {
        return '"'.concat(val, '"');
      }).join(", ");
      msg = "The ".concat(names, " arguments ").concat(determiner, " ").concat(oneOf(expected, "type"));
    } else if (name2.includes(" argument")) {
      msg = "The ".concat(name2, " ").concat(determiner, " ").concat(oneOf(expected, "type"));
    } else {
      var type = name2.includes(".") ? "property" : "argument";
      msg = 'The "'.concat(name2, '" ').concat(type, " ").concat(determiner, " ").concat(oneOf(expected, "type"));
    }
    if (arguments.length >= 3) {
      msg += ". Received type ".concat(actual !== null ? typeof actual : "null");
    }
    return msg;
  }
  function missingArgs() {
    var args = [];
    for (var _i = 0; _i < arguments.length; _i++) {
      args[_i] = arguments[_i];
    }
    assert3(args.length > 0, "At least one arg needs to be specified");
    var msg = "The ";
    var len = args.length;
    args = args.map(function(a6) {
      return '"'.concat(a6, '"');
    });
    switch (len) {
      case 1:
        msg += "".concat(args[0], " argument");
        break;
      case 2:
        msg += "".concat(args[0], " and ").concat(args[1], " arguments");
        break;
      default:
        msg += args.slice(0, len - 1).join(", ");
        msg += ", and ".concat(args[len - 1], " arguments");
        break;
    }
    return "".concat(msg, " must be specified");
  }
  function oneOf(expected, thing) {
    assert3(expected, "expected is required");
    assert3(typeof thing === "string", "thing is required");
    if (Array.isArray(expected)) {
      var len = expected.length;
      assert3(len > 0, "At least one expected value needs to be specified");
      expected = expected.map(function(i6) {
        return String(i6);
      });
      if (len > 2) {
        return "one of ".concat(thing, " ").concat(expected.slice(0, len - 1).join(", "), ", or ") + expected[len - 1];
      } else if (len === 2) {
        return "one of ".concat(thing, " ").concat(expected[0], " or ").concat(expected[1]);
      } else {
        return "of ".concat(thing, " ").concat(expected[0]);
      }
    } else {
      return "of ".concat(thing, " ").concat(String(expected));
    }
  }
  function bufferOutOfBounds(name2, isWriting) {
    if (isWriting) {
      return "Attempt to write outside buffer bounds";
    } else {
      return '"'.concat(name2, '" is outside of buffer bounds');
    }
  }
  return exports$d3;
}
function dew$a3() {
  if (_dewExec$a3) return exports$c3;
  _dewExec$a3 = true;
  Object.defineProperty(exports$c3, "__esModule", {
    value: true
  });
  exports$c3.strToEncoding = exports$c3.assertEncoding = exports$c3.ENCODING_UTF8 = void 0;
  var buffer_1 = dew$c3();
  var errors = dew$b3();
  exports$c3.ENCODING_UTF8 = "utf8";
  function assertEncoding(encoding) {
    if (encoding && !buffer_1.Buffer.isEncoding(encoding)) throw new errors.TypeError("ERR_INVALID_OPT_VALUE_ENCODING", encoding);
  }
  exports$c3.assertEncoding = assertEncoding;
  function strToEncoding(str, encoding) {
    if (!encoding || encoding === exports$c3.ENCODING_UTF8) return str;
    if (encoding === "buffer") return new buffer_1.Buffer(str);
    return new buffer_1.Buffer(str).toString(encoding);
  }
  exports$c3.strToEncoding = strToEncoding;
  return exports$c3;
}
function dew$93() {
  if (_dewExec$93) return exports$b3;
  _dewExec$93 = true;
  Object.defineProperty(exports$b3, "__esModule", {
    value: true
  });
  exports$b3.Dirent = void 0;
  var constants_1 = dew$f3();
  var encoding_1 = dew$a3();
  var S_IFMT = constants_1.constants.S_IFMT, S_IFDIR = constants_1.constants.S_IFDIR, S_IFREG = constants_1.constants.S_IFREG, S_IFBLK = constants_1.constants.S_IFBLK, S_IFCHR = constants_1.constants.S_IFCHR, S_IFLNK = constants_1.constants.S_IFLNK, S_IFIFO = constants_1.constants.S_IFIFO, S_IFSOCK = constants_1.constants.S_IFSOCK;
  var Dirent2 = (
    /** @class */
    (function() {
      function Dirent3() {
        this.name = "";
        this.mode = 0;
      }
      Dirent3.build = function(link3, encoding) {
        var dirent = new Dirent3();
        var mode = link3.getNode().mode;
        dirent.name = (0, encoding_1.strToEncoding)(link3.getName(), encoding);
        dirent.mode = mode;
        return dirent;
      };
      Dirent3.prototype._checkModeProperty = function(property) {
        return (this.mode & S_IFMT) === property;
      };
      Dirent3.prototype.isDirectory = function() {
        return this._checkModeProperty(S_IFDIR);
      };
      Dirent3.prototype.isFile = function() {
        return this._checkModeProperty(S_IFREG);
      };
      Dirent3.prototype.isBlockDevice = function() {
        return this._checkModeProperty(S_IFBLK);
      };
      Dirent3.prototype.isCharacterDevice = function() {
        return this._checkModeProperty(S_IFCHR);
      };
      Dirent3.prototype.isSymbolicLink = function() {
        return this._checkModeProperty(S_IFLNK);
      };
      Dirent3.prototype.isFIFO = function() {
        return this._checkModeProperty(S_IFIFO);
      };
      Dirent3.prototype.isSocket = function() {
        return this._checkModeProperty(S_IFSOCK);
      };
      return Dirent3;
    })()
  );
  exports$b3.Dirent = Dirent2;
  exports$b3.default = Dirent2;
  return exports$b3;
}
function dew$83() {
  if (_dewExec$83) return exports$a3;
  _dewExec$83 = true;
  var process$1 = process3;
  Object.defineProperty(exports$a3, "__esModule", {
    value: true
  });
  var _setImmediate;
  if (typeof process$1.nextTick === "function") _setImmediate = process$1.nextTick.bind(typeof globalThis !== "undefined" ? globalThis : _global$22);
  else _setImmediate = setTimeout.bind(typeof globalThis !== "undefined" ? globalThis : _global$22);
  exports$a3.default = _setImmediate;
  return exports$a3;
}
function dew$74() {
  if (_dewExec$74) return exports$93;
  _dewExec$74 = true;
  var process$1 = process3;
  Object.defineProperty(exports$93, "__esModule", {
    value: true
  });
  exports$93.createProcess = void 0;
  var maybeReturnProcess = function() {
    if (typeof process$1 !== "undefined") {
      return process$1;
    }
    try {
      return process3;
    } catch (_a) {
      return void 0;
    }
  };
  function createProcess() {
    var p6 = maybeReturnProcess() || {};
    if (!p6.cwd) p6.cwd = function() {
      return "/";
    };
    if (!p6.nextTick) p6.nextTick = dew$83().default;
    if (!p6.emitWarning) p6.emitWarning = function(message, type) {
      console.warn("".concat(type).concat(type ? ": " : "").concat(message));
    };
    if (!p6.env) p6.env = {};
    return p6;
  }
  exports$93.createProcess = createProcess;
  exports$93.default = createProcess();
  return exports$93;
}
function dew$64() {
  if (_dewExec$64) return exports$84;
  _dewExec$64 = true;
  var __extends = exports$84 && exports$84.__extends || /* @__PURE__ */ (function() {
    var extendStatics = function(d5, b5) {
      extendStatics = Object.setPrototypeOf || {
        __proto__: []
      } instanceof Array && function(d6, b6) {
        d6.__proto__ = b6;
      } || function(d6, b6) {
        for (var p6 in b6) if (Object.prototype.hasOwnProperty.call(b6, p6)) d6[p6] = b6[p6];
      };
      return extendStatics(d5, b5);
    };
    return function(d5, b5) {
      if (typeof b5 !== "function" && b5 !== null) throw new TypeError("Class extends value " + String(b5) + " is not a constructor or null");
      extendStatics(d5, b5);
      function __() {
        this.constructor = d5;
      }
      d5.prototype = b5 === null ? Object.create(b5) : (__.prototype = b5.prototype, new __());
    };
  })();
  Object.defineProperty(exports$84, "__esModule", {
    value: true
  });
  exports$84.File = exports$84.Link = exports$84.Node = exports$84.SEP = void 0;
  var process_1 = dew$74();
  var buffer_1 = dew$c3();
  var constants_1 = dew$f3();
  var events_1 = y4;
  var Stats_1 = dew$d3();
  var S_IFMT = constants_1.constants.S_IFMT, S_IFDIR = constants_1.constants.S_IFDIR, S_IFREG = constants_1.constants.S_IFREG, S_IFLNK = constants_1.constants.S_IFLNK, O_APPEND = constants_1.constants.O_APPEND;
  var getuid = function() {
    var _a, _b;
    return (_b = (_a = process_1.default.getuid) === null || _a === void 0 ? void 0 : _a.call(process_1.default)) !== null && _b !== void 0 ? _b : 0;
  };
  var getgid = function() {
    var _a, _b;
    return (_b = (_a = process_1.default.getgid) === null || _a === void 0 ? void 0 : _a.call(process_1.default)) !== null && _b !== void 0 ? _b : 0;
  };
  exports$84.SEP = "/";
  var Node = (
    /** @class */
    (function(_super) {
      __extends(Node2, _super);
      function Node2(ino, perm) {
        if (perm === void 0) {
          perm = 438;
        }
        var _this = _super.call(this) || this;
        _this._uid = getuid();
        _this._gid = getgid();
        _this._atime = /* @__PURE__ */ new Date();
        _this._mtime = /* @__PURE__ */ new Date();
        _this._ctime = /* @__PURE__ */ new Date();
        _this._perm = 438;
        _this.mode = S_IFREG;
        _this._nlink = 1;
        _this._perm = perm;
        _this.mode |= perm;
        _this.ino = ino;
        return _this;
      }
      Object.defineProperty(Node2.prototype, "ctime", {
        get: function() {
          return this._ctime;
        },
        set: function(ctime) {
          this._ctime = ctime;
        },
        enumerable: false,
        configurable: true
      });
      Object.defineProperty(Node2.prototype, "uid", {
        get: function() {
          return this._uid;
        },
        set: function(uid) {
          this._uid = uid;
          this.ctime = /* @__PURE__ */ new Date();
        },
        enumerable: false,
        configurable: true
      });
      Object.defineProperty(Node2.prototype, "gid", {
        get: function() {
          return this._gid;
        },
        set: function(gid) {
          this._gid = gid;
          this.ctime = /* @__PURE__ */ new Date();
        },
        enumerable: false,
        configurable: true
      });
      Object.defineProperty(Node2.prototype, "atime", {
        get: function() {
          return this._atime;
        },
        set: function(atime) {
          this._atime = atime;
          this.ctime = /* @__PURE__ */ new Date();
        },
        enumerable: false,
        configurable: true
      });
      Object.defineProperty(Node2.prototype, "mtime", {
        get: function() {
          return this._mtime;
        },
        set: function(mtime) {
          this._mtime = mtime;
          this.ctime = /* @__PURE__ */ new Date();
        },
        enumerable: false,
        configurable: true
      });
      Object.defineProperty(Node2.prototype, "perm", {
        get: function() {
          return this._perm;
        },
        set: function(perm) {
          this._perm = perm;
          this.ctime = /* @__PURE__ */ new Date();
        },
        enumerable: false,
        configurable: true
      });
      Object.defineProperty(Node2.prototype, "nlink", {
        get: function() {
          return this._nlink;
        },
        set: function(nlink) {
          this._nlink = nlink;
          this.ctime = /* @__PURE__ */ new Date();
        },
        enumerable: false,
        configurable: true
      });
      Node2.prototype.getString = function(encoding) {
        if (encoding === void 0) {
          encoding = "utf8";
        }
        this.atime = /* @__PURE__ */ new Date();
        return this.getBuffer().toString(encoding);
      };
      Node2.prototype.setString = function(str) {
        this.buf = (0, buffer_1.bufferFrom)(str, "utf8");
        this.touch();
      };
      Node2.prototype.getBuffer = function() {
        this.atime = /* @__PURE__ */ new Date();
        if (!this.buf) this.setBuffer((0, buffer_1.bufferAllocUnsafe)(0));
        return (0, buffer_1.bufferFrom)(this.buf);
      };
      Node2.prototype.setBuffer = function(buf) {
        this.buf = (0, buffer_1.bufferFrom)(buf);
        this.touch();
      };
      Node2.prototype.getSize = function() {
        return this.buf ? this.buf.length : 0;
      };
      Node2.prototype.setModeProperty = function(property) {
        this.mode = this.mode & ~S_IFMT | property;
      };
      Node2.prototype.setIsFile = function() {
        this.setModeProperty(S_IFREG);
      };
      Node2.prototype.setIsDirectory = function() {
        this.setModeProperty(S_IFDIR);
      };
      Node2.prototype.setIsSymlink = function() {
        this.setModeProperty(S_IFLNK);
      };
      Node2.prototype.isFile = function() {
        return (this.mode & S_IFMT) === S_IFREG;
      };
      Node2.prototype.isDirectory = function() {
        return (this.mode & S_IFMT) === S_IFDIR;
      };
      Node2.prototype.isSymlink = function() {
        return (this.mode & S_IFMT) === S_IFLNK;
      };
      Node2.prototype.makeSymlink = function(steps) {
        this.symlink = steps;
        this.setIsSymlink();
      };
      Node2.prototype.write = function(buf, off3, len, pos) {
        if (off3 === void 0) {
          off3 = 0;
        }
        if (len === void 0) {
          len = buf.length;
        }
        if (pos === void 0) {
          pos = 0;
        }
        if (!this.buf) this.buf = (0, buffer_1.bufferAllocUnsafe)(0);
        if (pos + len > this.buf.length) {
          var newBuf = (0, buffer_1.bufferAllocUnsafe)(pos + len);
          this.buf.copy(newBuf, 0, 0, this.buf.length);
          this.buf = newBuf;
        }
        buf.copy(this.buf, pos, off3, off3 + len);
        this.touch();
        return len;
      };
      Node2.prototype.read = function(buf, off3, len, pos) {
        if (off3 === void 0) {
          off3 = 0;
        }
        if (len === void 0) {
          len = buf.byteLength;
        }
        if (pos === void 0) {
          pos = 0;
        }
        this.atime = /* @__PURE__ */ new Date();
        if (!this.buf) this.buf = (0, buffer_1.bufferAllocUnsafe)(0);
        var actualLen = len;
        if (actualLen > buf.byteLength) {
          actualLen = buf.byteLength;
        }
        if (actualLen + pos > this.buf.length) {
          actualLen = this.buf.length - pos;
        }
        this.buf.copy(buf, off3, pos, pos + actualLen);
        return actualLen;
      };
      Node2.prototype.truncate = function(len) {
        if (len === void 0) {
          len = 0;
        }
        if (!len) this.buf = (0, buffer_1.bufferAllocUnsafe)(0);
        else {
          if (!this.buf) this.buf = (0, buffer_1.bufferAllocUnsafe)(0);
          if (len <= this.buf.length) {
            this.buf = this.buf.slice(0, len);
          } else {
            var buf = (0, buffer_1.bufferAllocUnsafe)(len);
            this.buf.copy(buf);
            buf.fill(0, this.buf.length);
            this.buf = buf;
          }
        }
        this.touch();
      };
      Node2.prototype.chmod = function(perm) {
        this.perm = perm;
        this.mode = this.mode & ~511 | perm;
        this.touch();
      };
      Node2.prototype.chown = function(uid, gid) {
        this.uid = uid;
        this.gid = gid;
        this.touch();
      };
      Node2.prototype.touch = function() {
        this.mtime = /* @__PURE__ */ new Date();
        this.emit("change", this);
      };
      Node2.prototype.canRead = function(uid, gid) {
        if (uid === void 0) {
          uid = getuid();
        }
        if (gid === void 0) {
          gid = getgid();
        }
        if (this.perm & 4) {
          return true;
        }
        if (gid === this.gid) {
          if (this.perm & 32) {
            return true;
          }
        }
        if (uid === this.uid) {
          if (this.perm & 256) {
            return true;
          }
        }
        return false;
      };
      Node2.prototype.canWrite = function(uid, gid) {
        if (uid === void 0) {
          uid = getuid();
        }
        if (gid === void 0) {
          gid = getgid();
        }
        if (this.perm & 2) {
          return true;
        }
        if (gid === this.gid) {
          if (this.perm & 16) {
            return true;
          }
        }
        if (uid === this.uid) {
          if (this.perm & 128) {
            return true;
          }
        }
        return false;
      };
      Node2.prototype.del = function() {
        this.emit("delete", this);
      };
      Node2.prototype.toJSON = function() {
        return {
          ino: this.ino,
          uid: this.uid,
          gid: this.gid,
          atime: this.atime.getTime(),
          mtime: this.mtime.getTime(),
          ctime: this.ctime.getTime(),
          perm: this.perm,
          mode: this.mode,
          nlink: this.nlink,
          symlink: this.symlink,
          data: this.getString()
        };
      };
      return Node2;
    })(events_1.EventEmitter)
  );
  exports$84.Node = Node;
  var Link = (
    /** @class */
    (function(_super) {
      __extends(Link2, _super);
      function Link2(vol2, parent, name2) {
        var _this = _super.call(this) || this;
        _this.children = {};
        _this._steps = [];
        _this.ino = 0;
        _this.length = 0;
        _this.vol = vol2;
        _this.parent = parent;
        _this.name = name2;
        _this.syncSteps();
        return _this;
      }
      Object.defineProperty(Link2.prototype, "steps", {
        get: function() {
          return this._steps;
        },
        // Recursively sync children steps, e.g. in case of dir rename
        set: function(val) {
          this._steps = val;
          for (var _i = 0, _a = Object.entries(this.children); _i < _a.length; _i++) {
            var _b = _a[_i], child = _b[0], link3 = _b[1];
            if (child === "." || child === "..") {
              continue;
            }
            link3 === null || link3 === void 0 ? void 0 : link3.syncSteps();
          }
        },
        enumerable: false,
        configurable: true
      });
      Link2.prototype.setNode = function(node) {
        this.node = node;
        this.ino = node.ino;
      };
      Link2.prototype.getNode = function() {
        return this.node;
      };
      Link2.prototype.createChild = function(name2, node) {
        if (node === void 0) {
          node = this.vol.createNode();
        }
        var link3 = new Link2(this.vol, this, name2);
        link3.setNode(node);
        if (node.isDirectory()) {
          link3.children["."] = link3;
          link3.getNode().nlink++;
        }
        this.setChild(name2, link3);
        return link3;
      };
      Link2.prototype.setChild = function(name2, link3) {
        if (link3 === void 0) {
          link3 = new Link2(this.vol, this, name2);
        }
        this.children[name2] = link3;
        link3.parent = this;
        this.length++;
        var node = link3.getNode();
        if (node.isDirectory()) {
          link3.children[".."] = this;
          this.getNode().nlink++;
        }
        this.getNode().mtime = /* @__PURE__ */ new Date();
        this.emit("child:add", link3, this);
        return link3;
      };
      Link2.prototype.deleteChild = function(link3) {
        var node = link3.getNode();
        if (node.isDirectory()) {
          delete link3.children[".."];
          this.getNode().nlink--;
        }
        delete this.children[link3.getName()];
        this.length--;
        this.getNode().mtime = /* @__PURE__ */ new Date();
        this.emit("child:delete", link3, this);
      };
      Link2.prototype.getChild = function(name2) {
        this.getNode().mtime = /* @__PURE__ */ new Date();
        if (Object.hasOwnProperty.call(this.children, name2)) {
          return this.children[name2];
        }
      };
      Link2.prototype.getPath = function() {
        return this.steps.join(exports$84.SEP);
      };
      Link2.prototype.getName = function() {
        return this.steps[this.steps.length - 1];
      };
      Link2.prototype.walk = function(steps, stop, i6) {
        if (stop === void 0) {
          stop = steps.length;
        }
        if (i6 === void 0) {
          i6 = 0;
        }
        if (i6 >= steps.length) return this;
        if (i6 >= stop) return this;
        var step = steps[i6];
        var link3 = this.getChild(step);
        if (!link3) return null;
        return link3.walk(steps, stop, i6 + 1);
      };
      Link2.prototype.toJSON = function() {
        return {
          steps: this.steps,
          ino: this.ino,
          children: Object.keys(this.children)
        };
      };
      Link2.prototype.syncSteps = function() {
        this.steps = this.parent ? this.parent.steps.concat([this.name]) : [this.name];
      };
      return Link2;
    })(events_1.EventEmitter)
  );
  exports$84.Link = Link;
  var File = (
    /** @class */
    (function() {
      function File2(link3, node, flags, fd) {
        this.position = 0;
        this.link = link3;
        this.node = node;
        this.flags = flags;
        this.fd = fd;
      }
      File2.prototype.getString = function(encoding) {
        return this.node.getString();
      };
      File2.prototype.setString = function(str) {
        this.node.setString(str);
      };
      File2.prototype.getBuffer = function() {
        return this.node.getBuffer();
      };
      File2.prototype.setBuffer = function(buf) {
        this.node.setBuffer(buf);
      };
      File2.prototype.getSize = function() {
        return this.node.getSize();
      };
      File2.prototype.truncate = function(len) {
        this.node.truncate(len);
      };
      File2.prototype.seekTo = function(position) {
        this.position = position;
      };
      File2.prototype.stats = function() {
        return Stats_1.default.build(this.node);
      };
      File2.prototype.write = function(buf, offset, length, position) {
        if (offset === void 0) {
          offset = 0;
        }
        if (length === void 0) {
          length = buf.length;
        }
        if (typeof position !== "number") position = this.position;
        if (this.flags & O_APPEND) position = this.getSize();
        var bytes = this.node.write(buf, offset, length, position);
        this.position = position + bytes;
        return bytes;
      };
      File2.prototype.read = function(buf, offset, length, position) {
        if (offset === void 0) {
          offset = 0;
        }
        if (length === void 0) {
          length = buf.byteLength;
        }
        if (typeof position !== "number") position = this.position;
        var bytes = this.node.read(buf, offset, length, position);
        this.position = position + bytes;
        return bytes;
      };
      File2.prototype.chmod = function(perm) {
        this.node.chmod(perm);
      };
      File2.prototype.chown = function(uid, gid) {
        this.node.chown(uid, gid);
      };
      return File2;
    })()
  );
  exports$84.File = File;
  return exports$84;
}
function dew$54() {
  if (_dewExec$54) return exports$74;
  _dewExec$54 = true;
  Object.defineProperty(exports$74, "__esModule", {
    value: true
  });
  function setTimeoutUnref(callback, time, args) {
    var ref = setTimeout.apply(typeof globalThis !== "undefined" ? globalThis : _global$12, arguments);
    if (ref && typeof ref === "object" && typeof ref.unref === "function") ref.unref();
    return ref;
  }
  exports$74.default = setTimeoutUnref;
  return exports$74;
}
function dew$44() {
  if (_dewExec$44) return exports$64;
  _dewExec$44 = true;
  var __spreadArray = exports$64 && exports$64.__spreadArray || function(to, from, pack) {
    if (pack || arguments.length === 2) for (var i6 = 0, l6 = from.length, ar; i6 < l6; i6++) {
      if (ar || !(i6 in from)) {
        if (!ar) ar = Array.prototype.slice.call(from, 0, i6);
        ar[i6] = from[i6];
      }
    }
    return to.concat(ar || Array.prototype.slice.call(from));
  };
  Object.defineProperty(exports$64, "__esModule", {
    value: true
  });
  exports$64.FileHandle = void 0;
  function promisify3(vol2, fn, getResult) {
    if (getResult === void 0) {
      getResult = function(input) {
        return input;
      };
    }
    return function() {
      var args = [];
      for (var _i = 0; _i < arguments.length; _i++) {
        args[_i] = arguments[_i];
      }
      return new Promise(function(resolve2, reject) {
        vol2[fn].bind(vol2).apply(void 0, __spreadArray(__spreadArray([], args, false), [function(error2, result) {
          if (error2) return reject(error2);
          return resolve2(getResult(result));
        }], false));
      });
    };
  }
  var FileHandle = (
    /** @class */
    (function() {
      function FileHandle2(vol2, fd) {
        this.vol = vol2;
        this.fd = fd;
      }
      FileHandle2.prototype.appendFile = function(data, options) {
        return promisify3(this.vol, "appendFile")(this.fd, data, options);
      };
      FileHandle2.prototype.chmod = function(mode) {
        return promisify3(this.vol, "fchmod")(this.fd, mode);
      };
      FileHandle2.prototype.chown = function(uid, gid) {
        return promisify3(this.vol, "fchown")(this.fd, uid, gid);
      };
      FileHandle2.prototype.close = function() {
        return promisify3(this.vol, "close")(this.fd);
      };
      FileHandle2.prototype.datasync = function() {
        return promisify3(this.vol, "fdatasync")(this.fd);
      };
      FileHandle2.prototype.read = function(buffer2, offset, length, position) {
        return promisify3(this.vol, "read", function(bytesRead) {
          return {
            bytesRead,
            buffer: buffer2
          };
        })(this.fd, buffer2, offset, length, position);
      };
      FileHandle2.prototype.readFile = function(options) {
        return promisify3(this.vol, "readFile")(this.fd, options);
      };
      FileHandle2.prototype.stat = function(options) {
        return promisify3(this.vol, "fstat")(this.fd, options);
      };
      FileHandle2.prototype.sync = function() {
        return promisify3(this.vol, "fsync")(this.fd);
      };
      FileHandle2.prototype.truncate = function(len) {
        return promisify3(this.vol, "ftruncate")(this.fd, len);
      };
      FileHandle2.prototype.utimes = function(atime, mtime) {
        return promisify3(this.vol, "futimes")(this.fd, atime, mtime);
      };
      FileHandle2.prototype.write = function(buffer2, offset, length, position) {
        return promisify3(this.vol, "write", function(bytesWritten) {
          return {
            bytesWritten,
            buffer: buffer2
          };
        })(this.fd, buffer2, offset, length, position);
      };
      FileHandle2.prototype.writeFile = function(data, options) {
        return promisify3(this.vol, "writeFile")(this.fd, data, options);
      };
      return FileHandle2;
    })()
  );
  exports$64.FileHandle = FileHandle;
  function createPromisesApi(vol2) {
    if (typeof Promise === "undefined") return null;
    return {
      FileHandle,
      access: function(path2, mode) {
        return promisify3(vol2, "access")(path2, mode);
      },
      appendFile: function(path2, data, options) {
        return promisify3(vol2, "appendFile")(path2 instanceof FileHandle ? path2.fd : path2, data, options);
      },
      chmod: function(path2, mode) {
        return promisify3(vol2, "chmod")(path2, mode);
      },
      chown: function(path2, uid, gid) {
        return promisify3(vol2, "chown")(path2, uid, gid);
      },
      copyFile: function(src, dest, flags) {
        return promisify3(vol2, "copyFile")(src, dest, flags);
      },
      lchmod: function(path2, mode) {
        return promisify3(vol2, "lchmod")(path2, mode);
      },
      lchown: function(path2, uid, gid) {
        return promisify3(vol2, "lchown")(path2, uid, gid);
      },
      link: function(existingPath, newPath) {
        return promisify3(vol2, "link")(existingPath, newPath);
      },
      lstat: function(path2, options) {
        return promisify3(vol2, "lstat")(path2, options);
      },
      mkdir: function(path2, options) {
        return promisify3(vol2, "mkdir")(path2, options);
      },
      mkdtemp: function(prefix, options) {
        return promisify3(vol2, "mkdtemp")(prefix, options);
      },
      open: function(path2, flags, mode) {
        return promisify3(vol2, "open", function(fd) {
          return new FileHandle(vol2, fd);
        })(path2, flags, mode);
      },
      readdir: function(path2, options) {
        return promisify3(vol2, "readdir")(path2, options);
      },
      readFile: function(id2, options) {
        return promisify3(vol2, "readFile")(id2 instanceof FileHandle ? id2.fd : id2, options);
      },
      readlink: function(path2, options) {
        return promisify3(vol2, "readlink")(path2, options);
      },
      realpath: function(path2, options) {
        return promisify3(vol2, "realpath")(path2, options);
      },
      rename: function(oldPath, newPath) {
        return promisify3(vol2, "rename")(oldPath, newPath);
      },
      rmdir: function(path2) {
        return promisify3(vol2, "rmdir")(path2);
      },
      rm: function(path2, options) {
        return promisify3(vol2, "rm")(path2, options);
      },
      stat: function(path2, options) {
        return promisify3(vol2, "stat")(path2, options);
      },
      symlink: function(target, path2, type) {
        return promisify3(vol2, "symlink")(target, path2, type);
      },
      truncate: function(path2, len) {
        return promisify3(vol2, "truncate")(path2, len);
      },
      unlink: function(path2) {
        return promisify3(vol2, "unlink")(path2);
      },
      utimes: function(path2, atime, mtime) {
        return promisify3(vol2, "utimes")(path2, atime, mtime);
      },
      writeFile: function(id2, data, options) {
        return promisify3(vol2, "writeFile")(id2 instanceof FileHandle ? id2.fd : id2, data, options);
      }
    };
  }
  exports$64.default = createPromisesApi;
  return exports$64;
}
function dew$34() {
  if (_dewExec$34) return exports$54;
  _dewExec$34 = true;
  var process$1 = process3;
  Object.defineProperty(exports$54, "__esModule", {
    value: true
  });
  exports$54.correctPath = correctPath;
  exports$54.unixify = unixify;
  var isWin = process$1.platform === "win32";
  function removeTrailingSeparator(str) {
    var i6 = str.length - 1;
    if (i6 < 2) {
      return str;
    }
    while (isSeparator(str, i6)) {
      i6--;
    }
    return str.substr(0, i6 + 1);
  }
  function isSeparator(str, i6) {
    var _char = str[i6];
    return i6 > 0 && (_char === "/" || isWin && _char === "\\");
  }
  function normalizePath(str, stripTrailing) {
    if (typeof str !== "string") {
      throw new TypeError("expected a string");
    }
    str = str.replace(/[\\\/]+/g, "/");
    if (stripTrailing !== false) {
      str = removeTrailingSeparator(str);
    }
    return str;
  }
  function unixify(filepath) {
    var stripTrailing = arguments.length > 1 && arguments[1] !== void 0 ? arguments[1] : true;
    if (isWin) {
      filepath = normalizePath(filepath, stripTrailing);
      return filepath.replace(/^([a-zA-Z]+:|\.\/)/, "");
    }
    return filepath;
  }
  function correctPath(filepath) {
    return unixify(filepath.replace(/^\\\\\?\\.:\\/, "\\"));
  }
  return exports$54;
}
function dew$25() {
  if (_dewExec$25) return exports$44;
  _dewExec$25 = true;
  var __extends = exports$44 && exports$44.__extends || /* @__PURE__ */ (function() {
    var extendStatics = function(d5, b5) {
      extendStatics = Object.setPrototypeOf || {
        __proto__: []
      } instanceof Array && function(d6, b6) {
        d6.__proto__ = b6;
      } || function(d6, b6) {
        for (var p6 in b6) if (Object.prototype.hasOwnProperty.call(b6, p6)) d6[p6] = b6[p6];
      };
      return extendStatics(d5, b5);
    };
    return function(d5, b5) {
      if (typeof b5 !== "function" && b5 !== null) throw new TypeError("Class extends value " + String(b5) + " is not a constructor or null");
      extendStatics(d5, b5);
      function __() {
        this.constructor = d5;
      }
      d5.prototype = b5 === null ? Object.create(b5) : (__.prototype = b5.prototype, new __());
    };
  })();
  var __spreadArray = exports$44 && exports$44.__spreadArray || function(to, from, pack) {
    if (pack || arguments.length === 2) for (var i6 = 0, l6 = from.length, ar; i6 < l6; i6++) {
      if (ar || !(i6 in from)) {
        if (!ar) ar = Array.prototype.slice.call(from, 0, i6);
        ar[i6] = from[i6];
      }
    }
    return to.concat(ar || Array.prototype.slice.call(from));
  };
  Object.defineProperty(exports$44, "__esModule", {
    value: true
  });
  exports$44.FSWatcher = exports$44.StatWatcher = exports$44.Volume = exports$44.toUnixTimestamp = exports$44.bufferToEncoding = exports$44.dataToBuffer = exports$44.dataToStr = exports$44.pathToSteps = exports$44.filenameToSteps = exports$44.pathToFilename = exports$44.flagsToNumber = exports$44.FLAGS = void 0;
  var pathModule = exports$22;
  var node_1 = dew$64();
  var Stats_1 = dew$d3();
  var Dirent_1 = dew$93();
  var buffer_1 = dew$c3();
  var setImmediate_1 = dew$83();
  var process_1 = dew$74();
  var setTimeoutUnref_1 = dew$54();
  var stream_1 = exports6;
  var constants_1 = dew$f3();
  var events_1 = y4;
  var encoding_1 = dew$a3();
  var errors = dew$b3();
  var util = X;
  var promises_1 = dew$44();
  var resolveCrossPlatform = pathModule.resolve;
  var O_RDONLY = constants_1.constants.O_RDONLY, O_WRONLY = constants_1.constants.O_WRONLY, O_RDWR = constants_1.constants.O_RDWR, O_CREAT = constants_1.constants.O_CREAT, O_EXCL = constants_1.constants.O_EXCL, O_TRUNC = constants_1.constants.O_TRUNC, O_APPEND = constants_1.constants.O_APPEND, O_SYNC = constants_1.constants.O_SYNC, O_DIRECTORY = constants_1.constants.O_DIRECTORY, F_OK2 = constants_1.constants.F_OK, COPYFILE_EXCL = constants_1.constants.COPYFILE_EXCL, COPYFILE_FICLONE_FORCE = constants_1.constants.COPYFILE_FICLONE_FORCE;
  var _a = pathModule.posix ? pathModule.posix : pathModule, sep = _a.sep, relative = _a.relative, join = _a.join, dirname = _a.dirname;
  var isWin = process_1.default.platform === "win32";
  var kMinPoolSpace = 128;
  var ERRSTR = {
    PATH_STR: "path must be a string or Buffer",
    // FD:             'file descriptor must be a unsigned 32-bit integer',
    FD: "fd must be a file descriptor",
    MODE_INT: "mode must be an int",
    CB: "callback must be a function",
    UID: "uid must be an unsigned int",
    GID: "gid must be an unsigned int",
    LEN: "len must be an integer",
    ATIME: "atime must be an integer",
    MTIME: "mtime must be an integer",
    PREFIX: "filename prefix is required",
    BUFFER: "buffer must be an instance of Buffer or StaticBuffer",
    OFFSET: "offset must be an integer",
    LENGTH: "length must be an integer",
    POSITION: "position must be an integer"
  };
  var ERRSTR_OPTS = function(tipeof) {
    return "Expected options to be either an object or a string, but got ".concat(tipeof, " instead");
  };
  var ENOENT = "ENOENT";
  var EBADF = "EBADF";
  var EINVAL = "EINVAL";
  var EPERM = "EPERM";
  var EPROTO = "EPROTO";
  var EEXIST = "EEXIST";
  var ENOTDIR = "ENOTDIR";
  var EMFILE = "EMFILE";
  var EACCES = "EACCES";
  var EISDIR = "EISDIR";
  var ENOTEMPTY = "ENOTEMPTY";
  var ENOSYS = "ENOSYS";
  var ERR_FS_EISDIR = "ERR_FS_EISDIR";
  function formatError(errorCode, func, path2, path22) {
    if (func === void 0) {
      func = "";
    }
    if (path2 === void 0) {
      path2 = "";
    }
    if (path22 === void 0) {
      path22 = "";
    }
    var pathFormatted = "";
    if (path2) pathFormatted = " '".concat(path2, "'");
    if (path22) pathFormatted += " -> '".concat(path22, "'");
    switch (errorCode) {
      case ENOENT:
        return "ENOENT: no such file or directory, ".concat(func).concat(pathFormatted);
      case EBADF:
        return "EBADF: bad file descriptor, ".concat(func).concat(pathFormatted);
      case EINVAL:
        return "EINVAL: invalid argument, ".concat(func).concat(pathFormatted);
      case EPERM:
        return "EPERM: operation not permitted, ".concat(func).concat(pathFormatted);
      case EPROTO:
        return "EPROTO: protocol error, ".concat(func).concat(pathFormatted);
      case EEXIST:
        return "EEXIST: file already exists, ".concat(func).concat(pathFormatted);
      case ENOTDIR:
        return "ENOTDIR: not a directory, ".concat(func).concat(pathFormatted);
      case EISDIR:
        return "EISDIR: illegal operation on a directory, ".concat(func).concat(pathFormatted);
      case EACCES:
        return "EACCES: permission denied, ".concat(func).concat(pathFormatted);
      case ENOTEMPTY:
        return "ENOTEMPTY: directory not empty, ".concat(func).concat(pathFormatted);
      case EMFILE:
        return "EMFILE: too many open files, ".concat(func).concat(pathFormatted);
      case ENOSYS:
        return "ENOSYS: function not implemented, ".concat(func).concat(pathFormatted);
      case ERR_FS_EISDIR:
        return "[ERR_FS_EISDIR]: Path is a directory: ".concat(func, " returned EISDIR (is a directory) ").concat(path2);
      default:
        return "".concat(errorCode, ": error occurred, ").concat(func).concat(pathFormatted);
    }
  }
  function createError(errorCode, func, path2, path22, Constructor) {
    if (func === void 0) {
      func = "";
    }
    if (path2 === void 0) {
      path2 = "";
    }
    if (path22 === void 0) {
      path22 = "";
    }
    if (Constructor === void 0) {
      Constructor = Error;
    }
    var error2 = new Constructor(formatError(errorCode, func, path2, path22));
    error2.code = errorCode;
    if (path2) {
      error2.path = path2;
    }
    return error2;
  }
  var FLAGS;
  (function(FLAGS2) {
    FLAGS2[FLAGS2["r"] = O_RDONLY] = "r";
    FLAGS2[FLAGS2["r+"] = O_RDWR] = "r+";
    FLAGS2[FLAGS2["rs"] = O_RDONLY | O_SYNC] = "rs";
    FLAGS2[FLAGS2["sr"] = FLAGS2.rs] = "sr";
    FLAGS2[FLAGS2["rs+"] = O_RDWR | O_SYNC] = "rs+";
    FLAGS2[FLAGS2["sr+"] = FLAGS2["rs+"]] = "sr+";
    FLAGS2[FLAGS2["w"] = O_WRONLY | O_CREAT | O_TRUNC] = "w";
    FLAGS2[FLAGS2["wx"] = O_WRONLY | O_CREAT | O_TRUNC | O_EXCL] = "wx";
    FLAGS2[FLAGS2["xw"] = FLAGS2.wx] = "xw";
    FLAGS2[FLAGS2["w+"] = O_RDWR | O_CREAT | O_TRUNC] = "w+";
    FLAGS2[FLAGS2["wx+"] = O_RDWR | O_CREAT | O_TRUNC | O_EXCL] = "wx+";
    FLAGS2[FLAGS2["xw+"] = FLAGS2["wx+"]] = "xw+";
    FLAGS2[FLAGS2["a"] = O_WRONLY | O_APPEND | O_CREAT] = "a";
    FLAGS2[FLAGS2["ax"] = O_WRONLY | O_APPEND | O_CREAT | O_EXCL] = "ax";
    FLAGS2[FLAGS2["xa"] = FLAGS2.ax] = "xa";
    FLAGS2[FLAGS2["a+"] = O_RDWR | O_APPEND | O_CREAT] = "a+";
    FLAGS2[FLAGS2["ax+"] = O_RDWR | O_APPEND | O_CREAT | O_EXCL] = "ax+";
    FLAGS2[FLAGS2["xa+"] = FLAGS2["ax+"]] = "xa+";
  })(FLAGS = exports$44.FLAGS || (exports$44.FLAGS = {}));
  function flagsToNumber(flags) {
    if (typeof flags === "number") return flags;
    if (typeof flags === "string") {
      var flagsNum = FLAGS[flags];
      if (typeof flagsNum !== "undefined") return flagsNum;
    }
    throw new errors.TypeError("ERR_INVALID_OPT_VALUE", "flags", flags);
  }
  exports$44.flagsToNumber = flagsToNumber;
  function getOptions(defaults, options) {
    var opts;
    if (!options) return defaults;
    else {
      var tipeof = typeof options;
      switch (tipeof) {
        case "string":
          opts = Object.assign({}, defaults, {
            encoding: options
          });
          break;
        case "object":
          opts = Object.assign({}, defaults, options);
          break;
        default:
          throw TypeError(ERRSTR_OPTS(tipeof));
      }
    }
    if (opts.encoding !== "buffer") (0, encoding_1.assertEncoding)(opts.encoding);
    return opts;
  }
  function optsGenerator(defaults) {
    return function(options) {
      return getOptions(defaults, options);
    };
  }
  function validateCallback(callback) {
    if (typeof callback !== "function") throw TypeError(ERRSTR.CB);
    return callback;
  }
  function optsAndCbGenerator(getOpts) {
    return function(options, callback) {
      return typeof options === "function" ? [getOpts(), options] : [getOpts(options), validateCallback(callback)];
    };
  }
  var optsDefaults = {
    encoding: "utf8"
  };
  var getDefaultOpts = optsGenerator(optsDefaults);
  var getDefaultOptsAndCb = optsAndCbGenerator(getDefaultOpts);
  var readFileOptsDefaults = {
    flag: "r"
  };
  var getReadFileOptions = optsGenerator(readFileOptsDefaults);
  var writeFileDefaults = {
    encoding: "utf8",
    mode: 438,
    flag: FLAGS[FLAGS.w]
  };
  var getWriteFileOptions = optsGenerator(writeFileDefaults);
  var appendFileDefaults = {
    encoding: "utf8",
    mode: 438,
    flag: FLAGS[FLAGS.a]
  };
  var getAppendFileOpts = optsGenerator(appendFileDefaults);
  var getAppendFileOptsAndCb = optsAndCbGenerator(getAppendFileOpts);
  var realpathDefaults = optsDefaults;
  var getRealpathOptions = optsGenerator(realpathDefaults);
  var getRealpathOptsAndCb = optsAndCbGenerator(getRealpathOptions);
  var mkdirDefaults = {
    mode: 511,
    recursive: false
  };
  var getMkdirOptions = function(options) {
    if (typeof options === "number") return Object.assign({}, mkdirDefaults, {
      mode: options
    });
    return Object.assign({}, mkdirDefaults, options);
  };
  var rmdirDefaults = {
    recursive: false
  };
  var getRmdirOptions = function(options) {
    return Object.assign({}, rmdirDefaults, options);
  };
  var getRmOpts = optsGenerator(optsDefaults);
  var getRmOptsAndCb = optsAndCbGenerator(getRmOpts);
  var readdirDefaults = {
    encoding: "utf8",
    withFileTypes: false
  };
  var getReaddirOptions = optsGenerator(readdirDefaults);
  var getReaddirOptsAndCb = optsAndCbGenerator(getReaddirOptions);
  var statDefaults = {
    bigint: false
  };
  var getStatOptions = function(options) {
    if (options === void 0) {
      options = {};
    }
    return Object.assign({}, statDefaults, options);
  };
  var getStatOptsAndCb = function(options, callback) {
    return typeof options === "function" ? [getStatOptions(), options] : [getStatOptions(options), validateCallback(callback)];
  };
  function getPathFromURLPosix3(url) {
    if (url.hostname !== "") {
      throw new errors.TypeError("ERR_INVALID_FILE_URL_HOST", process_1.default.platform);
    }
    var pathname = url.pathname;
    for (var n6 = 0; n6 < pathname.length; n6++) {
      if (pathname[n6] === "%") {
        var third = pathname.codePointAt(n6 + 2) | 32;
        if (pathname[n6 + 1] === "2" && third === 102) {
          throw new errors.TypeError("ERR_INVALID_FILE_URL_PATH", "must not include encoded / characters");
        }
      }
    }
    return decodeURIComponent(pathname);
  }
  function pathToFilename(path2) {
    if (typeof path2 !== "string" && !buffer_1.Buffer.isBuffer(path2)) {
      try {
        if (!(path2 instanceof h3.URL)) throw new TypeError(ERRSTR.PATH_STR);
      } catch (err) {
        throw new TypeError(ERRSTR.PATH_STR);
      }
      path2 = getPathFromURLPosix3(path2);
    }
    var pathString = String(path2);
    nullCheck(pathString);
    return pathString;
  }
  exports$44.pathToFilename = pathToFilename;
  var resolve2 = function(filename, base) {
    if (base === void 0) {
      base = process_1.default.cwd();
    }
    return resolveCrossPlatform(base, filename);
  };
  if (isWin) {
    var _resolve_1 = resolve2;
    var unixify_1 = dew$34().unixify;
    resolve2 = function(filename, base) {
      return unixify_1(_resolve_1(filename, base));
    };
  }
  function filenameToSteps(filename, base) {
    var fullPath = resolve2(filename, base);
    var fullPathSansSlash = fullPath.substring(1);
    if (!fullPathSansSlash) return [];
    return fullPathSansSlash.split(sep);
  }
  exports$44.filenameToSteps = filenameToSteps;
  function pathToSteps(path2) {
    return filenameToSteps(pathToFilename(path2));
  }
  exports$44.pathToSteps = pathToSteps;
  function dataToStr(data, encoding) {
    if (encoding === void 0) {
      encoding = encoding_1.ENCODING_UTF8;
    }
    if (buffer_1.Buffer.isBuffer(data)) return data.toString(encoding);
    else if (data instanceof Uint8Array) return (0, buffer_1.bufferFrom)(data).toString(encoding);
    else return String(data);
  }
  exports$44.dataToStr = dataToStr;
  function dataToBuffer(data, encoding) {
    if (encoding === void 0) {
      encoding = encoding_1.ENCODING_UTF8;
    }
    if (buffer_1.Buffer.isBuffer(data)) return data;
    else if (data instanceof Uint8Array) return (0, buffer_1.bufferFrom)(data);
    else return (0, buffer_1.bufferFrom)(String(data), encoding);
  }
  exports$44.dataToBuffer = dataToBuffer;
  function bufferToEncoding(buffer2, encoding) {
    if (!encoding || encoding === "buffer") return buffer2;
    else return buffer2.toString(encoding);
  }
  exports$44.bufferToEncoding = bufferToEncoding;
  function nullCheck(path2, callback) {
    if (("" + path2).indexOf("\0") !== -1) {
      var er = new Error("Path must be a string without null bytes");
      er.code = ENOENT;
      throw er;
    }
    return true;
  }
  function _modeToNumber(mode, def) {
    if (typeof mode === "number") return mode;
    if (typeof mode === "string") return parseInt(mode, 8);
    if (def) return modeToNumber(def);
    return void 0;
  }
  function modeToNumber(mode, def) {
    var result = _modeToNumber(mode, def);
    if (typeof result !== "number" || isNaN(result)) throw new TypeError(ERRSTR.MODE_INT);
    return result;
  }
  function isFd(path2) {
    return path2 >>> 0 === path2;
  }
  function validateFd(fd) {
    if (!isFd(fd)) throw TypeError(ERRSTR.FD);
  }
  function toUnixTimestamp(time) {
    if (typeof time === "string" && +time == time) {
      return +time;
    }
    if (time instanceof Date) {
      return time.getTime() / 1e3;
    }
    if (isFinite(time)) {
      if (time < 0) {
        return Date.now() / 1e3;
      }
      return time;
    }
    throw new Error("Cannot parse time: " + time);
  }
  exports$44.toUnixTimestamp = toUnixTimestamp;
  function validateUid(uid) {
    if (typeof uid !== "number") throw TypeError(ERRSTR.UID);
  }
  function validateGid(gid) {
    if (typeof gid !== "number") throw TypeError(ERRSTR.GID);
  }
  function flattenJSON(nestedJSON) {
    var flatJSON = {};
    function flatten(pathPrefix, node) {
      for (var path2 in node) {
        var contentOrNode = node[path2];
        var joinedPath = join(pathPrefix, path2);
        if (typeof contentOrNode === "string") {
          flatJSON[joinedPath] = contentOrNode;
        } else if (typeof contentOrNode === "object" && contentOrNode !== null && Object.keys(contentOrNode).length > 0) {
          flatten(joinedPath, contentOrNode);
        } else {
          flatJSON[joinedPath] = null;
        }
      }
    }
    flatten("", nestedJSON);
    return flatJSON;
  }
  var Volume = (
    /** @class */
    (function() {
      function Volume2(props) {
        if (props === void 0) {
          props = {};
        }
        this.ino = 0;
        this.inodes = {};
        this.releasedInos = [];
        this.fds = {};
        this.releasedFds = [];
        this.maxFiles = 1e4;
        this.openFiles = 0;
        this.promisesApi = (0, promises_1.default)(this);
        this.statWatchers = {};
        this.props = Object.assign({
          Node: node_1.Node,
          Link: node_1.Link,
          File: node_1.File
        }, props);
        var root = this.createLink();
        root.setNode(this.createNode(true));
        var self2 = this;
        this.StatWatcher = /** @class */
        (function(_super) {
          __extends(StatWatcher2, _super);
          function StatWatcher2() {
            return _super.call(this, self2) || this;
          }
          return StatWatcher2;
        })(StatWatcher);
        var _ReadStream = FsReadStream;
        this.ReadStream = /** @class */
        (function(_super) {
          __extends(class_1, _super);
          function class_1() {
            var args = [];
            for (var _i = 0; _i < arguments.length; _i++) {
              args[_i] = arguments[_i];
            }
            return _super.apply(this, __spreadArray([self2], args, false)) || this;
          }
          return class_1;
        })(_ReadStream);
        var _WriteStream = FsWriteStream;
        this.WriteStream = /** @class */
        (function(_super) {
          __extends(class_2, _super);
          function class_2() {
            var args = [];
            for (var _i = 0; _i < arguments.length; _i++) {
              args[_i] = arguments[_i];
            }
            return _super.apply(this, __spreadArray([self2], args, false)) || this;
          }
          return class_2;
        })(_WriteStream);
        this.FSWatcher = /** @class */
        (function(_super) {
          __extends(FSWatcher2, _super);
          function FSWatcher2() {
            return _super.call(this, self2) || this;
          }
          return FSWatcher2;
        })(FSWatcher);
        root.setChild(".", root);
        root.getNode().nlink++;
        root.setChild("..", root);
        root.getNode().nlink++;
        this.root = root;
      }
      Volume2.fromJSON = function(json, cwd3) {
        var vol2 = new Volume2();
        vol2.fromJSON(json, cwd3);
        return vol2;
      };
      Volume2.fromNestedJSON = function(json, cwd3) {
        var vol2 = new Volume2();
        vol2.fromNestedJSON(json, cwd3);
        return vol2;
      };
      Object.defineProperty(Volume2.prototype, "promises", {
        get: function() {
          if (this.promisesApi === null) throw new Error("Promise is not supported in this environment.");
          return this.promisesApi;
        },
        enumerable: false,
        configurable: true
      });
      Volume2.prototype.createLink = function(parent, name2, isDirectory, perm) {
        if (isDirectory === void 0) {
          isDirectory = false;
        }
        if (!parent) {
          return new this.props.Link(this, null, "");
        }
        if (!name2) {
          throw new Error("createLink: name cannot be empty");
        }
        return parent.createChild(name2, this.createNode(isDirectory, perm));
      };
      Volume2.prototype.deleteLink = function(link3) {
        var parent = link3.parent;
        if (parent) {
          parent.deleteChild(link3);
          return true;
        }
        return false;
      };
      Volume2.prototype.newInoNumber = function() {
        var releasedFd = this.releasedInos.pop();
        if (releasedFd) return releasedFd;
        else {
          this.ino = (this.ino + 1) % 4294967295;
          return this.ino;
        }
      };
      Volume2.prototype.newFdNumber = function() {
        var releasedFd = this.releasedFds.pop();
        return typeof releasedFd === "number" ? releasedFd : Volume2.fd--;
      };
      Volume2.prototype.createNode = function(isDirectory, perm) {
        if (isDirectory === void 0) {
          isDirectory = false;
        }
        var node = new this.props.Node(this.newInoNumber(), perm);
        if (isDirectory) node.setIsDirectory();
        this.inodes[node.ino] = node;
        return node;
      };
      Volume2.prototype.getNode = function(ino) {
        return this.inodes[ino];
      };
      Volume2.prototype.deleteNode = function(node) {
        node.del();
        delete this.inodes[node.ino];
        this.releasedInos.push(node.ino);
      };
      Volume2.prototype.genRndStr = function() {
        var str = (Math.random() + 1).toString(36).substring(2, 8);
        if (str.length === 6) return str;
        else return this.genRndStr();
      };
      Volume2.prototype.getLink = function(steps) {
        return this.root.walk(steps);
      };
      Volume2.prototype.getLinkOrThrow = function(filename, funcName) {
        var steps = filenameToSteps(filename);
        var link3 = this.getLink(steps);
        if (!link3) throw createError(ENOENT, funcName, filename);
        return link3;
      };
      Volume2.prototype.getResolvedLink = function(filenameOrSteps) {
        var steps = typeof filenameOrSteps === "string" ? filenameToSteps(filenameOrSteps) : filenameOrSteps;
        var link3 = this.root;
        var i6 = 0;
        while (i6 < steps.length) {
          var step = steps[i6];
          link3 = link3.getChild(step);
          if (!link3) return null;
          var node = link3.getNode();
          if (node.isSymlink()) {
            steps = node.symlink.concat(steps.slice(i6 + 1));
            link3 = this.root;
            i6 = 0;
            continue;
          }
          i6++;
        }
        return link3;
      };
      Volume2.prototype.getResolvedLinkOrThrow = function(filename, funcName) {
        var link3 = this.getResolvedLink(filename);
        if (!link3) throw createError(ENOENT, funcName, filename);
        return link3;
      };
      Volume2.prototype.resolveSymlinks = function(link3) {
        return this.getResolvedLink(link3.steps.slice(1));
      };
      Volume2.prototype.getLinkAsDirOrThrow = function(filename, funcName) {
        var link3 = this.getLinkOrThrow(filename, funcName);
        if (!link3.getNode().isDirectory()) throw createError(ENOTDIR, funcName, filename);
        return link3;
      };
      Volume2.prototype.getLinkParent = function(steps) {
        return this.root.walk(steps, steps.length - 1);
      };
      Volume2.prototype.getLinkParentAsDirOrThrow = function(filenameOrSteps, funcName) {
        var steps = filenameOrSteps instanceof Array ? filenameOrSteps : filenameToSteps(filenameOrSteps);
        var link3 = this.getLinkParent(steps);
        if (!link3) throw createError(ENOENT, funcName, sep + steps.join(sep));
        if (!link3.getNode().isDirectory()) throw createError(ENOTDIR, funcName, sep + steps.join(sep));
        return link3;
      };
      Volume2.prototype.getFileByFd = function(fd) {
        return this.fds[String(fd)];
      };
      Volume2.prototype.getFileByFdOrThrow = function(fd, funcName) {
        if (!isFd(fd)) throw TypeError(ERRSTR.FD);
        var file = this.getFileByFd(fd);
        if (!file) throw createError(EBADF, funcName);
        return file;
      };
      Volume2.prototype.wrapAsync = function(method, args, callback) {
        var _this = this;
        validateCallback(callback);
        (0, setImmediate_1.default)(function() {
          var result;
          try {
            result = method.apply(_this, args);
          } catch (err) {
            callback(err);
            return;
          }
          callback(null, result);
        });
      };
      Volume2.prototype._toJSON = function(link3, json, path2) {
        var _a2;
        if (link3 === void 0) {
          link3 = this.root;
        }
        if (json === void 0) {
          json = {};
        }
        var isEmpty = true;
        var children = link3.children;
        if (link3.getNode().isFile()) {
          children = (_a2 = {}, _a2[link3.getName()] = link3.parent.getChild(link3.getName()), _a2);
          link3 = link3.parent;
        }
        for (var name_1 in children) {
          if (name_1 === "." || name_1 === "..") {
            continue;
          }
          isEmpty = false;
          var child = link3.getChild(name_1);
          if (!child) {
            throw new Error("_toJSON: unexpected undefined");
          }
          var node = child.getNode();
          if (node.isFile()) {
            var filename = child.getPath();
            if (path2) filename = relative(path2, filename);
            json[filename] = node.getString();
          } else if (node.isDirectory()) {
            this._toJSON(child, json, path2);
          }
        }
        var dirPath = link3.getPath();
        if (path2) dirPath = relative(path2, dirPath);
        if (dirPath && isEmpty) {
          json[dirPath] = null;
        }
        return json;
      };
      Volume2.prototype.toJSON = function(paths, json, isRelative) {
        if (json === void 0) {
          json = {};
        }
        if (isRelative === void 0) {
          isRelative = false;
        }
        var links = [];
        if (paths) {
          if (!(paths instanceof Array)) paths = [paths];
          for (var _i = 0, paths_1 = paths; _i < paths_1.length; _i++) {
            var path2 = paths_1[_i];
            var filename = pathToFilename(path2);
            var link3 = this.getResolvedLink(filename);
            if (!link3) continue;
            links.push(link3);
          }
        } else {
          links.push(this.root);
        }
        if (!links.length) return json;
        for (var _a2 = 0, links_1 = links; _a2 < links_1.length; _a2++) {
          var link3 = links_1[_a2];
          this._toJSON(link3, json, isRelative ? link3.getPath() : "");
        }
        return json;
      };
      Volume2.prototype.fromJSON = function(json, cwd3) {
        if (cwd3 === void 0) {
          cwd3 = process_1.default.cwd();
        }
        for (var filename in json) {
          var data = json[filename];
          filename = resolve2(filename, cwd3);
          if (typeof data === "string") {
            var dir = dirname(filename);
            this.mkdirpBase(
              dir,
              511
              /* MODE.DIR */
            );
            this.writeFileSync(filename, data);
          } else {
            this.mkdirpBase(
              filename,
              511
              /* MODE.DIR */
            );
          }
        }
      };
      Volume2.prototype.fromNestedJSON = function(json, cwd3) {
        this.fromJSON(flattenJSON(json), cwd3);
      };
      Volume2.prototype.reset = function() {
        this.ino = 0;
        this.inodes = {};
        this.releasedInos = [];
        this.fds = {};
        this.releasedFds = [];
        this.openFiles = 0;
        this.root = this.createLink();
        this.root.setNode(this.createNode(true));
      };
      Volume2.prototype.mountSync = function(mountpoint, json) {
        this.fromJSON(json, mountpoint);
      };
      Volume2.prototype.openLink = function(link3, flagsNum, resolveSymlinks) {
        if (resolveSymlinks === void 0) {
          resolveSymlinks = true;
        }
        if (this.openFiles >= this.maxFiles) {
          throw createError(EMFILE, "open", link3.getPath());
        }
        var realLink = link3;
        if (resolveSymlinks) realLink = this.resolveSymlinks(link3);
        if (!realLink) throw createError(ENOENT, "open", link3.getPath());
        var node = realLink.getNode();
        if (node.isDirectory()) {
          if ((flagsNum & (O_RDONLY | O_RDWR | O_WRONLY)) !== O_RDONLY) throw createError(EISDIR, "open", link3.getPath());
        } else {
          if (flagsNum & O_DIRECTORY) throw createError(ENOTDIR, "open", link3.getPath());
        }
        if (!(flagsNum & O_WRONLY)) {
          if (!node.canRead()) {
            throw createError(EACCES, "open", link3.getPath());
          }
        }
        var file = new this.props.File(link3, node, flagsNum, this.newFdNumber());
        this.fds[file.fd] = file;
        this.openFiles++;
        if (flagsNum & O_TRUNC) file.truncate();
        return file;
      };
      Volume2.prototype.openFile = function(filename, flagsNum, modeNum, resolveSymlinks) {
        if (resolveSymlinks === void 0) {
          resolveSymlinks = true;
        }
        var steps = filenameToSteps(filename);
        var link3 = resolveSymlinks ? this.getResolvedLink(steps) : this.getLink(steps);
        if (link3 && flagsNum & O_EXCL) throw createError(EEXIST, "open", filename);
        if (!link3 && flagsNum & O_CREAT) {
          var dirLink = this.getResolvedLink(steps.slice(0, steps.length - 1));
          if (!dirLink) throw createError(ENOENT, "open", sep + steps.join(sep));
          if (flagsNum & O_CREAT && typeof modeNum === "number") {
            link3 = this.createLink(dirLink, steps[steps.length - 1], false, modeNum);
          }
        }
        if (link3) return this.openLink(link3, flagsNum, resolveSymlinks);
        throw createError(ENOENT, "open", filename);
      };
      Volume2.prototype.openBase = function(filename, flagsNum, modeNum, resolveSymlinks) {
        if (resolveSymlinks === void 0) {
          resolveSymlinks = true;
        }
        var file = this.openFile(filename, flagsNum, modeNum, resolveSymlinks);
        if (!file) throw createError(ENOENT, "open", filename);
        return file.fd;
      };
      Volume2.prototype.openSync = function(path2, flags, mode) {
        if (mode === void 0) {
          mode = 438;
        }
        var modeNum = modeToNumber(mode);
        var fileName = pathToFilename(path2);
        var flagsNum = flagsToNumber(flags);
        return this.openBase(fileName, flagsNum, modeNum);
      };
      Volume2.prototype.open = function(path2, flags, a6, b5) {
        var mode = a6;
        var callback = b5;
        if (typeof a6 === "function") {
          mode = 438;
          callback = a6;
        }
        mode = mode || 438;
        var modeNum = modeToNumber(mode);
        var fileName = pathToFilename(path2);
        var flagsNum = flagsToNumber(flags);
        this.wrapAsync(this.openBase, [fileName, flagsNum, modeNum], callback);
      };
      Volume2.prototype.closeFile = function(file) {
        if (!this.fds[file.fd]) return;
        this.openFiles--;
        delete this.fds[file.fd];
        this.releasedFds.push(file.fd);
      };
      Volume2.prototype.closeSync = function(fd) {
        validateFd(fd);
        var file = this.getFileByFdOrThrow(fd, "close");
        this.closeFile(file);
      };
      Volume2.prototype.close = function(fd, callback) {
        validateFd(fd);
        this.wrapAsync(this.closeSync, [fd], callback);
      };
      Volume2.prototype.openFileOrGetById = function(id2, flagsNum, modeNum) {
        if (typeof id2 === "number") {
          var file = this.fds[id2];
          if (!file) throw createError(ENOENT);
          return file;
        } else {
          return this.openFile(pathToFilename(id2), flagsNum, modeNum);
        }
      };
      Volume2.prototype.readBase = function(fd, buffer2, offset, length, position) {
        var file = this.getFileByFdOrThrow(fd);
        return file.read(buffer2, Number(offset), Number(length), position);
      };
      Volume2.prototype.readSync = function(fd, buffer2, offset, length, position) {
        validateFd(fd);
        return this.readBase(fd, buffer2, offset, length, position);
      };
      Volume2.prototype.read = function(fd, buffer2, offset, length, position, callback) {
        var _this = this;
        validateCallback(callback);
        if (length === 0) {
          return process_1.default.nextTick(function() {
            if (callback) callback(null, 0, buffer2);
          });
        }
        (0, setImmediate_1.default)(function() {
          try {
            var bytes = _this.readBase(fd, buffer2, offset, length, position);
            callback(null, bytes, buffer2);
          } catch (err) {
            callback(err);
          }
        });
      };
      Volume2.prototype.readFileBase = function(id2, flagsNum, encoding) {
        var result;
        var isUserFd = typeof id2 === "number";
        var userOwnsFd = isUserFd && isFd(id2);
        var fd;
        if (userOwnsFd) fd = id2;
        else {
          var filename = pathToFilename(id2);
          var steps = filenameToSteps(filename);
          var link3 = this.getResolvedLink(steps);
          if (link3) {
            var node = link3.getNode();
            if (node.isDirectory()) throw createError(EISDIR, "open", link3.getPath());
          }
          fd = this.openSync(id2, flagsNum);
        }
        try {
          result = bufferToEncoding(this.getFileByFdOrThrow(fd).getBuffer(), encoding);
        } finally {
          if (!userOwnsFd) {
            this.closeSync(fd);
          }
        }
        return result;
      };
      Volume2.prototype.readFileSync = function(file, options) {
        var opts = getReadFileOptions(options);
        var flagsNum = flagsToNumber(opts.flag);
        return this.readFileBase(file, flagsNum, opts.encoding);
      };
      Volume2.prototype.readFile = function(id2, a6, b5) {
        var _a2 = optsAndCbGenerator(getReadFileOptions)(a6, b5), opts = _a2[0], callback = _a2[1];
        var flagsNum = flagsToNumber(opts.flag);
        this.wrapAsync(this.readFileBase, [id2, flagsNum, opts.encoding], callback);
      };
      Volume2.prototype.writeBase = function(fd, buf, offset, length, position) {
        var file = this.getFileByFdOrThrow(fd, "write");
        return file.write(buf, offset, length, position);
      };
      Volume2.prototype.writeSync = function(fd, a6, b5, c6, d5) {
        validateFd(fd);
        var encoding;
        var offset;
        var length;
        var position;
        var isBuffer = typeof a6 !== "string";
        if (isBuffer) {
          offset = (b5 || 0) | 0;
          length = c6;
          position = d5;
        } else {
          position = b5;
          encoding = c6;
        }
        var buf = dataToBuffer(a6, encoding);
        if (isBuffer) {
          if (typeof length === "undefined") {
            length = buf.length;
          }
        } else {
          offset = 0;
          length = buf.length;
        }
        return this.writeBase(fd, buf, offset, length, position);
      };
      Volume2.prototype.write = function(fd, a6, b5, c6, d5, e6) {
        var _this = this;
        validateFd(fd);
        var offset;
        var length;
        var position;
        var encoding;
        var callback;
        var tipa = typeof a6;
        var tipb = typeof b5;
        var tipc = typeof c6;
        var tipd = typeof d5;
        if (tipa !== "string") {
          if (tipb === "function") {
            callback = b5;
          } else if (tipc === "function") {
            offset = b5 | 0;
            callback = c6;
          } else if (tipd === "function") {
            offset = b5 | 0;
            length = c6;
            callback = d5;
          } else {
            offset = b5 | 0;
            length = c6;
            position = d5;
            callback = e6;
          }
        } else {
          if (tipb === "function") {
            callback = b5;
          } else if (tipc === "function") {
            position = b5;
            callback = c6;
          } else if (tipd === "function") {
            position = b5;
            encoding = c6;
            callback = d5;
          }
        }
        var buf = dataToBuffer(a6, encoding);
        if (tipa !== "string") {
          if (typeof length === "undefined") length = buf.length;
        } else {
          offset = 0;
          length = buf.length;
        }
        var cb = validateCallback(callback);
        (0, setImmediate_1.default)(function() {
          try {
            var bytes = _this.writeBase(fd, buf, offset, length, position);
            if (tipa !== "string") {
              cb(null, bytes, buf);
            } else {
              cb(null, bytes, a6);
            }
          } catch (err) {
            cb(err);
          }
        });
      };
      Volume2.prototype.writeFileBase = function(id2, buf, flagsNum, modeNum) {
        var isUserFd = typeof id2 === "number";
        var fd;
        if (isUserFd) fd = id2;
        else {
          fd = this.openBase(pathToFilename(id2), flagsNum, modeNum);
        }
        var offset = 0;
        var length = buf.length;
        var position = flagsNum & O_APPEND ? void 0 : 0;
        try {
          while (length > 0) {
            var written = this.writeSync(fd, buf, offset, length, position);
            offset += written;
            length -= written;
            if (position !== void 0) position += written;
          }
        } finally {
          if (!isUserFd) this.closeSync(fd);
        }
      };
      Volume2.prototype.writeFileSync = function(id2, data, options) {
        var opts = getWriteFileOptions(options);
        var flagsNum = flagsToNumber(opts.flag);
        var modeNum = modeToNumber(opts.mode);
        var buf = dataToBuffer(data, opts.encoding);
        this.writeFileBase(id2, buf, flagsNum, modeNum);
      };
      Volume2.prototype.writeFile = function(id2, data, a6, b5) {
        var options = a6;
        var callback = b5;
        if (typeof a6 === "function") {
          options = writeFileDefaults;
          callback = a6;
        }
        var cb = validateCallback(callback);
        var opts = getWriteFileOptions(options);
        var flagsNum = flagsToNumber(opts.flag);
        var modeNum = modeToNumber(opts.mode);
        var buf = dataToBuffer(data, opts.encoding);
        this.wrapAsync(this.writeFileBase, [id2, buf, flagsNum, modeNum], cb);
      };
      Volume2.prototype.linkBase = function(filename1, filename2) {
        var steps1 = filenameToSteps(filename1);
        var link1 = this.getLink(steps1);
        if (!link1) throw createError(ENOENT, "link", filename1, filename2);
        var steps2 = filenameToSteps(filename2);
        var dir2 = this.getLinkParent(steps2);
        if (!dir2) throw createError(ENOENT, "link", filename1, filename2);
        var name2 = steps2[steps2.length - 1];
        if (dir2.getChild(name2)) throw createError(EEXIST, "link", filename1, filename2);
        var node = link1.getNode();
        node.nlink++;
        dir2.createChild(name2, node);
      };
      Volume2.prototype.copyFileBase = function(src, dest, flags) {
        var buf = this.readFileSync(src);
        if (flags & COPYFILE_EXCL) {
          if (this.existsSync(dest)) {
            throw createError(EEXIST, "copyFile", src, dest);
          }
        }
        if (flags & COPYFILE_FICLONE_FORCE) {
          throw createError(ENOSYS, "copyFile", src, dest);
        }
        this.writeFileBase(
          dest,
          buf,
          FLAGS.w,
          438
          /* MODE.DEFAULT */
        );
      };
      Volume2.prototype.copyFileSync = function(src, dest, flags) {
        var srcFilename = pathToFilename(src);
        var destFilename = pathToFilename(dest);
        return this.copyFileBase(srcFilename, destFilename, (flags || 0) | 0);
      };
      Volume2.prototype.copyFile = function(src, dest, a6, b5) {
        var srcFilename = pathToFilename(src);
        var destFilename = pathToFilename(dest);
        var flags;
        var callback;
        if (typeof a6 === "function") {
          flags = 0;
          callback = a6;
        } else {
          flags = a6;
          callback = b5;
        }
        validateCallback(callback);
        this.wrapAsync(this.copyFileBase, [srcFilename, destFilename, flags], callback);
      };
      Volume2.prototype.linkSync = function(existingPath, newPath) {
        var existingPathFilename = pathToFilename(existingPath);
        var newPathFilename = pathToFilename(newPath);
        this.linkBase(existingPathFilename, newPathFilename);
      };
      Volume2.prototype.link = function(existingPath, newPath, callback) {
        var existingPathFilename = pathToFilename(existingPath);
        var newPathFilename = pathToFilename(newPath);
        this.wrapAsync(this.linkBase, [existingPathFilename, newPathFilename], callback);
      };
      Volume2.prototype.unlinkBase = function(filename) {
        var steps = filenameToSteps(filename);
        var link3 = this.getLink(steps);
        if (!link3) throw createError(ENOENT, "unlink", filename);
        if (link3.length) throw Error("Dir not empty...");
        this.deleteLink(link3);
        var node = link3.getNode();
        node.nlink--;
        if (node.nlink <= 0) {
          this.deleteNode(node);
        }
      };
      Volume2.prototype.unlinkSync = function(path2) {
        var filename = pathToFilename(path2);
        this.unlinkBase(filename);
      };
      Volume2.prototype.unlink = function(path2, callback) {
        var filename = pathToFilename(path2);
        this.wrapAsync(this.unlinkBase, [filename], callback);
      };
      Volume2.prototype.symlinkBase = function(targetFilename, pathFilename) {
        var pathSteps = filenameToSteps(pathFilename);
        var dirLink = this.getLinkParent(pathSteps);
        if (!dirLink) throw createError(ENOENT, "symlink", targetFilename, pathFilename);
        var name2 = pathSteps[pathSteps.length - 1];
        if (dirLink.getChild(name2)) throw createError(EEXIST, "symlink", targetFilename, pathFilename);
        var symlink3 = dirLink.createChild(name2);
        symlink3.getNode().makeSymlink(filenameToSteps(targetFilename));
        return symlink3;
      };
      Volume2.prototype.symlinkSync = function(target, path2, type) {
        var targetFilename = pathToFilename(target);
        var pathFilename = pathToFilename(path2);
        this.symlinkBase(targetFilename, pathFilename);
      };
      Volume2.prototype.symlink = function(target, path2, a6, b5) {
        var callback = validateCallback(typeof a6 === "function" ? a6 : b5);
        var targetFilename = pathToFilename(target);
        var pathFilename = pathToFilename(path2);
        this.wrapAsync(this.symlinkBase, [targetFilename, pathFilename], callback);
      };
      Volume2.prototype.realpathBase = function(filename, encoding) {
        var steps = filenameToSteps(filename);
        var realLink = this.getResolvedLink(steps);
        if (!realLink) throw createError(ENOENT, "realpath", filename);
        return (0, encoding_1.strToEncoding)(realLink.getPath() || "/", encoding);
      };
      Volume2.prototype.realpathSync = function(path2, options) {
        return this.realpathBase(pathToFilename(path2), getRealpathOptions(options).encoding);
      };
      Volume2.prototype.realpath = function(path2, a6, b5) {
        var _a2 = getRealpathOptsAndCb(a6, b5), opts = _a2[0], callback = _a2[1];
        var pathFilename = pathToFilename(path2);
        this.wrapAsync(this.realpathBase, [pathFilename, opts.encoding], callback);
      };
      Volume2.prototype.lstatBase = function(filename, bigint, throwIfNoEntry) {
        if (bigint === void 0) {
          bigint = false;
        }
        if (throwIfNoEntry === void 0) {
          throwIfNoEntry = false;
        }
        var link3 = this.getLink(filenameToSteps(filename));
        if (link3) {
          return Stats_1.default.build(link3.getNode(), bigint);
        } else if (!throwIfNoEntry) {
          return void 0;
        } else {
          throw createError(ENOENT, "lstat", filename);
        }
      };
      Volume2.prototype.lstatSync = function(path2, options) {
        var _a2 = getStatOptions(options), _b = _a2.throwIfNoEntry, throwIfNoEntry = _b === void 0 ? true : _b, _c = _a2.bigint, bigint = _c === void 0 ? false : _c;
        return this.lstatBase(pathToFilename(path2), bigint, throwIfNoEntry);
      };
      Volume2.prototype.lstat = function(path2, a6, b5) {
        var _a2 = getStatOptsAndCb(a6, b5), _b = _a2[0], _c = _b.throwIfNoEntry, throwIfNoEntry = _c === void 0 ? true : _c, _d = _b.bigint, bigint = _d === void 0 ? false : _d, callback = _a2[1];
        this.wrapAsync(this.lstatBase, [pathToFilename(path2), bigint, throwIfNoEntry], callback);
      };
      Volume2.prototype.statBase = function(filename, bigint, throwIfNoEntry) {
        if (bigint === void 0) {
          bigint = false;
        }
        if (throwIfNoEntry === void 0) {
          throwIfNoEntry = true;
        }
        var link3 = this.getResolvedLink(filenameToSteps(filename));
        if (link3) {
          return Stats_1.default.build(link3.getNode(), bigint);
        } else if (!throwIfNoEntry) {
          return void 0;
        } else {
          throw createError(ENOENT, "stat", filename);
        }
      };
      Volume2.prototype.statSync = function(path2, options) {
        var _a2 = getStatOptions(options), _b = _a2.bigint, bigint = _b === void 0 ? true : _b, _c = _a2.throwIfNoEntry, throwIfNoEntry = _c === void 0 ? true : _c;
        return this.statBase(pathToFilename(path2), bigint, throwIfNoEntry);
      };
      Volume2.prototype.stat = function(path2, a6, b5) {
        var _a2 = getStatOptsAndCb(a6, b5), _b = _a2[0], _c = _b.bigint, bigint = _c === void 0 ? false : _c, _d = _b.throwIfNoEntry, throwIfNoEntry = _d === void 0 ? true : _d, callback = _a2[1];
        this.wrapAsync(this.statBase, [pathToFilename(path2), bigint, throwIfNoEntry], callback);
      };
      Volume2.prototype.fstatBase = function(fd, bigint) {
        if (bigint === void 0) {
          bigint = false;
        }
        var file = this.getFileByFd(fd);
        if (!file) throw createError(EBADF, "fstat");
        return Stats_1.default.build(file.node, bigint);
      };
      Volume2.prototype.fstatSync = function(fd, options) {
        return this.fstatBase(fd, getStatOptions(options).bigint);
      };
      Volume2.prototype.fstat = function(fd, a6, b5) {
        var _a2 = getStatOptsAndCb(a6, b5), opts = _a2[0], callback = _a2[1];
        this.wrapAsync(this.fstatBase, [fd, opts.bigint], callback);
      };
      Volume2.prototype.renameBase = function(oldPathFilename, newPathFilename) {
        var link3 = this.getLink(filenameToSteps(oldPathFilename));
        if (!link3) throw createError(ENOENT, "rename", oldPathFilename, newPathFilename);
        var newPathSteps = filenameToSteps(newPathFilename);
        var newPathDirLink = this.getLinkParent(newPathSteps);
        if (!newPathDirLink) throw createError(ENOENT, "rename", oldPathFilename, newPathFilename);
        var oldLinkParent = link3.parent;
        if (oldLinkParent) {
          oldLinkParent.deleteChild(link3);
        }
        var name2 = newPathSteps[newPathSteps.length - 1];
        link3.name = name2;
        link3.steps = __spreadArray(__spreadArray([], newPathDirLink.steps, true), [name2], false);
        newPathDirLink.setChild(link3.getName(), link3);
      };
      Volume2.prototype.renameSync = function(oldPath, newPath) {
        var oldPathFilename = pathToFilename(oldPath);
        var newPathFilename = pathToFilename(newPath);
        this.renameBase(oldPathFilename, newPathFilename);
      };
      Volume2.prototype.rename = function(oldPath, newPath, callback) {
        var oldPathFilename = pathToFilename(oldPath);
        var newPathFilename = pathToFilename(newPath);
        this.wrapAsync(this.renameBase, [oldPathFilename, newPathFilename], callback);
      };
      Volume2.prototype.existsBase = function(filename) {
        return !!this.statBase(filename);
      };
      Volume2.prototype.existsSync = function(path2) {
        try {
          return this.existsBase(pathToFilename(path2));
        } catch (err) {
          return false;
        }
      };
      Volume2.prototype.exists = function(path2, callback) {
        var _this = this;
        var filename = pathToFilename(path2);
        if (typeof callback !== "function") throw Error(ERRSTR.CB);
        (0, setImmediate_1.default)(function() {
          try {
            callback(_this.existsBase(filename));
          } catch (err) {
            callback(false);
          }
        });
      };
      Volume2.prototype.accessBase = function(filename, mode) {
        this.getLinkOrThrow(filename, "access");
      };
      Volume2.prototype.accessSync = function(path2, mode) {
        if (mode === void 0) {
          mode = F_OK2;
        }
        var filename = pathToFilename(path2);
        mode = mode | 0;
        this.accessBase(filename, mode);
      };
      Volume2.prototype.access = function(path2, a6, b5) {
        var mode = F_OK2;
        var callback;
        if (typeof a6 !== "function") {
          mode = a6 | 0;
          callback = validateCallback(b5);
        } else {
          callback = a6;
        }
        var filename = pathToFilename(path2);
        this.wrapAsync(this.accessBase, [filename, mode], callback);
      };
      Volume2.prototype.appendFileSync = function(id2, data, options) {
        if (options === void 0) {
          options = appendFileDefaults;
        }
        var opts = getAppendFileOpts(options);
        if (!opts.flag || isFd(id2)) opts.flag = "a";
        this.writeFileSync(id2, data, opts);
      };
      Volume2.prototype.appendFile = function(id2, data, a6, b5) {
        var _a2 = getAppendFileOptsAndCb(a6, b5), opts = _a2[0], callback = _a2[1];
        if (!opts.flag || isFd(id2)) opts.flag = "a";
        this.writeFile(id2, data, opts, callback);
      };
      Volume2.prototype.readdirBase = function(filename, options) {
        var steps = filenameToSteps(filename);
        var link3 = this.getResolvedLink(steps);
        if (!link3) throw createError(ENOENT, "readdir", filename);
        var node = link3.getNode();
        if (!node.isDirectory()) throw createError(ENOTDIR, "scandir", filename);
        if (options.withFileTypes) {
          var list_1 = [];
          for (var name_2 in link3.children) {
            var child = link3.getChild(name_2);
            if (!child || name_2 === "." || name_2 === "..") {
              continue;
            }
            list_1.push(Dirent_1.default.build(child, options.encoding));
          }
          if (!isWin && options.encoding !== "buffer") list_1.sort(function(a6, b5) {
            if (a6.name < b5.name) return -1;
            if (a6.name > b5.name) return 1;
            return 0;
          });
          return list_1;
        }
        var list = [];
        for (var name_3 in link3.children) {
          if (name_3 === "." || name_3 === "..") {
            continue;
          }
          list.push((0, encoding_1.strToEncoding)(name_3, options.encoding));
        }
        if (!isWin && options.encoding !== "buffer") list.sort();
        return list;
      };
      Volume2.prototype.readdirSync = function(path2, options) {
        var opts = getReaddirOptions(options);
        var filename = pathToFilename(path2);
        return this.readdirBase(filename, opts);
      };
      Volume2.prototype.readdir = function(path2, a6, b5) {
        var _a2 = getReaddirOptsAndCb(a6, b5), options = _a2[0], callback = _a2[1];
        var filename = pathToFilename(path2);
        this.wrapAsync(this.readdirBase, [filename, options], callback);
      };
      Volume2.prototype.readlinkBase = function(filename, encoding) {
        var link3 = this.getLinkOrThrow(filename, "readlink");
        var node = link3.getNode();
        if (!node.isSymlink()) throw createError(EINVAL, "readlink", filename);
        var str = sep + node.symlink.join(sep);
        return (0, encoding_1.strToEncoding)(str, encoding);
      };
      Volume2.prototype.readlinkSync = function(path2, options) {
        var opts = getDefaultOpts(options);
        var filename = pathToFilename(path2);
        return this.readlinkBase(filename, opts.encoding);
      };
      Volume2.prototype.readlink = function(path2, a6, b5) {
        var _a2 = getDefaultOptsAndCb(a6, b5), opts = _a2[0], callback = _a2[1];
        var filename = pathToFilename(path2);
        this.wrapAsync(this.readlinkBase, [filename, opts.encoding], callback);
      };
      Volume2.prototype.fsyncBase = function(fd) {
        this.getFileByFdOrThrow(fd, "fsync");
      };
      Volume2.prototype.fsyncSync = function(fd) {
        this.fsyncBase(fd);
      };
      Volume2.prototype.fsync = function(fd, callback) {
        this.wrapAsync(this.fsyncBase, [fd], callback);
      };
      Volume2.prototype.fdatasyncBase = function(fd) {
        this.getFileByFdOrThrow(fd, "fdatasync");
      };
      Volume2.prototype.fdatasyncSync = function(fd) {
        this.fdatasyncBase(fd);
      };
      Volume2.prototype.fdatasync = function(fd, callback) {
        this.wrapAsync(this.fdatasyncBase, [fd], callback);
      };
      Volume2.prototype.ftruncateBase = function(fd, len) {
        var file = this.getFileByFdOrThrow(fd, "ftruncate");
        file.truncate(len);
      };
      Volume2.prototype.ftruncateSync = function(fd, len) {
        this.ftruncateBase(fd, len);
      };
      Volume2.prototype.ftruncate = function(fd, a6, b5) {
        var len = typeof a6 === "number" ? a6 : 0;
        var callback = validateCallback(typeof a6 === "number" ? b5 : a6);
        this.wrapAsync(this.ftruncateBase, [fd, len], callback);
      };
      Volume2.prototype.truncateBase = function(path2, len) {
        var fd = this.openSync(path2, "r+");
        try {
          this.ftruncateSync(fd, len);
        } finally {
          this.closeSync(fd);
        }
      };
      Volume2.prototype.truncateSync = function(id2, len) {
        if (isFd(id2)) return this.ftruncateSync(id2, len);
        this.truncateBase(id2, len);
      };
      Volume2.prototype.truncate = function(id2, a6, b5) {
        var len = typeof a6 === "number" ? a6 : 0;
        var callback = validateCallback(typeof a6 === "number" ? b5 : a6);
        if (isFd(id2)) return this.ftruncate(id2, len, callback);
        this.wrapAsync(this.truncateBase, [id2, len], callback);
      };
      Volume2.prototype.futimesBase = function(fd, atime, mtime) {
        var file = this.getFileByFdOrThrow(fd, "futimes");
        var node = file.node;
        node.atime = new Date(atime * 1e3);
        node.mtime = new Date(mtime * 1e3);
      };
      Volume2.prototype.futimesSync = function(fd, atime, mtime) {
        this.futimesBase(fd, toUnixTimestamp(atime), toUnixTimestamp(mtime));
      };
      Volume2.prototype.futimes = function(fd, atime, mtime, callback) {
        this.wrapAsync(this.futimesBase, [fd, toUnixTimestamp(atime), toUnixTimestamp(mtime)], callback);
      };
      Volume2.prototype.utimesBase = function(filename, atime, mtime) {
        var fd = this.openSync(filename, "r");
        try {
          this.futimesBase(fd, atime, mtime);
        } finally {
          this.closeSync(fd);
        }
      };
      Volume2.prototype.utimesSync = function(path2, atime, mtime) {
        this.utimesBase(pathToFilename(path2), toUnixTimestamp(atime), toUnixTimestamp(mtime));
      };
      Volume2.prototype.utimes = function(path2, atime, mtime, callback) {
        this.wrapAsync(this.utimesBase, [pathToFilename(path2), toUnixTimestamp(atime), toUnixTimestamp(mtime)], callback);
      };
      Volume2.prototype.mkdirBase = function(filename, modeNum) {
        var steps = filenameToSteps(filename);
        if (!steps.length) {
          throw createError(EEXIST, "mkdir", filename);
        }
        var dir = this.getLinkParentAsDirOrThrow(filename, "mkdir");
        var name2 = steps[steps.length - 1];
        if (dir.getChild(name2)) throw createError(EEXIST, "mkdir", filename);
        dir.createChild(name2, this.createNode(true, modeNum));
      };
      Volume2.prototype.mkdirpBase = function(filename, modeNum) {
        var fullPath = resolve2(filename);
        var fullPathSansSlash = fullPath.substring(1);
        var steps = !fullPathSansSlash ? [] : fullPathSansSlash.split(sep);
        var link3 = this.root;
        var created = false;
        for (var i6 = 0; i6 < steps.length; i6++) {
          var step = steps[i6];
          if (!link3.getNode().isDirectory()) throw createError(ENOTDIR, "mkdir", link3.getPath());
          var child = link3.getChild(step);
          if (child) {
            if (child.getNode().isDirectory()) link3 = child;
            else throw createError(ENOTDIR, "mkdir", child.getPath());
          } else {
            link3 = link3.createChild(step, this.createNode(true, modeNum));
            created = true;
          }
        }
        return created ? fullPath : void 0;
      };
      Volume2.prototype.mkdirSync = function(path2, options) {
        var opts = getMkdirOptions(options);
        var modeNum = modeToNumber(opts.mode, 511);
        var filename = pathToFilename(path2);
        if (opts.recursive) return this.mkdirpBase(filename, modeNum);
        this.mkdirBase(filename, modeNum);
      };
      Volume2.prototype.mkdir = function(path2, a6, b5) {
        var opts = getMkdirOptions(a6);
        var callback = validateCallback(typeof a6 === "function" ? a6 : b5);
        var modeNum = modeToNumber(opts.mode, 511);
        var filename = pathToFilename(path2);
        if (opts.recursive) this.wrapAsync(this.mkdirpBase, [filename, modeNum], callback);
        else this.wrapAsync(this.mkdirBase, [filename, modeNum], callback);
      };
      Volume2.prototype.mkdirpSync = function(path2, mode) {
        return this.mkdirSync(path2, {
          mode,
          recursive: true
        });
      };
      Volume2.prototype.mkdirp = function(path2, a6, b5) {
        var mode = typeof a6 === "function" ? void 0 : a6;
        var callback = validateCallback(typeof a6 === "function" ? a6 : b5);
        this.mkdir(path2, {
          mode,
          recursive: true
        }, callback);
      };
      Volume2.prototype.mkdtempBase = function(prefix, encoding, retry) {
        if (retry === void 0) {
          retry = 5;
        }
        var filename = prefix + this.genRndStr();
        try {
          this.mkdirBase(
            filename,
            511
            /* MODE.DIR */
          );
          return (0, encoding_1.strToEncoding)(filename, encoding);
        } catch (err) {
          if (err.code === EEXIST) {
            if (retry > 1) return this.mkdtempBase(prefix, encoding, retry - 1);
            else throw Error("Could not create temp dir.");
          } else throw err;
        }
      };
      Volume2.prototype.mkdtempSync = function(prefix, options) {
        var encoding = getDefaultOpts(options).encoding;
        if (!prefix || typeof prefix !== "string") throw new TypeError("filename prefix is required");
        nullCheck(prefix);
        return this.mkdtempBase(prefix, encoding);
      };
      Volume2.prototype.mkdtemp = function(prefix, a6, b5) {
        var _a2 = getDefaultOptsAndCb(a6, b5), encoding = _a2[0].encoding, callback = _a2[1];
        if (!prefix || typeof prefix !== "string") throw new TypeError("filename prefix is required");
        if (!nullCheck(prefix)) return;
        this.wrapAsync(this.mkdtempBase, [prefix, encoding], callback);
      };
      Volume2.prototype.rmdirBase = function(filename, options) {
        var opts = getRmdirOptions(options);
        var link3 = this.getLinkAsDirOrThrow(filename, "rmdir");
        if (link3.length && !opts.recursive) throw createError(ENOTEMPTY, "rmdir", filename);
        this.deleteLink(link3);
      };
      Volume2.prototype.rmdirSync = function(path2, options) {
        this.rmdirBase(pathToFilename(path2), options);
      };
      Volume2.prototype.rmdir = function(path2, a6, b5) {
        var opts = getRmdirOptions(a6);
        var callback = validateCallback(typeof a6 === "function" ? a6 : b5);
        this.wrapAsync(this.rmdirBase, [pathToFilename(path2), opts], callback);
      };
      Volume2.prototype.rmBase = function(filename, options) {
        if (options === void 0) {
          options = {};
        }
        var link3 = this.getResolvedLink(filename);
        if (!link3) {
          if (!options.force) throw createError(ENOENT, "stat", filename);
          return;
        }
        if (link3.getNode().isDirectory()) {
          if (!options.recursive) {
            throw createError(ERR_FS_EISDIR, "rm", filename);
          }
        }
        this.deleteLink(link3);
      };
      Volume2.prototype.rmSync = function(path2, options) {
        this.rmBase(pathToFilename(path2), options);
      };
      Volume2.prototype.rm = function(path2, a6, b5) {
        var _a2 = getRmOptsAndCb(a6, b5), opts = _a2[0], callback = _a2[1];
        this.wrapAsync(this.rmBase, [pathToFilename(path2), opts], callback);
      };
      Volume2.prototype.fchmodBase = function(fd, modeNum) {
        var file = this.getFileByFdOrThrow(fd, "fchmod");
        file.chmod(modeNum);
      };
      Volume2.prototype.fchmodSync = function(fd, mode) {
        this.fchmodBase(fd, modeToNumber(mode));
      };
      Volume2.prototype.fchmod = function(fd, mode, callback) {
        this.wrapAsync(this.fchmodBase, [fd, modeToNumber(mode)], callback);
      };
      Volume2.prototype.chmodBase = function(filename, modeNum) {
        var fd = this.openSync(filename, "r");
        try {
          this.fchmodBase(fd, modeNum);
        } finally {
          this.closeSync(fd);
        }
      };
      Volume2.prototype.chmodSync = function(path2, mode) {
        var modeNum = modeToNumber(mode);
        var filename = pathToFilename(path2);
        this.chmodBase(filename, modeNum);
      };
      Volume2.prototype.chmod = function(path2, mode, callback) {
        var modeNum = modeToNumber(mode);
        var filename = pathToFilename(path2);
        this.wrapAsync(this.chmodBase, [filename, modeNum], callback);
      };
      Volume2.prototype.lchmodBase = function(filename, modeNum) {
        var fd = this.openBase(filename, O_RDWR, 0, false);
        try {
          this.fchmodBase(fd, modeNum);
        } finally {
          this.closeSync(fd);
        }
      };
      Volume2.prototype.lchmodSync = function(path2, mode) {
        var modeNum = modeToNumber(mode);
        var filename = pathToFilename(path2);
        this.lchmodBase(filename, modeNum);
      };
      Volume2.prototype.lchmod = function(path2, mode, callback) {
        var modeNum = modeToNumber(mode);
        var filename = pathToFilename(path2);
        this.wrapAsync(this.lchmodBase, [filename, modeNum], callback);
      };
      Volume2.prototype.fchownBase = function(fd, uid, gid) {
        this.getFileByFdOrThrow(fd, "fchown").chown(uid, gid);
      };
      Volume2.prototype.fchownSync = function(fd, uid, gid) {
        validateUid(uid);
        validateGid(gid);
        this.fchownBase(fd, uid, gid);
      };
      Volume2.prototype.fchown = function(fd, uid, gid, callback) {
        validateUid(uid);
        validateGid(gid);
        this.wrapAsync(this.fchownBase, [fd, uid, gid], callback);
      };
      Volume2.prototype.chownBase = function(filename, uid, gid) {
        var link3 = this.getResolvedLinkOrThrow(filename, "chown");
        var node = link3.getNode();
        node.chown(uid, gid);
      };
      Volume2.prototype.chownSync = function(path2, uid, gid) {
        validateUid(uid);
        validateGid(gid);
        this.chownBase(pathToFilename(path2), uid, gid);
      };
      Volume2.prototype.chown = function(path2, uid, gid, callback) {
        validateUid(uid);
        validateGid(gid);
        this.wrapAsync(this.chownBase, [pathToFilename(path2), uid, gid], callback);
      };
      Volume2.prototype.lchownBase = function(filename, uid, gid) {
        this.getLinkOrThrow(filename, "lchown").getNode().chown(uid, gid);
      };
      Volume2.prototype.lchownSync = function(path2, uid, gid) {
        validateUid(uid);
        validateGid(gid);
        this.lchownBase(pathToFilename(path2), uid, gid);
      };
      Volume2.prototype.lchown = function(path2, uid, gid, callback) {
        validateUid(uid);
        validateGid(gid);
        this.wrapAsync(this.lchownBase, [pathToFilename(path2), uid, gid], callback);
      };
      Volume2.prototype.watchFile = function(path2, a6, b5) {
        var filename = pathToFilename(path2);
        var options = a6;
        var listener = b5;
        if (typeof options === "function") {
          listener = a6;
          options = null;
        }
        if (typeof listener !== "function") {
          throw Error('"watchFile()" requires a listener function');
        }
        var interval = 5007;
        var persistent = true;
        if (options && typeof options === "object") {
          if (typeof options.interval === "number") interval = options.interval;
          if (typeof options.persistent === "boolean") persistent = options.persistent;
        }
        var watcher = this.statWatchers[filename];
        if (!watcher) {
          watcher = new this.StatWatcher();
          watcher.start(filename, persistent, interval);
          this.statWatchers[filename] = watcher;
        }
        watcher.addListener("change", listener);
        return watcher;
      };
      Volume2.prototype.unwatchFile = function(path2, listener) {
        var filename = pathToFilename(path2);
        var watcher = this.statWatchers[filename];
        if (!watcher) return;
        if (typeof listener === "function") {
          watcher.removeListener("change", listener);
        } else {
          watcher.removeAllListeners("change");
        }
        if (watcher.listenerCount("change") === 0) {
          watcher.stop();
          delete this.statWatchers[filename];
        }
      };
      Volume2.prototype.createReadStream = function(path2, options) {
        return new this.ReadStream(path2, options);
      };
      Volume2.prototype.createWriteStream = function(path2, options) {
        return new this.WriteStream(path2, options);
      };
      Volume2.prototype.watch = function(path2, options, listener) {
        var filename = pathToFilename(path2);
        var givenOptions = options;
        if (typeof options === "function") {
          listener = options;
          givenOptions = null;
        }
        var _a2 = getDefaultOpts(givenOptions), persistent = _a2.persistent, recursive = _a2.recursive, encoding = _a2.encoding;
        if (persistent === void 0) persistent = true;
        if (recursive === void 0) recursive = false;
        var watcher = new this.FSWatcher();
        watcher.start(filename, persistent, recursive, encoding);
        if (listener) {
          watcher.addListener("change", listener);
        }
        return watcher;
      };
      Volume2.fd = 2147483647;
      return Volume2;
    })()
  );
  exports$44.Volume = Volume;
  function emitStop(self2) {
    self2.emit("stop");
  }
  var StatWatcher = (
    /** @class */
    (function(_super) {
      __extends(StatWatcher2, _super);
      function StatWatcher2(vol2) {
        var _this = _super.call(this) || this;
        _this.onInterval = function() {
          try {
            var stats = _this.vol.statSync(_this.filename);
            if (_this.hasChanged(stats)) {
              _this.emit("change", stats, _this.prev);
              _this.prev = stats;
            }
          } finally {
            _this.loop();
          }
        };
        _this.vol = vol2;
        return _this;
      }
      StatWatcher2.prototype.loop = function() {
        this.timeoutRef = this.setTimeout(this.onInterval, this.interval);
      };
      StatWatcher2.prototype.hasChanged = function(stats) {
        if (stats.mtimeMs > this.prev.mtimeMs) return true;
        if (stats.nlink !== this.prev.nlink) return true;
        return false;
      };
      StatWatcher2.prototype.start = function(path2, persistent, interval) {
        if (persistent === void 0) {
          persistent = true;
        }
        if (interval === void 0) {
          interval = 5007;
        }
        this.filename = pathToFilename(path2);
        this.setTimeout = persistent ? setTimeout.bind(typeof globalThis !== "undefined" ? globalThis : _global5) : setTimeoutUnref_1.default;
        this.interval = interval;
        this.prev = this.vol.statSync(this.filename);
        this.loop();
      };
      StatWatcher2.prototype.stop = function() {
        clearTimeout(this.timeoutRef);
        process_1.default.nextTick(emitStop, this);
      };
      return StatWatcher2;
    })(events_1.EventEmitter)
  );
  exports$44.StatWatcher = StatWatcher;
  var pool;
  function allocNewPool(poolSize) {
    pool = (0, buffer_1.bufferAllocUnsafe)(poolSize);
    pool.used = 0;
  }
  util.inherits(FsReadStream, stream_1.Readable);
  exports$44.ReadStream = FsReadStream;
  function FsReadStream(vol2, path2, options) {
    if (!(this instanceof FsReadStream)) return new FsReadStream(vol2, path2, options);
    this._vol = vol2;
    options = Object.assign({}, getOptions(options, {}));
    if (options.highWaterMark === void 0) options.highWaterMark = 64 * 1024;
    stream_1.Readable.call(this, options);
    this.path = pathToFilename(path2);
    this.fd = options.fd === void 0 ? null : options.fd;
    this.flags = options.flags === void 0 ? "r" : options.flags;
    this.mode = options.mode === void 0 ? 438 : options.mode;
    this.start = options.start;
    this.end = options.end;
    this.autoClose = options.autoClose === void 0 ? true : options.autoClose;
    this.pos = void 0;
    this.bytesRead = 0;
    if (this.start !== void 0) {
      if (typeof this.start !== "number") {
        throw new TypeError('"start" option must be a Number');
      }
      if (this.end === void 0) {
        this.end = Infinity;
      } else if (typeof this.end !== "number") {
        throw new TypeError('"end" option must be a Number');
      }
      if (this.start > this.end) {
        throw new Error('"start" option must be <= "end" option');
      }
      this.pos = this.start;
    }
    if (typeof this.fd !== "number") this.open();
    this.on("end", function() {
      if (this.autoClose) {
        if (this.destroy) this.destroy();
      }
    });
  }
  FsReadStream.prototype.open = function() {
    var self2 = this;
    this._vol.open(this.path, this.flags, this.mode, function(er, fd) {
      if (er) {
        if (self2.autoClose) {
          if (self2.destroy) self2.destroy();
        }
        self2.emit("error", er);
        return;
      }
      self2.fd = fd;
      self2.emit("open", fd);
      self2.read();
    });
  };
  FsReadStream.prototype._read = function(n6) {
    if (typeof this.fd !== "number") {
      return this.once("open", function() {
        this._read(n6);
      });
    }
    if (this.destroyed) return;
    if (!pool || pool.length - pool.used < kMinPoolSpace) {
      allocNewPool(this._readableState.highWaterMark);
    }
    var thisPool = pool;
    var toRead = Math.min(pool.length - pool.used, n6);
    var start = pool.used;
    if (this.pos !== void 0) toRead = Math.min(this.end - this.pos + 1, toRead);
    if (toRead <= 0) return this.push(null);
    var self2 = this;
    this._vol.read(this.fd, pool, pool.used, toRead, this.pos, onread);
    if (this.pos !== void 0) this.pos += toRead;
    pool.used += toRead;
    function onread(er, bytesRead) {
      if (er) {
        if (self2.autoClose && self2.destroy) {
          self2.destroy();
        }
        self2.emit("error", er);
      } else {
        var b5 = null;
        if (bytesRead > 0) {
          self2.bytesRead += bytesRead;
          b5 = thisPool.slice(start, start + bytesRead);
        }
        self2.push(b5);
      }
    }
  };
  FsReadStream.prototype._destroy = function(err, cb) {
    this.close(function(err2) {
      cb(err || err2);
    });
  };
  FsReadStream.prototype.close = function(cb) {
    var _this = this;
    var _a2;
    if (cb) this.once("close", cb);
    if (this.closed || typeof this.fd !== "number") {
      if (typeof this.fd !== "number") {
        this.once("open", closeOnOpen);
        return;
      }
      return process_1.default.nextTick(function() {
        return _this.emit("close");
      });
    }
    if (typeof ((_a2 = this._readableState) === null || _a2 === void 0 ? void 0 : _a2.closed) === "boolean") {
      this._readableState.closed = true;
    } else {
      this.closed = true;
    }
    this._vol.close(this.fd, function(er) {
      if (er) _this.emit("error", er);
      else _this.emit("close");
    });
    this.fd = null;
  };
  function closeOnOpen(fd) {
    this.close();
  }
  util.inherits(FsWriteStream, stream_1.Writable);
  exports$44.WriteStream = FsWriteStream;
  function FsWriteStream(vol2, path2, options) {
    if (!(this instanceof FsWriteStream)) return new FsWriteStream(vol2, path2, options);
    this._vol = vol2;
    options = Object.assign({}, getOptions(options, {}));
    stream_1.Writable.call(this, options);
    this.path = pathToFilename(path2);
    this.fd = options.fd === void 0 ? null : options.fd;
    this.flags = options.flags === void 0 ? "w" : options.flags;
    this.mode = options.mode === void 0 ? 438 : options.mode;
    this.start = options.start;
    this.autoClose = options.autoClose === void 0 ? true : !!options.autoClose;
    this.pos = void 0;
    this.bytesWritten = 0;
    if (this.start !== void 0) {
      if (typeof this.start !== "number") {
        throw new TypeError('"start" option must be a Number');
      }
      if (this.start < 0) {
        throw new Error('"start" must be >= zero');
      }
      this.pos = this.start;
    }
    if (options.encoding) this.setDefaultEncoding(options.encoding);
    if (typeof this.fd !== "number") this.open();
    this.once("finish", function() {
      if (this.autoClose) {
        this.close();
      }
    });
  }
  FsWriteStream.prototype.open = function() {
    this._vol.open(this.path, this.flags, this.mode, function(er, fd) {
      if (er) {
        if (this.autoClose && this.destroy) {
          this.destroy();
        }
        this.emit("error", er);
        return;
      }
      this.fd = fd;
      this.emit("open", fd);
    }.bind(this));
  };
  FsWriteStream.prototype._write = function(data, encoding, cb) {
    if (!(data instanceof buffer_1.Buffer || data instanceof Uint8Array)) return this.emit("error", new Error("Invalid data"));
    if (typeof this.fd !== "number") {
      return this.once("open", function() {
        this._write(data, encoding, cb);
      });
    }
    var self2 = this;
    this._vol.write(this.fd, data, 0, data.length, this.pos, function(er, bytes) {
      if (er) {
        if (self2.autoClose && self2.destroy) {
          self2.destroy();
        }
        return cb(er);
      }
      self2.bytesWritten += bytes;
      cb();
    });
    if (this.pos !== void 0) this.pos += data.length;
  };
  FsWriteStream.prototype._writev = function(data, cb) {
    if (typeof this.fd !== "number") {
      return this.once("open", function() {
        this._writev(data, cb);
      });
    }
    var self2 = this;
    var len = data.length;
    var chunks = new Array(len);
    var size = 0;
    for (var i6 = 0; i6 < len; i6++) {
      var chunk = data[i6].chunk;
      chunks[i6] = chunk;
      size += chunk.length;
    }
    var buf = buffer_1.Buffer.concat(chunks);
    this._vol.write(this.fd, buf, 0, buf.length, this.pos, function(er, bytes) {
      if (er) {
        if (self2.destroy) self2.destroy();
        return cb(er);
      }
      self2.bytesWritten += bytes;
      cb();
    });
    if (this.pos !== void 0) this.pos += size;
  };
  FsWriteStream.prototype.close = function(cb) {
    var _this = this;
    var _a2;
    if (cb) this.once("close", cb);
    if (this.closed || typeof this.fd !== "number") {
      if (typeof this.fd !== "number") {
        this.once("open", closeOnOpen);
        return;
      }
      return process_1.default.nextTick(function() {
        return _this.emit("close");
      });
    }
    if (typeof ((_a2 = this._writableState) === null || _a2 === void 0 ? void 0 : _a2.closed) === "boolean") {
      this._writableState.closed = true;
    } else {
      this.closed = true;
    }
    this._vol.close(this.fd, function(er) {
      if (er) _this.emit("error", er);
      else _this.emit("close");
    });
    this.fd = null;
  };
  FsWriteStream.prototype._destroy = FsReadStream.prototype._destroy;
  FsWriteStream.prototype.destroySoon = FsWriteStream.prototype.end;
  var FSWatcher = (
    /** @class */
    (function(_super) {
      __extends(FSWatcher2, _super);
      function FSWatcher2(vol2) {
        var _this = _super.call(this) || this;
        _this._filename = "";
        _this._filenameEncoded = "";
        _this._recursive = false;
        _this._encoding = encoding_1.ENCODING_UTF8;
        _this._listenerRemovers = /* @__PURE__ */ new Map();
        _this._onParentChild = function(link3) {
          if (link3.getName() === _this._getName()) {
            _this._emit("rename");
          }
        };
        _this._emit = function(type) {
          _this.emit("change", type, _this._filenameEncoded);
        };
        _this._persist = function() {
          _this._timer = setTimeout(_this._persist, 1e6);
        };
        _this._vol = vol2;
        return _this;
      }
      FSWatcher2.prototype._getName = function() {
        return this._steps[this._steps.length - 1];
      };
      FSWatcher2.prototype.start = function(path2, persistent, recursive, encoding) {
        var _this = this;
        if (persistent === void 0) {
          persistent = true;
        }
        if (recursive === void 0) {
          recursive = false;
        }
        if (encoding === void 0) {
          encoding = encoding_1.ENCODING_UTF8;
        }
        this._filename = pathToFilename(path2);
        this._steps = filenameToSteps(this._filename);
        this._filenameEncoded = (0, encoding_1.strToEncoding)(this._filename);
        this._recursive = recursive;
        this._encoding = encoding;
        try {
          this._link = this._vol.getLinkOrThrow(this._filename, "FSWatcher");
        } catch (err) {
          var error2 = new Error("watch ".concat(this._filename, " ").concat(err.code));
          error2.code = err.code;
          error2.errno = err.code;
          throw error2;
        }
        var watchLinkNodeChanged = function(link3) {
          var _a2;
          var filepath = link3.getPath();
          var node = link3.getNode();
          var onNodeChange = function() {
            var filename = relative(_this._filename, filepath);
            if (!filename) {
              filename = _this._getName();
            }
            return _this.emit("change", "change", filename);
          };
          node.on("change", onNodeChange);
          var removers = (_a2 = _this._listenerRemovers.get(node.ino)) !== null && _a2 !== void 0 ? _a2 : [];
          removers.push(function() {
            return node.removeListener("change", onNodeChange);
          });
          _this._listenerRemovers.set(node.ino, removers);
        };
        var watchLinkChildrenChanged = function(link3) {
          var _a2;
          var node = link3.getNode();
          var onLinkChildAdd = function(l6) {
            _this.emit("change", "rename", relative(_this._filename, l6.getPath()));
            setTimeout(function() {
              watchLinkNodeChanged(l6);
              watchLinkChildrenChanged(l6);
            });
          };
          var onLinkChildDelete = function(l6) {
            var removeLinkNodeListeners = function(curLink) {
              var ino = curLink.getNode().ino;
              var removers2 = _this._listenerRemovers.get(ino);
              if (removers2) {
                removers2.forEach(function(r6) {
                  return r6();
                });
                _this._listenerRemovers.delete(ino);
              }
              Object.values(curLink.children).forEach(function(childLink) {
                if (childLink) {
                  removeLinkNodeListeners(childLink);
                }
              });
            };
            removeLinkNodeListeners(l6);
            _this.emit("change", "rename", relative(_this._filename, l6.getPath()));
          };
          Object.entries(link3.children).forEach(function(_a3) {
            var name2 = _a3[0], childLink = _a3[1];
            if (childLink && name2 !== "." && name2 !== "..") {
              watchLinkNodeChanged(childLink);
            }
          });
          link3.on("child:add", onLinkChildAdd);
          link3.on("child:delete", onLinkChildDelete);
          var removers = (_a2 = _this._listenerRemovers.get(node.ino)) !== null && _a2 !== void 0 ? _a2 : [];
          removers.push(function() {
            link3.removeListener("child:add", onLinkChildAdd);
            link3.removeListener("child:delete", onLinkChildDelete);
          });
          if (recursive) {
            Object.entries(link3.children).forEach(function(_a3) {
              var name2 = _a3[0], childLink = _a3[1];
              if (childLink && name2 !== "." && name2 !== "..") {
                watchLinkChildrenChanged(childLink);
              }
            });
          }
        };
        watchLinkNodeChanged(this._link);
        watchLinkChildrenChanged(this._link);
        var parent = this._link.parent;
        if (parent) {
          parent.setMaxListeners(parent.getMaxListeners() + 1);
          parent.on("child:delete", this._onParentChild);
        }
        if (persistent) this._persist();
      };
      FSWatcher2.prototype.close = function() {
        clearTimeout(this._timer);
        this._listenerRemovers.forEach(function(removers) {
          removers.forEach(function(r6) {
            return r6();
          });
        });
        this._listenerRemovers.clear();
        var parent = this._link.parent;
        if (parent) {
          parent.removeListener("child:delete", this._onParentChild);
        }
      };
      return FSWatcher2;
    })(events_1.EventEmitter)
  );
  exports$44.FSWatcher = FSWatcher;
  return exports$44;
}
function dew$16() {
  if (_dewExec$16) return exports$34;
  _dewExec$16 = true;
  Object.defineProperty(exports$34, "__esModule", {
    value: true
  });
  exports$34.fsSyncMethods = exports$34.fsProps = exports$34.fsAsyncMethods = void 0;
  exports$34.fsProps = ["constants", "F_OK", "R_OK", "W_OK", "X_OK", "Stats"];
  exports$34.fsSyncMethods = ["renameSync", "ftruncateSync", "truncateSync", "chownSync", "fchownSync", "lchownSync", "chmodSync", "fchmodSync", "lchmodSync", "statSync", "lstatSync", "fstatSync", "linkSync", "symlinkSync", "readlinkSync", "realpathSync", "unlinkSync", "rmdirSync", "mkdirSync", "mkdirpSync", "readdirSync", "closeSync", "openSync", "utimesSync", "futimesSync", "fsyncSync", "writeSync", "readSync", "readFileSync", "writeFileSync", "appendFileSync", "existsSync", "accessSync", "fdatasyncSync", "mkdtempSync", "copyFileSync", "rmSync", "createReadStream", "createWriteStream"];
  exports$34.fsAsyncMethods = ["rename", "ftruncate", "truncate", "chown", "fchown", "lchown", "chmod", "fchmod", "lchmod", "stat", "lstat", "fstat", "link", "symlink", "readlink", "realpath", "unlink", "rmdir", "mkdir", "mkdirp", "readdir", "close", "open", "utimes", "futimes", "fsync", "write", "read", "readFile", "writeFile", "appendFile", "exists", "access", "fdatasync", "mkdtemp", "copyFile", "rm", "watchFile", "unwatchFile", "watch"];
  return exports$34;
}
function dew10() {
  if (_dewExec10) return exports$26;
  _dewExec10 = true;
  var __assign = exports$26 && exports$26.__assign || function() {
    __assign = Object.assign || function(t6) {
      for (var s6, i6 = 1, n6 = arguments.length; i6 < n6; i6++) {
        s6 = arguments[i6];
        for (var p6 in s6) if (Object.prototype.hasOwnProperty.call(s6, p6)) t6[p6] = s6[p6];
      }
      return t6;
    };
    return __assign.apply(this, arguments);
  };
  Object.defineProperty(exports$26, "__esModule", {
    value: true
  });
  exports$26.fs = exports$26.createFsFromVolume = exports$26.vol = exports$26.Volume = void 0;
  var Stats_1 = dew$d3();
  var Dirent_1 = dew$93();
  var volume_1 = dew$25();
  var _a = dew$16(), fsSyncMethods = _a.fsSyncMethods, fsAsyncMethods = _a.fsAsyncMethods;
  var constants_1 = dew$f3();
  var F_OK2 = constants_1.constants.F_OK, R_OK2 = constants_1.constants.R_OK, W_OK2 = constants_1.constants.W_OK, X_OK2 = constants_1.constants.X_OK;
  exports$26.Volume = volume_1.Volume;
  exports$26.vol = new volume_1.Volume();
  function createFsFromVolume2(vol2) {
    var fs2 = {
      F_OK: F_OK2,
      R_OK: R_OK2,
      W_OK: W_OK2,
      X_OK: X_OK2,
      constants: constants_1.constants,
      Stats: Stats_1.default,
      Dirent: Dirent_1.default
    };
    for (var _i = 0, fsSyncMethods_1 = fsSyncMethods; _i < fsSyncMethods_1.length; _i++) {
      var method = fsSyncMethods_1[_i];
      if (typeof vol2[method] === "function") fs2[method] = vol2[method].bind(vol2);
    }
    for (var _a2 = 0, fsAsyncMethods_1 = fsAsyncMethods; _a2 < fsAsyncMethods_1.length; _a2++) {
      var method = fsAsyncMethods_1[_a2];
      if (typeof vol2[method] === "function") fs2[method] = vol2[method].bind(vol2);
    }
    fs2.StatWatcher = vol2.StatWatcher;
    fs2.FSWatcher = vol2.FSWatcher;
    fs2.WriteStream = vol2.WriteStream;
    fs2.ReadStream = vol2.ReadStream;
    fs2.promises = vol2.promises;
    fs2._toUnixTimestamp = volume_1.toUnixTimestamp;
    return fs2;
  }
  exports$26.createFsFromVolume = createFsFromVolume2;
  exports$26.fs = createFsFromVolume2(exports$26.vol);
  exports$26 = __assign(__assign({}, exports$26), exports$26.fs);
  exports$26.semantic = true;
  return exports$26;
}
function unimplemented3(name2) {
  throw new Error(`Node.js fs ${name2} is not supported by JSPM core in the browser`);
}
function watchStdo(path2, fd, listener) {
  let oldSize = 0;
  const decoder = new TextDecoder();
  vol.watch(path2, "utf8", () => {
    const { size } = vol.fstatSync(fd);
    const buf = Buffer2.alloc(size - oldSize);
    vol.readSync(fd, buf, 0, buf.length, oldSize);
    oldSize = size;
    listener(decoder.decode(buf, { stream: true }));
  });
}
function handleFsUrl(url, isSync) {
  if (url.protocol === "file:")
    return fileURLToPath2(url);
  if (url.protocol === "https:" || url.protocol === "http:") {
    const path2 = "\\\\url\\" + url.href.replaceAll(/\//g, "\\\\");
    if (existsSync(path2))
      return path2;
    if (isSync)
      throw new Error(`Cannot sync request URL ${url} via FS. JSPM FS support for network URLs requires using async FS methods or priming the MemFS cache first with an async request before a sync request.`);
    return (async () => {
      const res = await fetch(url);
      if (!res.ok)
        throw new Error(`Unable to fetch ${url.href}, ${res.status}`);
      const buf = await res.arrayBuffer();
      writeFileSync(path2, Buffer2.from(buf));
      return path2;
    })();
  }
  throw new Error("URL " + url + " not supported in JSPM FS implementation.");
}
function wrapFsSync(fn) {
  return function(path2, ...args) {
    if (path2 instanceof URL)
      return fn(handleFsUrl(path2, true), ...args);
    return fn(path2, ...args);
  };
}
function wrapFsPromise(fn) {
  return async function(path2, ...args) {
    if (path2 instanceof URL)
      return fn(await handleFsUrl(path2), ...args);
    return fn(path2, ...args);
  };
}
function wrapFsCallback(fn) {
  return function(path2, ...args) {
    const cb = args[args.length - 1];
    if (path2 instanceof URL && typeof cb === "function") {
      handleFsUrl(path2).then((path3) => {
        fn(path3, ...args);
      }, cb);
    } else {
      fn(path2, ...args);
    }
  };
}
var exports$h2, _dewExec$f3, exports$g3, _dewExec$e3, exports$f3, _dewExec$d3, exports$e3, _dewExec$c3, exports$d3, _dewExec$b3, _global$3, exports$c3, _dewExec$a3, exports$b3, _dewExec$93, exports$a3, _dewExec$83, _global$22, exports$93, _dewExec$74, exports$84, _dewExec$64, exports$74, _dewExec$54, _global$12, exports$64, _dewExec$44, exports$54, _dewExec$34, exports$44, _dewExec$25, _global5, exports$34, _dewExec$16, exports$26, _dewExec10, exports$19, exports11, vol, createFsFromVolume, fs, appendFile, appendFileSync, access, accessSync, chown, chownSync, chmod, chmodSync, close, closeSync, copyFile, copyFileSync, cp, cpSync, createReadStream, createWriteStream, exists, existsSync, fchown, fchownSync, fchmod, fchmodSync, fdatasync, fdatasyncSync, fstat, fstatSync, fsync, fsyncSync, ftruncate, ftruncateSync, futimes, futimesSync, lchown, lchownSync, lchmod, lchmodSync, link, linkSync, lstat, lstatSync, mkdir, mkdirSync, mkdtemp, mkdtempSync, open, openSync, opendir, opendirSync, readdir, readdirSync, read, readSync, readv, readvSync, readFile, readFileSync, readlink, readlinkSync, realpath, realpathSync, rename, renameSync, rm, rmSync, rmdir, rmdirSync, stat, statSync, symlink, symlinkSync, truncate, truncateSync, unwatchFile, unlink, unlinkSync, utimes, utimesSync, watch, watchFile, writeFile, writeFileSync, write, writeSync, writev, writevSync, Dir, Dirent, Stats, ReadStream, WriteStream, FileReadStream, FileWriteStream, _toUnixTimestamp, F_OK, R_OK, W_OK, X_OK, constants, promises;
var init_fs = __esm({
  "node_modules/@jspm/core/nodelibs/browser/fs.js"() {
    init_dirname();
    init_buffer2();
    init_process2();
    init_chunk_DtuTasat();
    init_chunk_CjPlbOtt();
    init_chunk_CbQqNoLO();
    init_chunk_D3uu3VYh();
    init_chunk_DHWh_hmB();
    init_chunk_b0rmRow7();
    init_chunk_DEMDiNwt();
    init_chunk_DtDiafJB();
    init_chunk_tHuMsdT0();
    init_chunk_B6_G_Ftj();
    init_buffer();
    init_url();
    init_chunk_B738Er4n();
    init_punycode();
    init_chunk_DtcTpLWz();
    init_chunk_BlJi4mNy();
    exports$h2 = {};
    _dewExec$f3 = false;
    exports$g3 = {};
    _dewExec$e3 = false;
    exports$f3 = {};
    _dewExec$d3 = false;
    exports$e3 = {};
    _dewExec$c3 = false;
    exports$d3 = {};
    _dewExec$b3 = false;
    _global$3 = typeof globalThis !== "undefined" ? globalThis : typeof self !== "undefined" ? self : global;
    exports$c3 = {};
    _dewExec$a3 = false;
    exports$b3 = {};
    _dewExec$93 = false;
    exports$22._makeLong;
    exports$22.basename;
    exports$22.delimiter;
    exports$22.dirname;
    exports$22.extname;
    exports$22.format;
    exports$22.isAbsolute;
    exports$22.join;
    exports$22.normalize;
    exports$22.parse;
    exports$22.posix;
    exports$22.relative;
    exports$22.resolve;
    exports$22.sep;
    exports$22.win32;
    exports$a3 = {};
    _dewExec$83 = false;
    _global$22 = typeof globalThis !== "undefined" ? globalThis : typeof self !== "undefined" ? self : global;
    exports$93 = {};
    _dewExec$74 = false;
    exports$84 = {};
    _dewExec$64 = false;
    exports$74 = {};
    _dewExec$54 = false;
    _global$12 = typeof globalThis !== "undefined" ? globalThis : typeof self !== "undefined" ? self : global;
    exports$64 = {};
    _dewExec$44 = false;
    exports$54 = {};
    _dewExec$34 = false;
    exports$44 = {};
    _dewExec$25 = false;
    _global5 = typeof globalThis !== "undefined" ? globalThis : typeof self !== "undefined" ? self : global;
    exports$34 = {};
    _dewExec$16 = false;
    exports$26 = {};
    _dewExec10 = false;
    exports$19 = dew10();
    exports$19["__esModule"];
    exports$19["fs"];
    exports$19["createFsFromVolume"];
    exports$19["vol"];
    exports$19["Volume"];
    exports$19["semantic"];
    exports11 = dew$25();
    exports11["__esModule"];
    exports11["FSWatcher"];
    exports11["StatWatcher"];
    exports11["Volume"];
    exports11["toUnixTimestamp"];
    exports11["bufferToEncoding"];
    exports11["dataToBuffer"];
    exports11["dataToStr"];
    exports11["pathToSteps"];
    exports11["filenameToSteps"];
    exports11["pathToFilename"];
    exports11["flagsToNumber"];
    exports11["FLAGS"];
    exports11["ReadStream"];
    exports11["WriteStream"];
    ({ vol, createFsFromVolume } = exports$19);
    vol.fromNestedJSON({
      "/dev": { stdin: "", stdout: "", stderr: "" },
      "/usr/bin": {},
      "/home": {},
      "/tmp": {}
    });
    vol.releasedFds = [2, 1, 0];
    vol.openSync("/dev/stdin", "w");
    vol.openSync("/dev/stdout", "r");
    vol.openSync("/dev/stderr", "r");
    watchStdo("/dev/stdout", 1, console.log);
    watchStdo("/dev/stderr", 2, console.error);
    fs = createFsFromVolume(vol);
    fs.opendir = () => unimplemented3("opendir");
    fs.opendirSync = () => unimplemented3("opendirSync");
    fs.promises.opendir = () => unimplemented3("promises.opendir");
    fs.cp = () => unimplemented3("cp");
    fs.cpSync = () => unimplemented3("cpSync");
    fs.promises.cp = () => unimplemented3("promises.cp");
    fs.readv = () => unimplemented3("readv");
    fs.readvSync = () => unimplemented3("readvSync");
    fs.rm = () => unimplemented3("rm");
    fs.rmSync = () => unimplemented3("rmSync");
    fs.promises.rm = () => unimplemented3("promises.rm");
    fs.Dir = () => unimplemented3("Dir");
    fs.promises.watch = () => unimplemented3("promises.watch");
    fs.FileReadStream = fs.ReadStream;
    fs.FileWriteStream = fs.WriteStream;
    fs.promises.readFile = wrapFsPromise(fs.promises.readFile);
    fs.readFile = wrapFsCallback(fs.readFile);
    fs.readFileSync = wrapFsSync(fs.readFileSync);
    ({
      appendFile,
      appendFileSync,
      access,
      accessSync,
      chown,
      chownSync,
      chmod,
      chmodSync,
      close,
      closeSync,
      copyFile,
      copyFileSync,
      cp,
      cpSync,
      createReadStream,
      createWriteStream,
      exists,
      existsSync,
      fchown,
      fchownSync,
      fchmod,
      fchmodSync,
      fdatasync,
      fdatasyncSync,
      fstat,
      fstatSync,
      fsync,
      fsyncSync,
      ftruncate,
      ftruncateSync,
      futimes,
      futimesSync,
      lchown,
      lchownSync,
      lchmod,
      lchmodSync,
      link,
      linkSync,
      lstat,
      lstatSync,
      mkdir,
      mkdirSync,
      mkdtemp,
      mkdtempSync,
      open,
      openSync,
      opendir,
      opendirSync,
      readdir,
      readdirSync,
      read,
      readSync,
      readv,
      readvSync,
      readFile,
      readFileSync,
      readlink,
      readlinkSync,
      realpath,
      realpathSync,
      rename,
      renameSync,
      rm,
      rmSync,
      rmdir,
      rmdirSync,
      stat,
      statSync,
      symlink,
      symlinkSync,
      truncate,
      truncateSync,
      unwatchFile,
      unlink,
      unlinkSync,
      utimes,
      utimesSync,
      watch,
      watchFile,
      writeFile,
      writeFileSync,
      write,
      writeSync,
      writev,
      writevSync,
      Dir,
      Dirent,
      Stats,
      ReadStream,
      WriteStream,
      FileReadStream,
      FileWriteStream,
      _toUnixTimestamp,
      constants: { F_OK, R_OK, W_OK, X_OK },
      constants,
      promises
    } = fs);
  }
});

// node_modules/@jspm/core/nodelibs/browser/fs/promises.js
var promises_exports = {};
__export(promises_exports, {
  access: () => access2,
  appendFile: () => appendFile2,
  chmod: () => chmod2,
  chown: () => chown2,
  copyFile: () => copyFile2,
  cp: () => cp2,
  default: () => promises,
  lchmod: () => lchmod2,
  lchown: () => lchown2,
  link: () => link2,
  lstat: () => lstat2,
  mkdir: () => mkdir2,
  mkdtemp: () => mkdtemp2,
  open: () => open2,
  opendir: () => opendir2,
  readFile: () => readFile2,
  readdir: () => readdir2,
  readlink: () => readlink2,
  realpath: () => realpath2,
  rename: () => rename2,
  rm: () => rm2,
  rmdir: () => rmdir2,
  stat: () => stat2,
  symlink: () => symlink2,
  truncate: () => truncate2,
  unlink: () => unlink2,
  utimes: () => utimes2,
  watch: () => watch2,
  writeFile: () => writeFile2
});
var access2, copyFile2, cp2, open2, opendir2, rename2, truncate2, rm2, rmdir2, mkdir2, readdir2, readlink2, symlink2, lstat2, stat2, link2, unlink2, chmod2, lchmod2, lchown2, chown2, utimes2, realpath2, mkdtemp2, writeFile2, appendFile2, readFile2, watch2;
var init_promises = __esm({
  "node_modules/@jspm/core/nodelibs/browser/fs/promises.js"() {
    init_dirname();
    init_buffer2();
    init_process2();
    init_fs();
    init_chunk_DtuTasat();
    init_chunk_CjPlbOtt();
    init_chunk_D3uu3VYh();
    init_chunk_CbQqNoLO();
    init_chunk_DHWh_hmB();
    init_chunk_b0rmRow7();
    init_chunk_DEMDiNwt();
    init_chunk_DtDiafJB();
    init_chunk_tHuMsdT0();
    init_chunk_B6_G_Ftj();
    init_chunk_B738Er4n();
    init_buffer();
    init_url();
    init_punycode();
    init_chunk_DtcTpLWz();
    init_chunk_BlJi4mNy();
    ({
      access: access2,
      copyFile: copyFile2,
      cp: cp2,
      open: open2,
      opendir: opendir2,
      rename: rename2,
      truncate: truncate2,
      rm: rm2,
      rmdir: rmdir2,
      mkdir: mkdir2,
      readdir: readdir2,
      readlink: readlink2,
      symlink: symlink2,
      lstat: lstat2,
      stat: stat2,
      link: link2,
      unlink: unlink2,
      chmod: chmod2,
      lchmod: lchmod2,
      lchown: lchown2,
      chown: chown2,
      utimes: utimes2,
      realpath: realpath2,
      mkdtemp: mkdtemp2,
      writeFile: writeFile2,
      appendFile: appendFile2,
      readFile: readFile2,
      watch: watch2
    } = promises);
  }
});

// node_modules/@bsull/augurs-prophet-wasmstan/prophet-wasmstan.js
init_dirname();
init_buffer2();
init_process2();

// node_modules/@bytecodealliance/preview2-shim/lib/browser/cli.js
init_dirname();
init_buffer2();
init_process2();

// node_modules/@bytecodealliance/preview2-shim/lib/browser/filesystem.js
init_dirname();
init_buffer2();
init_process2();

// node_modules/@bytecodealliance/preview2-shim/lib/browser/io.js
init_dirname();
init_buffer2();
init_process2();
var id = 0;
var symbolDispose = Symbol.dispose || /* @__PURE__ */ Symbol.for("dispose");
var IoError = class Error2 {
  constructor(msg) {
    this.msg = msg;
  }
  toDebugString() {
    return this.msg;
  }
};
var InputStream = class {
  /**
   * @param {InputStreamHandler} handler
   */
  constructor(handler) {
    if (!handler)
      console.trace("no handler");
    this.id = ++id;
    this.handler = handler;
  }
  read(len) {
    if (this.handler.read)
      return this.handler.read(len);
    return this.handler.blockingRead.call(this, len);
  }
  blockingRead(len) {
    return this.handler.blockingRead.call(this, len);
  }
  skip(len) {
    if (this.handler.skip)
      return this.handler.skip.call(this, len);
    if (this.handler.read) {
      const bytes = this.handler.read.call(this, len);
      return BigInt(bytes.byteLength);
    }
    return this.blockingSkip.call(this, len);
  }
  blockingSkip(len) {
    if (this.handler.blockingSkip)
      return this.handler.blockingSkip.call(this, len);
    const bytes = this.handler.blockingRead.call(this, len);
    return BigInt(bytes.byteLength);
  }
  subscribe() {
    console.log(`[streams] Subscribe to input stream ${this.id}`);
  }
  [symbolDispose]() {
    if (this.handler.drop)
      this.handler.drop.call(this);
  }
};
var OutputStream = class {
  /**
   * @param {OutputStreamHandler} handler
   */
  constructor(handler) {
    if (!handler)
      console.trace("no handler");
    this.id = ++id;
    this.open = true;
    this.handler = handler;
  }
  checkWrite(len) {
    if (!this.open)
      return 0n;
    if (this.handler.checkWrite)
      return this.handler.checkWrite.call(this, len);
    return 1000000n;
  }
  write(buf) {
    this.handler.write.call(this, buf);
  }
  blockingWriteAndFlush(buf) {
    this.handler.write.call(this, buf);
  }
  flush() {
    if (this.handler.flush)
      this.handler.flush.call(this);
  }
  blockingFlush() {
    this.open = true;
  }
  writeZeroes(len) {
    this.write.call(this, new Uint8Array(Number(len)));
  }
  blockingWriteZeroes(len) {
    this.blockingWrite.call(this, new Uint8Array(Number(len)));
  }
  blockingWriteZeroesAndFlush(len) {
    this.blockingWriteAndFlush.call(this, new Uint8Array(Number(len)));
  }
  splice(src, len) {
    const spliceLen = Math.min(len, this.checkWrite.call(this));
    const bytes = src.read(spliceLen);
    this.write.call(this, bytes);
    return bytes.byteLength;
  }
  blockingSplice(_src, _len) {
    console.log(`[streams] Blocking splice ${this.id}`);
  }
  forward(_src) {
    console.log(`[streams] Forward ${this.id}`);
  }
  subscribe() {
    console.log(`[streams] Subscribe to output stream ${this.id}`);
  }
  [symbolDispose]() {
  }
};
var error = { Error: IoError };
var streams = { InputStream, OutputStream };

// node_modules/@bytecodealliance/preview2-shim/lib/browser/filesystem.js
var { InputStream: InputStream2, OutputStream: OutputStream2 } = streams;
var _cwd = "/";
var _fileData = { dir: {} };
var timeZero = {
  seconds: BigInt(0),
  nanoseconds: 0
};
function getChildEntry(parentEntry, subpath, openFlags) {
  if (subpath === "." && _rootPreopen && descriptorGetEntry(_rootPreopen[0]) === parentEntry) {
    subpath = _cwd;
    if (subpath.startsWith("/") && subpath !== "/")
      subpath = subpath.slice(1);
  }
  let entry = parentEntry;
  let segmentIdx;
  do {
    if (!entry || !entry.dir) throw "not-directory";
    segmentIdx = subpath.indexOf("/");
    const segment = segmentIdx === -1 ? subpath : subpath.slice(0, segmentIdx);
    if (segment === "..") throw "no-entry";
    if (segment === "." || segment === "") ;
    else if (!entry.dir[segment] && openFlags.create)
      entry = entry.dir[segment] = openFlags.directory ? { dir: {} } : { source: new Uint8Array([]) };
    else
      entry = entry.dir[segment];
    subpath = subpath.slice(segmentIdx + 1);
  } while (segmentIdx !== -1);
  if (!entry) throw "no-entry";
  return entry;
}
function getSource(fileEntry) {
  if (typeof fileEntry.source === "string") {
    fileEntry.source = new TextEncoder().encode(fileEntry.source);
  }
  return fileEntry.source;
}
var DirectoryEntryStream = class {
  constructor(entries) {
    this.idx = 0;
    this.entries = entries;
  }
  readDirectoryEntry() {
    if (this.idx === this.entries.length)
      return null;
    const [name2, entry] = this.entries[this.idx];
    this.idx += 1;
    return {
      name: name2,
      type: entry.dir ? "directory" : "regular-file"
    };
  }
};
var Descriptor = class _Descriptor {
  #stream;
  #entry;
  #mtime = 0;
  _getEntry(descriptor) {
    return descriptor.#entry;
  }
  constructor(entry, isStream) {
    if (isStream)
      this.#stream = entry;
    else
      this.#entry = entry;
  }
  readViaStream(_offset) {
    const source = getSource(this.#entry);
    let offset = Number(_offset);
    return new InputStream2({
      blockingRead(len) {
        if (offset === source.byteLength)
          throw { tag: "closed" };
        const bytes = source.slice(offset, offset + Number(len));
        offset += bytes.byteLength;
        return bytes;
      }
    });
  }
  writeViaStream(_offset) {
    const entry = this.#entry;
    let offset = Number(_offset);
    return new OutputStream2({
      write(buf) {
        const newSource = new Uint8Array(buf.byteLength + entry.source.byteLength);
        newSource.set(entry.source, 0);
        newSource.set(buf, offset);
        offset += buf.byteLength;
        entry.source = newSource;
        return buf.byteLength;
      }
    });
  }
  appendViaStream() {
    console.log(`[filesystem] APPEND STREAM`);
  }
  advise(descriptor, offset, length, advice) {
    console.log(`[filesystem] ADVISE`, descriptor, offset, length, advice);
  }
  syncData() {
    console.log(`[filesystem] SYNC DATA`);
  }
  getFlags() {
    console.log(`[filesystem] FLAGS FOR`);
  }
  getType() {
    if (this.#stream) return "fifo";
    if (this.#entry.dir) return "directory";
    if (this.#entry.source) return "regular-file";
    return "unknown";
  }
  setSize(size) {
    console.log(`[filesystem] SET SIZE`, size);
  }
  setTimes(dataAccessTimestamp, dataModificationTimestamp) {
    console.log(`[filesystem] SET TIMES`, dataAccessTimestamp, dataModificationTimestamp);
  }
  read(length, offset) {
    const source = getSource(this.#entry);
    return [source.slice(offset, offset + length), offset + length >= source.byteLength];
  }
  write(buffer2, offset) {
    if (offset !== 0) throw "invalid-seek";
    this.#entry.source = buffer2;
    return buffer2.byteLength;
  }
  readDirectory() {
    if (!this.#entry?.dir)
      throw "bad-descriptor";
    return new DirectoryEntryStream(Object.entries(this.#entry.dir).sort(([a6], [b5]) => a6 > b5 ? 1 : -1));
  }
  sync() {
    console.log(`[filesystem] SYNC`);
  }
  createDirectoryAt(path2) {
    const entry = getChildEntry(this.#entry, path2, { create: true, directory: true });
    if (entry.source) throw "exist";
  }
  stat() {
    let type = "unknown", size = BigInt(0);
    if (this.#entry.source) {
      type = "regular-file";
      const source = getSource(this.#entry);
      size = BigInt(source.byteLength);
    } else if (this.#entry.dir) {
      type = "directory";
    }
    return {
      type,
      linkCount: BigInt(0),
      size,
      dataAccessTimestamp: timeZero,
      dataModificationTimestamp: timeZero,
      statusChangeTimestamp: timeZero
    };
  }
  statAt(_pathFlags, path2) {
    const entry = getChildEntry(this.#entry, path2, { create: false, directory: false });
    let type = "unknown", size = BigInt(0);
    if (entry.source) {
      type = "regular-file";
      const source = getSource(entry);
      size = BigInt(source.byteLength);
    } else if (entry.dir) {
      type = "directory";
    }
    return {
      type,
      linkCount: BigInt(0),
      size,
      dataAccessTimestamp: timeZero,
      dataModificationTimestamp: timeZero,
      statusChangeTimestamp: timeZero
    };
  }
  setTimesAt() {
    console.log(`[filesystem] SET TIMES AT`);
  }
  linkAt() {
    console.log(`[filesystem] LINK AT`);
  }
  openAt(_pathFlags, path2, openFlags, _descriptorFlags, _modes) {
    const childEntry = getChildEntry(this.#entry, path2, openFlags);
    return new _Descriptor(childEntry);
  }
  readlinkAt() {
    console.log(`[filesystem] READLINK AT`);
  }
  removeDirectoryAt() {
    console.log(`[filesystem] REMOVE DIR AT`);
  }
  renameAt() {
    console.log(`[filesystem] RENAME AT`);
  }
  symlinkAt() {
    console.log(`[filesystem] SYMLINK AT`);
  }
  unlinkFileAt() {
    console.log(`[filesystem] UNLINK FILE AT`);
  }
  isSameObject(other) {
    return other === this;
  }
  metadataHash() {
    let upper = BigInt(0);
    upper += BigInt(this.#mtime);
    return { upper, lower: BigInt(0) };
  }
  metadataHashAt(_pathFlags, _path) {
    let upper = BigInt(0);
    upper += BigInt(this.#mtime);
    return { upper, lower: BigInt(0) };
  }
};
var descriptorGetEntry = Descriptor.prototype._getEntry;
delete Descriptor.prototype._getEntry;
var _preopens = [[new Descriptor(_fileData), "/"]];
var _rootPreopen = _preopens[0];
var preopens = {
  getDirectories() {
    return _preopens;
  }
};
var types = {
  Descriptor,
  DirectoryEntryStream
};

// node_modules/@bytecodealliance/preview2-shim/lib/browser/cli.js
var { InputStream: InputStream3, OutputStream: OutputStream3 } = streams;
var symbolDispose2 = Symbol.dispose ?? /* @__PURE__ */ Symbol.for("dispose");
var _env = [];
var _args = [];
var _cwd2 = "/";
var environment = {
  getEnvironment() {
    return _env;
  },
  getArguments() {
    return _args;
  },
  initialCwd() {
    return _cwd2;
  }
};
var ComponentExit = class extends Error {
  constructor(ok) {
    super(`Component exited ${ok ? "successfully" : "with error"}`);
    this.exitError = true;
    this.ok = ok;
  }
};
var exit2 = {
  exit(status) {
    throw new ComponentExit(status.tag === "err" ? true : false);
  }
};
var stdinStream = new InputStream3({
  blockingRead(_len) {
  },
  subscribe() {
  },
  [symbolDispose2]() {
  }
});
var textDecoder = new TextDecoder();
var stdoutStream = new OutputStream3({
  write(contents) {
    if (contents[contents.length - 1] == 10) {
      contents = contents.subarray(0, contents.length - 1);
    }
    console.log(textDecoder.decode(contents));
  },
  blockingFlush() {
  },
  [symbolDispose2]() {
  }
});
var stderrStream = new OutputStream3({
  write(contents) {
    if (contents[contents.length - 1] == 10) {
      contents = contents.subarray(0, contents.length - 1);
    }
    console.error(textDecoder.decode(contents));
  },
  blockingFlush() {
  },
  [symbolDispose2]() {
  }
});
var stdin2 = {
  InputStream: InputStream3,
  getStdin() {
    return stdinStream;
  }
};
var stdout2 = {
  OutputStream: OutputStream3,
  getStdout() {
    return stdoutStream;
  }
};
var stderr2 = {
  OutputStream: OutputStream3,
  getStderr() {
    return stderrStream;
  }
};
var TerminalInput = class {
};
var TerminalOutput = class {
};
var terminalStdoutInstance = new TerminalOutput();
var terminalStderrInstance = new TerminalOutput();
var terminalStdinInstance = new TerminalInput();
var terminalInput = {
  TerminalInput
};
var terminalOutput = {
  TerminalOutput
};
var terminalStderr = {
  TerminalOutput,
  getTerminalStderr() {
    return terminalStderrInstance;
  }
};
var terminalStdin = {
  TerminalInput,
  getTerminalStdin() {
    return terminalStdinInstance;
  }
};
var terminalStdout = {
  TerminalOutput,
  getTerminalStdout() {
    return terminalStdoutInstance;
  }
};

// node_modules/@bytecodealliance/preview2-shim/lib/browser/clocks.js
init_dirname();
init_buffer2();
init_process2();
var monotonicClock = {
  resolution() {
    return 1e6;
  },
  now() {
    return BigInt(Math.floor(performance.now() * 1e6));
  },
  subscribeInstant(instant) {
    instant = BigInt(instant);
    const now2 = this.now();
    if (instant <= now2)
      return this.subscribeDuration(0);
    return this.subscribeDuration(instant - now2);
  },
  subscribeDuration(_duration) {
    _duration = BigInt(_duration);
    console.log(`[monotonic-clock] subscribe`);
  }
};
var wallClock = {
  now() {
    let now2 = Date.now();
    const seconds = BigInt(Math.floor(now2 / 1e3));
    const nanoseconds = now2 % 1e3 * 1e6;
    return { seconds, nanoseconds };
  },
  resolution() {
    return { seconds: 0n, nanoseconds: 1e6 };
  }
};

// node_modules/@bytecodealliance/preview2-shim/lib/browser/random.js
init_dirname();
init_buffer2();
init_process2();
var MAX_BYTES = 65536;
var insecureRandomValue1;
var insecureRandomValue2;
var random = {
  getRandomBytes(len) {
    const bytes = new Uint8Array(Number(len));
    if (len > MAX_BYTES) {
      for (var generated = 0; generated < len; generated += MAX_BYTES) {
        crypto.getRandomValues(bytes.subarray(generated, generated + MAX_BYTES));
      }
    } else {
      crypto.getRandomValues(bytes);
    }
    return bytes;
  },
  getRandomU64() {
    return crypto.getRandomValues(new BigUint64Array(1))[0];
  },
  insecureRandom() {
    if (insecureRandomValue1 === void 0) {
      insecureRandomValue1 = random.getRandomU64();
      insecureRandomValue2 = random.getRandomU64();
    }
    return [insecureRandomValue1, insecureRandomValue2];
  }
};

// node_modules/@bsull/augurs-prophet-wasmstan/prophet-wasmstan.js
var { getEnvironment } = environment;
var { exit: exit4 } = exit2;
var { getStderr } = stderr2;
var { getStdin } = stdin2;
var { getStdout } = stdout2;
var { TerminalInput: TerminalInput2 } = terminalInput;
var { TerminalOutput: TerminalOutput2 } = terminalOutput;
var { getTerminalStderr } = terminalStderr;
var { getTerminalStdin } = terminalStdin;
var { getTerminalStdout } = terminalStdout;
var { now } = monotonicClock;
var { now: now$1 } = wallClock;
var { getDirectories } = preopens;
var {
  Descriptor: Descriptor2,
  filesystemErrorCode
} = types;
var { Error: Error$1 } = error;
var {
  InputStream: InputStream4,
  OutputStream: OutputStream4
} = streams;
var { getRandomBytes } = random;
var base64Compile = (str) => WebAssembly.compile(typeof Buffer2 !== "undefined" ? Buffer2.from(str, "base64") : Uint8Array.from(atob(str), (b5) => b5.charCodeAt(0)));
var ComponentError = class extends Error {
  constructor(value) {
    const enumerable = typeof value !== "string";
    super(enumerable ? `${String(value)} (see error.payload)` : value);
    Object.defineProperty(this, "payload", { value, enumerable });
  }
};
var curResourceBorrows = [];
var dv = new DataView(new ArrayBuffer());
var dataView = (mem) => dv.buffer === mem.buffer ? dv : dv = new DataView(mem.buffer);
var isNode = typeof process_exports !== "undefined" && process_exports.versions && process_exports.versions.node;
var _fs;
async function fetchCompile(url) {
  if (isNode) {
    _fs = _fs || await Promise.resolve().then(() => (init_promises(), promises_exports));
    return WebAssembly.compile(await _fs.readFile(url));
  }
  return fetch(url).then(WebAssembly.compileStreaming);
}
function getErrorPayload(e6) {
  if (e6 && hasOwnProperty.call(e6, "payload")) return e6.payload;
  if (e6 instanceof Error) throw e6;
  return e6;
}
var handleTables = [];
var hasOwnProperty = Object.prototype.hasOwnProperty;
var instantiateCore = WebAssembly.instantiate;
var T_FLAG = 1 << 30;
function rscTableCreateOwn(table, rep) {
  const free = table[0] & ~T_FLAG;
  if (free === 0) {
    table.push(0);
    table.push(rep | T_FLAG);
    return (table.length >> 1) - 1;
  }
  table[0] = table[free << 1];
  table[free << 1] = 0;
  table[(free << 1) + 1] = rep | T_FLAG;
  return free;
}
function rscTableRemove(table, handle) {
  const scope = table[handle << 1];
  const val = table[(handle << 1) + 1];
  const own = (val & T_FLAG) !== 0;
  const rep = val & ~T_FLAG;
  if (val === 0 || (scope & T_FLAG) !== 0) throw new TypeError("Invalid handle");
  table[handle << 1] = table[0] | T_FLAG;
  table[0] = handle | T_FLAG;
  return { rep, scope, own };
}
var symbolCabiDispose = /* @__PURE__ */ Symbol.for("cabiDispose");
var symbolRscHandle = /* @__PURE__ */ Symbol("handle");
var symbolRscRep = /* @__PURE__ */ Symbol.for("cabiRep");
var symbolDispose3 = Symbol.dispose || /* @__PURE__ */ Symbol.for("dispose");
var toUint64 = (val) => BigInt.asUintN(64, BigInt(val));
function toUint32(val) {
  return val >>> 0;
}
var utf8Decoder = new TextDecoder();
var utf8Encoder = new TextEncoder();
var utf8EncodedLen = 0;
function utf8Encode(s6, realloc, memory) {
  if (typeof s6 !== "string") throw new TypeError("expected a string");
  if (s6.length === 0) {
    utf8EncodedLen = 0;
    return 1;
  }
  let buf = utf8Encoder.encode(s6);
  let ptr = realloc(0, 0, 1, buf.length);
  new Uint8Array(memory.buffer).set(buf, ptr);
  utf8EncodedLen = buf.length;
  return ptr;
}
var exports0;
var exports1;
function trampoline0() {
  const ret = now();
  return toUint64(ret);
}
var handleTable2 = [T_FLAG, 0];
var captureTable2 = /* @__PURE__ */ new Map();
var captureCnt2 = 0;
handleTables[2] = handleTable2;
function trampoline8() {
  const ret = getStderr();
  if (!(ret instanceof OutputStream4)) {
    throw new TypeError('Resource error: Not a valid "OutputStream" resource.');
  }
  var handle0 = ret[symbolRscHandle];
  if (!handle0) {
    const rep = ret[symbolRscRep] || ++captureCnt2;
    captureTable2.set(rep, ret);
    handle0 = rscTableCreateOwn(handleTable2, rep);
  }
  return handle0;
}
function trampoline9(arg0) {
  let variant0;
  switch (arg0) {
    case 0: {
      variant0 = {
        tag: "ok",
        val: void 0
      };
      break;
    }
    case 1: {
      variant0 = {
        tag: "err",
        val: void 0
      };
      break;
    }
    default: {
      throw new TypeError("invalid variant discriminant for expected");
    }
  }
  exit4(variant0);
}
var handleTable1 = [T_FLAG, 0];
var captureTable1 = /* @__PURE__ */ new Map();
var captureCnt1 = 0;
handleTables[1] = handleTable1;
function trampoline10() {
  const ret = getStdin();
  if (!(ret instanceof InputStream4)) {
    throw new TypeError('Resource error: Not a valid "InputStream" resource.');
  }
  var handle0 = ret[symbolRscHandle];
  if (!handle0) {
    const rep = ret[symbolRscRep] || ++captureCnt1;
    captureTable1.set(rep, ret);
    handle0 = rscTableCreateOwn(handleTable1, rep);
  }
  return handle0;
}
function trampoline11() {
  const ret = getStdout();
  if (!(ret instanceof OutputStream4)) {
    throw new TypeError('Resource error: Not a valid "OutputStream" resource.');
  }
  var handle0 = ret[symbolRscHandle];
  if (!handle0) {
    const rep = ret[symbolRscRep] || ++captureCnt2;
    captureTable2.set(rep, ret);
    handle0 = rscTableCreateOwn(handleTable2, rep);
  }
  return handle0;
}
var exports22;
var memory0;
var realloc0;
var handleTable5 = [T_FLAG, 0];
var captureTable5 = /* @__PURE__ */ new Map();
var captureCnt5 = 0;
handleTables[5] = handleTable5;
function trampoline12(arg0) {
  const ret = getDirectories();
  var vec3 = ret;
  var len3 = vec3.length;
  var result3 = realloc0(0, 0, 4, len3 * 12);
  for (let i6 = 0; i6 < vec3.length; i6++) {
    const e6 = vec3[i6];
    const base = result3 + i6 * 12;
    var [tuple0_0, tuple0_1] = e6;
    if (!(tuple0_0 instanceof Descriptor2)) {
      throw new TypeError('Resource error: Not a valid "Descriptor" resource.');
    }
    var handle1 = tuple0_0[symbolRscHandle];
    if (!handle1) {
      const rep = tuple0_0[symbolRscRep] || ++captureCnt5;
      captureTable5.set(rep, tuple0_0);
      handle1 = rscTableCreateOwn(handleTable5, rep);
    }
    dataView(memory0).setInt32(base + 0, handle1, true);
    var ptr2 = utf8Encode(tuple0_1, realloc0, memory0);
    var len2 = utf8EncodedLen;
    dataView(memory0).setInt32(base + 8, len2, true);
    dataView(memory0).setInt32(base + 4, ptr2, true);
  }
  dataView(memory0).setInt32(arg0 + 4, len3, true);
  dataView(memory0).setInt32(arg0 + 0, result3, true);
}
function trampoline13(arg0) {
  const ret = now$1();
  var { seconds: v0_0, nanoseconds: v0_1 } = ret;
  dataView(memory0).setBigInt64(arg0 + 0, toUint64(v0_0), true);
  dataView(memory0).setInt32(arg0 + 8, toUint32(v0_1), true);
}
function trampoline14(arg0, arg1) {
  var handle1 = arg0;
  var rep2 = handleTable5[(handle1 << 1) + 1] & ~T_FLAG;
  var rsc0 = captureTable5.get(rep2);
  if (!rsc0) {
    rsc0 = Object.create(Descriptor2.prototype);
    Object.defineProperty(rsc0, symbolRscHandle, { writable: true, value: handle1 });
    Object.defineProperty(rsc0, symbolRscRep, { writable: true, value: rep2 });
  }
  curResourceBorrows.push(rsc0);
  let ret;
  try {
    ret = { tag: "ok", val: rsc0.getType() };
  } catch (e6) {
    ret = { tag: "err", val: getErrorPayload(e6) };
  }
  for (const rsc of curResourceBorrows) {
    rsc[symbolRscHandle] = null;
  }
  curResourceBorrows = [];
  var variant5 = ret;
  switch (variant5.tag) {
    case "ok": {
      const e6 = variant5.val;
      dataView(memory0).setInt8(arg1 + 0, 0, true);
      var val3 = e6;
      let enum3;
      switch (val3) {
        case "unknown": {
          enum3 = 0;
          break;
        }
        case "block-device": {
          enum3 = 1;
          break;
        }
        case "character-device": {
          enum3 = 2;
          break;
        }
        case "directory": {
          enum3 = 3;
          break;
        }
        case "fifo": {
          enum3 = 4;
          break;
        }
        case "symbolic-link": {
          enum3 = 5;
          break;
        }
        case "regular-file": {
          enum3 = 6;
          break;
        }
        case "socket": {
          enum3 = 7;
          break;
        }
        default: {
          if (e6 instanceof Error) {
            console.error(e6);
          }
          throw new TypeError(`"${val3}" is not one of the cases of descriptor-type`);
        }
      }
      dataView(memory0).setInt8(arg1 + 1, enum3, true);
      break;
    }
    case "err": {
      const e6 = variant5.val;
      dataView(memory0).setInt8(arg1 + 0, 1, true);
      var val4 = e6;
      let enum4;
      switch (val4) {
        case "access": {
          enum4 = 0;
          break;
        }
        case "would-block": {
          enum4 = 1;
          break;
        }
        case "already": {
          enum4 = 2;
          break;
        }
        case "bad-descriptor": {
          enum4 = 3;
          break;
        }
        case "busy": {
          enum4 = 4;
          break;
        }
        case "deadlock": {
          enum4 = 5;
          break;
        }
        case "quota": {
          enum4 = 6;
          break;
        }
        case "exist": {
          enum4 = 7;
          break;
        }
        case "file-too-large": {
          enum4 = 8;
          break;
        }
        case "illegal-byte-sequence": {
          enum4 = 9;
          break;
        }
        case "in-progress": {
          enum4 = 10;
          break;
        }
        case "interrupted": {
          enum4 = 11;
          break;
        }
        case "invalid": {
          enum4 = 12;
          break;
        }
        case "io": {
          enum4 = 13;
          break;
        }
        case "is-directory": {
          enum4 = 14;
          break;
        }
        case "loop": {
          enum4 = 15;
          break;
        }
        case "too-many-links": {
          enum4 = 16;
          break;
        }
        case "message-size": {
          enum4 = 17;
          break;
        }
        case "name-too-long": {
          enum4 = 18;
          break;
        }
        case "no-device": {
          enum4 = 19;
          break;
        }
        case "no-entry": {
          enum4 = 20;
          break;
        }
        case "no-lock": {
          enum4 = 21;
          break;
        }
        case "insufficient-memory": {
          enum4 = 22;
          break;
        }
        case "insufficient-space": {
          enum4 = 23;
          break;
        }
        case "not-directory": {
          enum4 = 24;
          break;
        }
        case "not-empty": {
          enum4 = 25;
          break;
        }
        case "not-recoverable": {
          enum4 = 26;
          break;
        }
        case "unsupported": {
          enum4 = 27;
          break;
        }
        case "no-tty": {
          enum4 = 28;
          break;
        }
        case "no-such-device": {
          enum4 = 29;
          break;
        }
        case "overflow": {
          enum4 = 30;
          break;
        }
        case "not-permitted": {
          enum4 = 31;
          break;
        }
        case "pipe": {
          enum4 = 32;
          break;
        }
        case "read-only": {
          enum4 = 33;
          break;
        }
        case "invalid-seek": {
          enum4 = 34;
          break;
        }
        case "text-file-busy": {
          enum4 = 35;
          break;
        }
        case "cross-device": {
          enum4 = 36;
          break;
        }
        default: {
          if (e6 instanceof Error) {
            console.error(e6);
          }
          throw new TypeError(`"${val4}" is not one of the cases of error-code`);
        }
      }
      dataView(memory0).setInt8(arg1 + 1, enum4, true);
      break;
    }
    default: {
      throw new TypeError("invalid variant specified for result");
    }
  }
}
var handleTable0 = [T_FLAG, 0];
var captureTable0 = /* @__PURE__ */ new Map();
var captureCnt0 = 0;
handleTables[0] = handleTable0;
function trampoline15(arg0, arg1) {
  var handle1 = arg0;
  var rep2 = handleTable0[(handle1 << 1) + 1] & ~T_FLAG;
  var rsc0 = captureTable0.get(rep2);
  if (!rsc0) {
    rsc0 = Object.create(Error$1.prototype);
    Object.defineProperty(rsc0, symbolRscHandle, { writable: true, value: handle1 });
    Object.defineProperty(rsc0, symbolRscRep, { writable: true, value: rep2 });
  }
  curResourceBorrows.push(rsc0);
  const ret = filesystemErrorCode(rsc0);
  for (const rsc of curResourceBorrows) {
    rsc[symbolRscHandle] = null;
  }
  curResourceBorrows = [];
  var variant4 = ret;
  if (variant4 === null || variant4 === void 0) {
    dataView(memory0).setInt8(arg1 + 0, 0, true);
  } else {
    const e6 = variant4;
    dataView(memory0).setInt8(arg1 + 0, 1, true);
    var val3 = e6;
    let enum3;
    switch (val3) {
      case "access": {
        enum3 = 0;
        break;
      }
      case "would-block": {
        enum3 = 1;
        break;
      }
      case "already": {
        enum3 = 2;
        break;
      }
      case "bad-descriptor": {
        enum3 = 3;
        break;
      }
      case "busy": {
        enum3 = 4;
        break;
      }
      case "deadlock": {
        enum3 = 5;
        break;
      }
      case "quota": {
        enum3 = 6;
        break;
      }
      case "exist": {
        enum3 = 7;
        break;
      }
      case "file-too-large": {
        enum3 = 8;
        break;
      }
      case "illegal-byte-sequence": {
        enum3 = 9;
        break;
      }
      case "in-progress": {
        enum3 = 10;
        break;
      }
      case "interrupted": {
        enum3 = 11;
        break;
      }
      case "invalid": {
        enum3 = 12;
        break;
      }
      case "io": {
        enum3 = 13;
        break;
      }
      case "is-directory": {
        enum3 = 14;
        break;
      }
      case "loop": {
        enum3 = 15;
        break;
      }
      case "too-many-links": {
        enum3 = 16;
        break;
      }
      case "message-size": {
        enum3 = 17;
        break;
      }
      case "name-too-long": {
        enum3 = 18;
        break;
      }
      case "no-device": {
        enum3 = 19;
        break;
      }
      case "no-entry": {
        enum3 = 20;
        break;
      }
      case "no-lock": {
        enum3 = 21;
        break;
      }
      case "insufficient-memory": {
        enum3 = 22;
        break;
      }
      case "insufficient-space": {
        enum3 = 23;
        break;
      }
      case "not-directory": {
        enum3 = 24;
        break;
      }
      case "not-empty": {
        enum3 = 25;
        break;
      }
      case "not-recoverable": {
        enum3 = 26;
        break;
      }
      case "unsupported": {
        enum3 = 27;
        break;
      }
      case "no-tty": {
        enum3 = 28;
        break;
      }
      case "no-such-device": {
        enum3 = 29;
        break;
      }
      case "overflow": {
        enum3 = 30;
        break;
      }
      case "not-permitted": {
        enum3 = 31;
        break;
      }
      case "pipe": {
        enum3 = 32;
        break;
      }
      case "read-only": {
        enum3 = 33;
        break;
      }
      case "invalid-seek": {
        enum3 = 34;
        break;
      }
      case "text-file-busy": {
        enum3 = 35;
        break;
      }
      case "cross-device": {
        enum3 = 36;
        break;
      }
      default: {
        if (e6 instanceof Error) {
          console.error(e6);
        }
        throw new TypeError(`"${val3}" is not one of the cases of error-code`);
      }
    }
    dataView(memory0).setInt8(arg1 + 1, enum3, true);
  }
}
function trampoline16(arg0, arg1, arg2) {
  var handle1 = arg0;
  var rep2 = handleTable5[(handle1 << 1) + 1] & ~T_FLAG;
  var rsc0 = captureTable5.get(rep2);
  if (!rsc0) {
    rsc0 = Object.create(Descriptor2.prototype);
    Object.defineProperty(rsc0, symbolRscHandle, { writable: true, value: handle1 });
    Object.defineProperty(rsc0, symbolRscRep, { writable: true, value: rep2 });
  }
  curResourceBorrows.push(rsc0);
  let ret;
  try {
    ret = { tag: "ok", val: rsc0.readViaStream(BigInt.asUintN(64, arg1)) };
  } catch (e6) {
    ret = { tag: "err", val: getErrorPayload(e6) };
  }
  for (const rsc of curResourceBorrows) {
    rsc[symbolRscHandle] = null;
  }
  curResourceBorrows = [];
  var variant5 = ret;
  switch (variant5.tag) {
    case "ok": {
      const e6 = variant5.val;
      dataView(memory0).setInt8(arg2 + 0, 0, true);
      if (!(e6 instanceof InputStream4)) {
        throw new TypeError('Resource error: Not a valid "InputStream" resource.');
      }
      var handle3 = e6[symbolRscHandle];
      if (!handle3) {
        const rep = e6[symbolRscRep] || ++captureCnt1;
        captureTable1.set(rep, e6);
        handle3 = rscTableCreateOwn(handleTable1, rep);
      }
      dataView(memory0).setInt32(arg2 + 4, handle3, true);
      break;
    }
    case "err": {
      const e6 = variant5.val;
      dataView(memory0).setInt8(arg2 + 0, 1, true);
      var val4 = e6;
      let enum4;
      switch (val4) {
        case "access": {
          enum4 = 0;
          break;
        }
        case "would-block": {
          enum4 = 1;
          break;
        }
        case "already": {
          enum4 = 2;
          break;
        }
        case "bad-descriptor": {
          enum4 = 3;
          break;
        }
        case "busy": {
          enum4 = 4;
          break;
        }
        case "deadlock": {
          enum4 = 5;
          break;
        }
        case "quota": {
          enum4 = 6;
          break;
        }
        case "exist": {
          enum4 = 7;
          break;
        }
        case "file-too-large": {
          enum4 = 8;
          break;
        }
        case "illegal-byte-sequence": {
          enum4 = 9;
          break;
        }
        case "in-progress": {
          enum4 = 10;
          break;
        }
        case "interrupted": {
          enum4 = 11;
          break;
        }
        case "invalid": {
          enum4 = 12;
          break;
        }
        case "io": {
          enum4 = 13;
          break;
        }
        case "is-directory": {
          enum4 = 14;
          break;
        }
        case "loop": {
          enum4 = 15;
          break;
        }
        case "too-many-links": {
          enum4 = 16;
          break;
        }
        case "message-size": {
          enum4 = 17;
          break;
        }
        case "name-too-long": {
          enum4 = 18;
          break;
        }
        case "no-device": {
          enum4 = 19;
          break;
        }
        case "no-entry": {
          enum4 = 20;
          break;
        }
        case "no-lock": {
          enum4 = 21;
          break;
        }
        case "insufficient-memory": {
          enum4 = 22;
          break;
        }
        case "insufficient-space": {
          enum4 = 23;
          break;
        }
        case "not-directory": {
          enum4 = 24;
          break;
        }
        case "not-empty": {
          enum4 = 25;
          break;
        }
        case "not-recoverable": {
          enum4 = 26;
          break;
        }
        case "unsupported": {
          enum4 = 27;
          break;
        }
        case "no-tty": {
          enum4 = 28;
          break;
        }
        case "no-such-device": {
          enum4 = 29;
          break;
        }
        case "overflow": {
          enum4 = 30;
          break;
        }
        case "not-permitted": {
          enum4 = 31;
          break;
        }
        case "pipe": {
          enum4 = 32;
          break;
        }
        case "read-only": {
          enum4 = 33;
          break;
        }
        case "invalid-seek": {
          enum4 = 34;
          break;
        }
        case "text-file-busy": {
          enum4 = 35;
          break;
        }
        case "cross-device": {
          enum4 = 36;
          break;
        }
        default: {
          if (e6 instanceof Error) {
            console.error(e6);
          }
          throw new TypeError(`"${val4}" is not one of the cases of error-code`);
        }
      }
      dataView(memory0).setInt8(arg2 + 4, enum4, true);
      break;
    }
    default: {
      throw new TypeError("invalid variant specified for result");
    }
  }
}
function trampoline17(arg0, arg1, arg2) {
  var handle1 = arg0;
  var rep2 = handleTable5[(handle1 << 1) + 1] & ~T_FLAG;
  var rsc0 = captureTable5.get(rep2);
  if (!rsc0) {
    rsc0 = Object.create(Descriptor2.prototype);
    Object.defineProperty(rsc0, symbolRscHandle, { writable: true, value: handle1 });
    Object.defineProperty(rsc0, symbolRscRep, { writable: true, value: rep2 });
  }
  curResourceBorrows.push(rsc0);
  let ret;
  try {
    ret = { tag: "ok", val: rsc0.writeViaStream(BigInt.asUintN(64, arg1)) };
  } catch (e6) {
    ret = { tag: "err", val: getErrorPayload(e6) };
  }
  for (const rsc of curResourceBorrows) {
    rsc[symbolRscHandle] = null;
  }
  curResourceBorrows = [];
  var variant5 = ret;
  switch (variant5.tag) {
    case "ok": {
      const e6 = variant5.val;
      dataView(memory0).setInt8(arg2 + 0, 0, true);
      if (!(e6 instanceof OutputStream4)) {
        throw new TypeError('Resource error: Not a valid "OutputStream" resource.');
      }
      var handle3 = e6[symbolRscHandle];
      if (!handle3) {
        const rep = e6[symbolRscRep] || ++captureCnt2;
        captureTable2.set(rep, e6);
        handle3 = rscTableCreateOwn(handleTable2, rep);
      }
      dataView(memory0).setInt32(arg2 + 4, handle3, true);
      break;
    }
    case "err": {
      const e6 = variant5.val;
      dataView(memory0).setInt8(arg2 + 0, 1, true);
      var val4 = e6;
      let enum4;
      switch (val4) {
        case "access": {
          enum4 = 0;
          break;
        }
        case "would-block": {
          enum4 = 1;
          break;
        }
        case "already": {
          enum4 = 2;
          break;
        }
        case "bad-descriptor": {
          enum4 = 3;
          break;
        }
        case "busy": {
          enum4 = 4;
          break;
        }
        case "deadlock": {
          enum4 = 5;
          break;
        }
        case "quota": {
          enum4 = 6;
          break;
        }
        case "exist": {
          enum4 = 7;
          break;
        }
        case "file-too-large": {
          enum4 = 8;
          break;
        }
        case "illegal-byte-sequence": {
          enum4 = 9;
          break;
        }
        case "in-progress": {
          enum4 = 10;
          break;
        }
        case "interrupted": {
          enum4 = 11;
          break;
        }
        case "invalid": {
          enum4 = 12;
          break;
        }
        case "io": {
          enum4 = 13;
          break;
        }
        case "is-directory": {
          enum4 = 14;
          break;
        }
        case "loop": {
          enum4 = 15;
          break;
        }
        case "too-many-links": {
          enum4 = 16;
          break;
        }
        case "message-size": {
          enum4 = 17;
          break;
        }
        case "name-too-long": {
          enum4 = 18;
          break;
        }
        case "no-device": {
          enum4 = 19;
          break;
        }
        case "no-entry": {
          enum4 = 20;
          break;
        }
        case "no-lock": {
          enum4 = 21;
          break;
        }
        case "insufficient-memory": {
          enum4 = 22;
          break;
        }
        case "insufficient-space": {
          enum4 = 23;
          break;
        }
        case "not-directory": {
          enum4 = 24;
          break;
        }
        case "not-empty": {
          enum4 = 25;
          break;
        }
        case "not-recoverable": {
          enum4 = 26;
          break;
        }
        case "unsupported": {
          enum4 = 27;
          break;
        }
        case "no-tty": {
          enum4 = 28;
          break;
        }
        case "no-such-device": {
          enum4 = 29;
          break;
        }
        case "overflow": {
          enum4 = 30;
          break;
        }
        case "not-permitted": {
          enum4 = 31;
          break;
        }
        case "pipe": {
          enum4 = 32;
          break;
        }
        case "read-only": {
          enum4 = 33;
          break;
        }
        case "invalid-seek": {
          enum4 = 34;
          break;
        }
        case "text-file-busy": {
          enum4 = 35;
          break;
        }
        case "cross-device": {
          enum4 = 36;
          break;
        }
        default: {
          if (e6 instanceof Error) {
            console.error(e6);
          }
          throw new TypeError(`"${val4}" is not one of the cases of error-code`);
        }
      }
      dataView(memory0).setInt8(arg2 + 4, enum4, true);
      break;
    }
    default: {
      throw new TypeError("invalid variant specified for result");
    }
  }
}
function trampoline18(arg0, arg1) {
  var handle1 = arg0;
  var rep2 = handleTable5[(handle1 << 1) + 1] & ~T_FLAG;
  var rsc0 = captureTable5.get(rep2);
  if (!rsc0) {
    rsc0 = Object.create(Descriptor2.prototype);
    Object.defineProperty(rsc0, symbolRscHandle, { writable: true, value: handle1 });
    Object.defineProperty(rsc0, symbolRscRep, { writable: true, value: rep2 });
  }
  curResourceBorrows.push(rsc0);
  let ret;
  try {
    ret = { tag: "ok", val: rsc0.appendViaStream() };
  } catch (e6) {
    ret = { tag: "err", val: getErrorPayload(e6) };
  }
  for (const rsc of curResourceBorrows) {
    rsc[symbolRscHandle] = null;
  }
  curResourceBorrows = [];
  var variant5 = ret;
  switch (variant5.tag) {
    case "ok": {
      const e6 = variant5.val;
      dataView(memory0).setInt8(arg1 + 0, 0, true);
      if (!(e6 instanceof OutputStream4)) {
        throw new TypeError('Resource error: Not a valid "OutputStream" resource.');
      }
      var handle3 = e6[symbolRscHandle];
      if (!handle3) {
        const rep = e6[symbolRscRep] || ++captureCnt2;
        captureTable2.set(rep, e6);
        handle3 = rscTableCreateOwn(handleTable2, rep);
      }
      dataView(memory0).setInt32(arg1 + 4, handle3, true);
      break;
    }
    case "err": {
      const e6 = variant5.val;
      dataView(memory0).setInt8(arg1 + 0, 1, true);
      var val4 = e6;
      let enum4;
      switch (val4) {
        case "access": {
          enum4 = 0;
          break;
        }
        case "would-block": {
          enum4 = 1;
          break;
        }
        case "already": {
          enum4 = 2;
          break;
        }
        case "bad-descriptor": {
          enum4 = 3;
          break;
        }
        case "busy": {
          enum4 = 4;
          break;
        }
        case "deadlock": {
          enum4 = 5;
          break;
        }
        case "quota": {
          enum4 = 6;
          break;
        }
        case "exist": {
          enum4 = 7;
          break;
        }
        case "file-too-large": {
          enum4 = 8;
          break;
        }
        case "illegal-byte-sequence": {
          enum4 = 9;
          break;
        }
        case "in-progress": {
          enum4 = 10;
          break;
        }
        case "interrupted": {
          enum4 = 11;
          break;
        }
        case "invalid": {
          enum4 = 12;
          break;
        }
        case "io": {
          enum4 = 13;
          break;
        }
        case "is-directory": {
          enum4 = 14;
          break;
        }
        case "loop": {
          enum4 = 15;
          break;
        }
        case "too-many-links": {
          enum4 = 16;
          break;
        }
        case "message-size": {
          enum4 = 17;
          break;
        }
        case "name-too-long": {
          enum4 = 18;
          break;
        }
        case "no-device": {
          enum4 = 19;
          break;
        }
        case "no-entry": {
          enum4 = 20;
          break;
        }
        case "no-lock": {
          enum4 = 21;
          break;
        }
        case "insufficient-memory": {
          enum4 = 22;
          break;
        }
        case "insufficient-space": {
          enum4 = 23;
          break;
        }
        case "not-directory": {
          enum4 = 24;
          break;
        }
        case "not-empty": {
          enum4 = 25;
          break;
        }
        case "not-recoverable": {
          enum4 = 26;
          break;
        }
        case "unsupported": {
          enum4 = 27;
          break;
        }
        case "no-tty": {
          enum4 = 28;
          break;
        }
        case "no-such-device": {
          enum4 = 29;
          break;
        }
        case "overflow": {
          enum4 = 30;
          break;
        }
        case "not-permitted": {
          enum4 = 31;
          break;
        }
        case "pipe": {
          enum4 = 32;
          break;
        }
        case "read-only": {
          enum4 = 33;
          break;
        }
        case "invalid-seek": {
          enum4 = 34;
          break;
        }
        case "text-file-busy": {
          enum4 = 35;
          break;
        }
        case "cross-device": {
          enum4 = 36;
          break;
        }
        default: {
          if (e6 instanceof Error) {
            console.error(e6);
          }
          throw new TypeError(`"${val4}" is not one of the cases of error-code`);
        }
      }
      dataView(memory0).setInt8(arg1 + 4, enum4, true);
      break;
    }
    default: {
      throw new TypeError("invalid variant specified for result");
    }
  }
}
function trampoline19(arg0, arg1) {
  var handle1 = arg0;
  var rep2 = handleTable5[(handle1 << 1) + 1] & ~T_FLAG;
  var rsc0 = captureTable5.get(rep2);
  if (!rsc0) {
    rsc0 = Object.create(Descriptor2.prototype);
    Object.defineProperty(rsc0, symbolRscHandle, { writable: true, value: handle1 });
    Object.defineProperty(rsc0, symbolRscRep, { writable: true, value: rep2 });
  }
  curResourceBorrows.push(rsc0);
  let ret;
  try {
    ret = { tag: "ok", val: rsc0.getFlags() };
  } catch (e6) {
    ret = { tag: "err", val: getErrorPayload(e6) };
  }
  for (const rsc of curResourceBorrows) {
    rsc[symbolRscHandle] = null;
  }
  curResourceBorrows = [];
  var variant5 = ret;
  switch (variant5.tag) {
    case "ok": {
      const e6 = variant5.val;
      dataView(memory0).setInt8(arg1 + 0, 0, true);
      let flags3 = 0;
      if (typeof e6 === "object" && e6 !== null) {
        flags3 = Boolean(e6.read) << 0 | Boolean(e6.write) << 1 | Boolean(e6.fileIntegritySync) << 2 | Boolean(e6.dataIntegritySync) << 3 | Boolean(e6.requestedWriteSync) << 4 | Boolean(e6.mutateDirectory) << 5;
      } else if (e6 !== null && e6 !== void 0) {
        throw new TypeError("only an object, undefined or null can be converted to flags");
      }
      dataView(memory0).setInt8(arg1 + 1, flags3, true);
      break;
    }
    case "err": {
      const e6 = variant5.val;
      dataView(memory0).setInt8(arg1 + 0, 1, true);
      var val4 = e6;
      let enum4;
      switch (val4) {
        case "access": {
          enum4 = 0;
          break;
        }
        case "would-block": {
          enum4 = 1;
          break;
        }
        case "already": {
          enum4 = 2;
          break;
        }
        case "bad-descriptor": {
          enum4 = 3;
          break;
        }
        case "busy": {
          enum4 = 4;
          break;
        }
        case "deadlock": {
          enum4 = 5;
          break;
        }
        case "quota": {
          enum4 = 6;
          break;
        }
        case "exist": {
          enum4 = 7;
          break;
        }
        case "file-too-large": {
          enum4 = 8;
          break;
        }
        case "illegal-byte-sequence": {
          enum4 = 9;
          break;
        }
        case "in-progress": {
          enum4 = 10;
          break;
        }
        case "interrupted": {
          enum4 = 11;
          break;
        }
        case "invalid": {
          enum4 = 12;
          break;
        }
        case "io": {
          enum4 = 13;
          break;
        }
        case "is-directory": {
          enum4 = 14;
          break;
        }
        case "loop": {
          enum4 = 15;
          break;
        }
        case "too-many-links": {
          enum4 = 16;
          break;
        }
        case "message-size": {
          enum4 = 17;
          break;
        }
        case "name-too-long": {
          enum4 = 18;
          break;
        }
        case "no-device": {
          enum4 = 19;
          break;
        }
        case "no-entry": {
          enum4 = 20;
          break;
        }
        case "no-lock": {
          enum4 = 21;
          break;
        }
        case "insufficient-memory": {
          enum4 = 22;
          break;
        }
        case "insufficient-space": {
          enum4 = 23;
          break;
        }
        case "not-directory": {
          enum4 = 24;
          break;
        }
        case "not-empty": {
          enum4 = 25;
          break;
        }
        case "not-recoverable": {
          enum4 = 26;
          break;
        }
        case "unsupported": {
          enum4 = 27;
          break;
        }
        case "no-tty": {
          enum4 = 28;
          break;
        }
        case "no-such-device": {
          enum4 = 29;
          break;
        }
        case "overflow": {
          enum4 = 30;
          break;
        }
        case "not-permitted": {
          enum4 = 31;
          break;
        }
        case "pipe": {
          enum4 = 32;
          break;
        }
        case "read-only": {
          enum4 = 33;
          break;
        }
        case "invalid-seek": {
          enum4 = 34;
          break;
        }
        case "text-file-busy": {
          enum4 = 35;
          break;
        }
        case "cross-device": {
          enum4 = 36;
          break;
        }
        default: {
          if (e6 instanceof Error) {
            console.error(e6);
          }
          throw new TypeError(`"${val4}" is not one of the cases of error-code`);
        }
      }
      dataView(memory0).setInt8(arg1 + 1, enum4, true);
      break;
    }
    default: {
      throw new TypeError("invalid variant specified for result");
    }
  }
}
function trampoline20(arg0, arg1) {
  var handle1 = arg0;
  var rep2 = handleTable5[(handle1 << 1) + 1] & ~T_FLAG;
  var rsc0 = captureTable5.get(rep2);
  if (!rsc0) {
    rsc0 = Object.create(Descriptor2.prototype);
    Object.defineProperty(rsc0, symbolRscHandle, { writable: true, value: handle1 });
    Object.defineProperty(rsc0, symbolRscRep, { writable: true, value: rep2 });
  }
  curResourceBorrows.push(rsc0);
  let ret;
  try {
    ret = { tag: "ok", val: rsc0.stat() };
  } catch (e6) {
    ret = { tag: "err", val: getErrorPayload(e6) };
  }
  for (const rsc of curResourceBorrows) {
    rsc[symbolRscHandle] = null;
  }
  curResourceBorrows = [];
  var variant12 = ret;
  switch (variant12.tag) {
    case "ok": {
      const e6 = variant12.val;
      dataView(memory0).setInt8(arg1 + 0, 0, true);
      var { type: v3_0, linkCount: v3_1, size: v3_2, dataAccessTimestamp: v3_3, dataModificationTimestamp: v3_4, statusChangeTimestamp: v3_5 } = e6;
      var val4 = v3_0;
      let enum4;
      switch (val4) {
        case "unknown": {
          enum4 = 0;
          break;
        }
        case "block-device": {
          enum4 = 1;
          break;
        }
        case "character-device": {
          enum4 = 2;
          break;
        }
        case "directory": {
          enum4 = 3;
          break;
        }
        case "fifo": {
          enum4 = 4;
          break;
        }
        case "symbolic-link": {
          enum4 = 5;
          break;
        }
        case "regular-file": {
          enum4 = 6;
          break;
        }
        case "socket": {
          enum4 = 7;
          break;
        }
        default: {
          if (v3_0 instanceof Error) {
            console.error(v3_0);
          }
          throw new TypeError(`"${val4}" is not one of the cases of descriptor-type`);
        }
      }
      dataView(memory0).setInt8(arg1 + 8, enum4, true);
      dataView(memory0).setBigInt64(arg1 + 16, toUint64(v3_1), true);
      dataView(memory0).setBigInt64(arg1 + 24, toUint64(v3_2), true);
      var variant6 = v3_3;
      if (variant6 === null || variant6 === void 0) {
        dataView(memory0).setInt8(arg1 + 32, 0, true);
      } else {
        const e7 = variant6;
        dataView(memory0).setInt8(arg1 + 32, 1, true);
        var { seconds: v5_0, nanoseconds: v5_1 } = e7;
        dataView(memory0).setBigInt64(arg1 + 40, toUint64(v5_0), true);
        dataView(memory0).setInt32(arg1 + 48, toUint32(v5_1), true);
      }
      var variant8 = v3_4;
      if (variant8 === null || variant8 === void 0) {
        dataView(memory0).setInt8(arg1 + 56, 0, true);
      } else {
        const e7 = variant8;
        dataView(memory0).setInt8(arg1 + 56, 1, true);
        var { seconds: v7_0, nanoseconds: v7_1 } = e7;
        dataView(memory0).setBigInt64(arg1 + 64, toUint64(v7_0), true);
        dataView(memory0).setInt32(arg1 + 72, toUint32(v7_1), true);
      }
      var variant10 = v3_5;
      if (variant10 === null || variant10 === void 0) {
        dataView(memory0).setInt8(arg1 + 80, 0, true);
      } else {
        const e7 = variant10;
        dataView(memory0).setInt8(arg1 + 80, 1, true);
        var { seconds: v9_0, nanoseconds: v9_1 } = e7;
        dataView(memory0).setBigInt64(arg1 + 88, toUint64(v9_0), true);
        dataView(memory0).setInt32(arg1 + 96, toUint32(v9_1), true);
      }
      break;
    }
    case "err": {
      const e6 = variant12.val;
      dataView(memory0).setInt8(arg1 + 0, 1, true);
      var val11 = e6;
      let enum11;
      switch (val11) {
        case "access": {
          enum11 = 0;
          break;
        }
        case "would-block": {
          enum11 = 1;
          break;
        }
        case "already": {
          enum11 = 2;
          break;
        }
        case "bad-descriptor": {
          enum11 = 3;
          break;
        }
        case "busy": {
          enum11 = 4;
          break;
        }
        case "deadlock": {
          enum11 = 5;
          break;
        }
        case "quota": {
          enum11 = 6;
          break;
        }
        case "exist": {
          enum11 = 7;
          break;
        }
        case "file-too-large": {
          enum11 = 8;
          break;
        }
        case "illegal-byte-sequence": {
          enum11 = 9;
          break;
        }
        case "in-progress": {
          enum11 = 10;
          break;
        }
        case "interrupted": {
          enum11 = 11;
          break;
        }
        case "invalid": {
          enum11 = 12;
          break;
        }
        case "io": {
          enum11 = 13;
          break;
        }
        case "is-directory": {
          enum11 = 14;
          break;
        }
        case "loop": {
          enum11 = 15;
          break;
        }
        case "too-many-links": {
          enum11 = 16;
          break;
        }
        case "message-size": {
          enum11 = 17;
          break;
        }
        case "name-too-long": {
          enum11 = 18;
          break;
        }
        case "no-device": {
          enum11 = 19;
          break;
        }
        case "no-entry": {
          enum11 = 20;
          break;
        }
        case "no-lock": {
          enum11 = 21;
          break;
        }
        case "insufficient-memory": {
          enum11 = 22;
          break;
        }
        case "insufficient-space": {
          enum11 = 23;
          break;
        }
        case "not-directory": {
          enum11 = 24;
          break;
        }
        case "not-empty": {
          enum11 = 25;
          break;
        }
        case "not-recoverable": {
          enum11 = 26;
          break;
        }
        case "unsupported": {
          enum11 = 27;
          break;
        }
        case "no-tty": {
          enum11 = 28;
          break;
        }
        case "no-such-device": {
          enum11 = 29;
          break;
        }
        case "overflow": {
          enum11 = 30;
          break;
        }
        case "not-permitted": {
          enum11 = 31;
          break;
        }
        case "pipe": {
          enum11 = 32;
          break;
        }
        case "read-only": {
          enum11 = 33;
          break;
        }
        case "invalid-seek": {
          enum11 = 34;
          break;
        }
        case "text-file-busy": {
          enum11 = 35;
          break;
        }
        case "cross-device": {
          enum11 = 36;
          break;
        }
        default: {
          if (e6 instanceof Error) {
            console.error(e6);
          }
          throw new TypeError(`"${val11}" is not one of the cases of error-code`);
        }
      }
      dataView(memory0).setInt8(arg1 + 8, enum11, true);
      break;
    }
    default: {
      throw new TypeError("invalid variant specified for result");
    }
  }
}
function trampoline21(arg0, arg1, arg2) {
  var handle1 = arg0;
  var rep2 = handleTable1[(handle1 << 1) + 1] & ~T_FLAG;
  var rsc0 = captureTable1.get(rep2);
  if (!rsc0) {
    rsc0 = Object.create(InputStream4.prototype);
    Object.defineProperty(rsc0, symbolRscHandle, { writable: true, value: handle1 });
    Object.defineProperty(rsc0, symbolRscRep, { writable: true, value: rep2 });
  }
  curResourceBorrows.push(rsc0);
  let ret;
  try {
    ret = { tag: "ok", val: rsc0.read(BigInt.asUintN(64, arg1)) };
  } catch (e6) {
    ret = { tag: "err", val: getErrorPayload(e6) };
  }
  for (const rsc of curResourceBorrows) {
    rsc[symbolRscHandle] = null;
  }
  curResourceBorrows = [];
  var variant6 = ret;
  switch (variant6.tag) {
    case "ok": {
      const e6 = variant6.val;
      dataView(memory0).setInt8(arg2 + 0, 0, true);
      var val3 = e6;
      var len3 = val3.byteLength;
      var ptr3 = realloc0(0, 0, 1, len3 * 1);
      var src3 = new Uint8Array(val3.buffer || val3, val3.byteOffset, len3 * 1);
      new Uint8Array(memory0.buffer, ptr3, len3 * 1).set(src3);
      dataView(memory0).setInt32(arg2 + 8, len3, true);
      dataView(memory0).setInt32(arg2 + 4, ptr3, true);
      break;
    }
    case "err": {
      const e6 = variant6.val;
      dataView(memory0).setInt8(arg2 + 0, 1, true);
      var variant5 = e6;
      switch (variant5.tag) {
        case "last-operation-failed": {
          const e7 = variant5.val;
          dataView(memory0).setInt8(arg2 + 4, 0, true);
          if (!(e7 instanceof Error$1)) {
            throw new TypeError('Resource error: Not a valid "Error" resource.');
          }
          var handle4 = e7[symbolRscHandle];
          if (!handle4) {
            const rep = e7[symbolRscRep] || ++captureCnt0;
            captureTable0.set(rep, e7);
            handle4 = rscTableCreateOwn(handleTable0, rep);
          }
          dataView(memory0).setInt32(arg2 + 8, handle4, true);
          break;
        }
        case "closed": {
          dataView(memory0).setInt8(arg2 + 4, 1, true);
          break;
        }
        default: {
          throw new TypeError(`invalid variant tag value \`${JSON.stringify(variant5.tag)}\` (received \`${variant5}\`) specified for \`StreamError\``);
        }
      }
      break;
    }
    default: {
      throw new TypeError("invalid variant specified for result");
    }
  }
}
function trampoline22(arg0, arg1, arg2) {
  var handle1 = arg0;
  var rep2 = handleTable1[(handle1 << 1) + 1] & ~T_FLAG;
  var rsc0 = captureTable1.get(rep2);
  if (!rsc0) {
    rsc0 = Object.create(InputStream4.prototype);
    Object.defineProperty(rsc0, symbolRscHandle, { writable: true, value: handle1 });
    Object.defineProperty(rsc0, symbolRscRep, { writable: true, value: rep2 });
  }
  curResourceBorrows.push(rsc0);
  let ret;
  try {
    ret = { tag: "ok", val: rsc0.blockingRead(BigInt.asUintN(64, arg1)) };
  } catch (e6) {
    ret = { tag: "err", val: getErrorPayload(e6) };
  }
  for (const rsc of curResourceBorrows) {
    rsc[symbolRscHandle] = null;
  }
  curResourceBorrows = [];
  var variant6 = ret;
  switch (variant6.tag) {
    case "ok": {
      const e6 = variant6.val;
      dataView(memory0).setInt8(arg2 + 0, 0, true);
      var val3 = e6;
      var len3 = val3.byteLength;
      var ptr3 = realloc0(0, 0, 1, len3 * 1);
      var src3 = new Uint8Array(val3.buffer || val3, val3.byteOffset, len3 * 1);
      new Uint8Array(memory0.buffer, ptr3, len3 * 1).set(src3);
      dataView(memory0).setInt32(arg2 + 8, len3, true);
      dataView(memory0).setInt32(arg2 + 4, ptr3, true);
      break;
    }
    case "err": {
      const e6 = variant6.val;
      dataView(memory0).setInt8(arg2 + 0, 1, true);
      var variant5 = e6;
      switch (variant5.tag) {
        case "last-operation-failed": {
          const e7 = variant5.val;
          dataView(memory0).setInt8(arg2 + 4, 0, true);
          if (!(e7 instanceof Error$1)) {
            throw new TypeError('Resource error: Not a valid "Error" resource.');
          }
          var handle4 = e7[symbolRscHandle];
          if (!handle4) {
            const rep = e7[symbolRscRep] || ++captureCnt0;
            captureTable0.set(rep, e7);
            handle4 = rscTableCreateOwn(handleTable0, rep);
          }
          dataView(memory0).setInt32(arg2 + 8, handle4, true);
          break;
        }
        case "closed": {
          dataView(memory0).setInt8(arg2 + 4, 1, true);
          break;
        }
        default: {
          throw new TypeError(`invalid variant tag value \`${JSON.stringify(variant5.tag)}\` (received \`${variant5}\`) specified for \`StreamError\``);
        }
      }
      break;
    }
    default: {
      throw new TypeError("invalid variant specified for result");
    }
  }
}
function trampoline23(arg0, arg1) {
  var handle1 = arg0;
  var rep2 = handleTable2[(handle1 << 1) + 1] & ~T_FLAG;
  var rsc0 = captureTable2.get(rep2);
  if (!rsc0) {
    rsc0 = Object.create(OutputStream4.prototype);
    Object.defineProperty(rsc0, symbolRscHandle, { writable: true, value: handle1 });
    Object.defineProperty(rsc0, symbolRscRep, { writable: true, value: rep2 });
  }
  curResourceBorrows.push(rsc0);
  let ret;
  try {
    ret = { tag: "ok", val: rsc0.checkWrite() };
  } catch (e6) {
    ret = { tag: "err", val: getErrorPayload(e6) };
  }
  for (const rsc of curResourceBorrows) {
    rsc[symbolRscHandle] = null;
  }
  curResourceBorrows = [];
  var variant5 = ret;
  switch (variant5.tag) {
    case "ok": {
      const e6 = variant5.val;
      dataView(memory0).setInt8(arg1 + 0, 0, true);
      dataView(memory0).setBigInt64(arg1 + 8, toUint64(e6), true);
      break;
    }
    case "err": {
      const e6 = variant5.val;
      dataView(memory0).setInt8(arg1 + 0, 1, true);
      var variant4 = e6;
      switch (variant4.tag) {
        case "last-operation-failed": {
          const e7 = variant4.val;
          dataView(memory0).setInt8(arg1 + 8, 0, true);
          if (!(e7 instanceof Error$1)) {
            throw new TypeError('Resource error: Not a valid "Error" resource.');
          }
          var handle3 = e7[symbolRscHandle];
          if (!handle3) {
            const rep = e7[symbolRscRep] || ++captureCnt0;
            captureTable0.set(rep, e7);
            handle3 = rscTableCreateOwn(handleTable0, rep);
          }
          dataView(memory0).setInt32(arg1 + 12, handle3, true);
          break;
        }
        case "closed": {
          dataView(memory0).setInt8(arg1 + 8, 1, true);
          break;
        }
        default: {
          throw new TypeError(`invalid variant tag value \`${JSON.stringify(variant4.tag)}\` (received \`${variant4}\`) specified for \`StreamError\``);
        }
      }
      break;
    }
    default: {
      throw new TypeError("invalid variant specified for result");
    }
  }
}
function trampoline24(arg0, arg1, arg2, arg3) {
  var handle1 = arg0;
  var rep2 = handleTable2[(handle1 << 1) + 1] & ~T_FLAG;
  var rsc0 = captureTable2.get(rep2);
  if (!rsc0) {
    rsc0 = Object.create(OutputStream4.prototype);
    Object.defineProperty(rsc0, symbolRscHandle, { writable: true, value: handle1 });
    Object.defineProperty(rsc0, symbolRscRep, { writable: true, value: rep2 });
  }
  curResourceBorrows.push(rsc0);
  var ptr3 = arg1;
  var len3 = arg2;
  var result3 = new Uint8Array(memory0.buffer.slice(ptr3, ptr3 + len3 * 1));
  let ret;
  try {
    ret = { tag: "ok", val: rsc0.write(result3) };
  } catch (e6) {
    ret = { tag: "err", val: getErrorPayload(e6) };
  }
  for (const rsc of curResourceBorrows) {
    rsc[symbolRscHandle] = null;
  }
  curResourceBorrows = [];
  var variant6 = ret;
  switch (variant6.tag) {
    case "ok": {
      const e6 = variant6.val;
      dataView(memory0).setInt8(arg3 + 0, 0, true);
      break;
    }
    case "err": {
      const e6 = variant6.val;
      dataView(memory0).setInt8(arg3 + 0, 1, true);
      var variant5 = e6;
      switch (variant5.tag) {
        case "last-operation-failed": {
          const e7 = variant5.val;
          dataView(memory0).setInt8(arg3 + 4, 0, true);
          if (!(e7 instanceof Error$1)) {
            throw new TypeError('Resource error: Not a valid "Error" resource.');
          }
          var handle4 = e7[symbolRscHandle];
          if (!handle4) {
            const rep = e7[symbolRscRep] || ++captureCnt0;
            captureTable0.set(rep, e7);
            handle4 = rscTableCreateOwn(handleTable0, rep);
          }
          dataView(memory0).setInt32(arg3 + 8, handle4, true);
          break;
        }
        case "closed": {
          dataView(memory0).setInt8(arg3 + 4, 1, true);
          break;
        }
        default: {
          throw new TypeError(`invalid variant tag value \`${JSON.stringify(variant5.tag)}\` (received \`${variant5}\`) specified for \`StreamError\``);
        }
      }
      break;
    }
    default: {
      throw new TypeError("invalid variant specified for result");
    }
  }
}
function trampoline25(arg0, arg1, arg2, arg3) {
  var handle1 = arg0;
  var rep2 = handleTable2[(handle1 << 1) + 1] & ~T_FLAG;
  var rsc0 = captureTable2.get(rep2);
  if (!rsc0) {
    rsc0 = Object.create(OutputStream4.prototype);
    Object.defineProperty(rsc0, symbolRscHandle, { writable: true, value: handle1 });
    Object.defineProperty(rsc0, symbolRscRep, { writable: true, value: rep2 });
  }
  curResourceBorrows.push(rsc0);
  var ptr3 = arg1;
  var len3 = arg2;
  var result3 = new Uint8Array(memory0.buffer.slice(ptr3, ptr3 + len3 * 1));
  let ret;
  try {
    ret = { tag: "ok", val: rsc0.blockingWriteAndFlush(result3) };
  } catch (e6) {
    ret = { tag: "err", val: getErrorPayload(e6) };
  }
  for (const rsc of curResourceBorrows) {
    rsc[symbolRscHandle] = null;
  }
  curResourceBorrows = [];
  var variant6 = ret;
  switch (variant6.tag) {
    case "ok": {
      const e6 = variant6.val;
      dataView(memory0).setInt8(arg3 + 0, 0, true);
      break;
    }
    case "err": {
      const e6 = variant6.val;
      dataView(memory0).setInt8(arg3 + 0, 1, true);
      var variant5 = e6;
      switch (variant5.tag) {
        case "last-operation-failed": {
          const e7 = variant5.val;
          dataView(memory0).setInt8(arg3 + 4, 0, true);
          if (!(e7 instanceof Error$1)) {
            throw new TypeError('Resource error: Not a valid "Error" resource.');
          }
          var handle4 = e7[symbolRscHandle];
          if (!handle4) {
            const rep = e7[symbolRscRep] || ++captureCnt0;
            captureTable0.set(rep, e7);
            handle4 = rscTableCreateOwn(handleTable0, rep);
          }
          dataView(memory0).setInt32(arg3 + 8, handle4, true);
          break;
        }
        case "closed": {
          dataView(memory0).setInt8(arg3 + 4, 1, true);
          break;
        }
        default: {
          throw new TypeError(`invalid variant tag value \`${JSON.stringify(variant5.tag)}\` (received \`${variant5}\`) specified for \`StreamError\``);
        }
      }
      break;
    }
    default: {
      throw new TypeError("invalid variant specified for result");
    }
  }
}
function trampoline26(arg0, arg1) {
  var handle1 = arg0;
  var rep2 = handleTable2[(handle1 << 1) + 1] & ~T_FLAG;
  var rsc0 = captureTable2.get(rep2);
  if (!rsc0) {
    rsc0 = Object.create(OutputStream4.prototype);
    Object.defineProperty(rsc0, symbolRscHandle, { writable: true, value: handle1 });
    Object.defineProperty(rsc0, symbolRscRep, { writable: true, value: rep2 });
  }
  curResourceBorrows.push(rsc0);
  let ret;
  try {
    ret = { tag: "ok", val: rsc0.blockingFlush() };
  } catch (e6) {
    ret = { tag: "err", val: getErrorPayload(e6) };
  }
  for (const rsc of curResourceBorrows) {
    rsc[symbolRscHandle] = null;
  }
  curResourceBorrows = [];
  var variant5 = ret;
  switch (variant5.tag) {
    case "ok": {
      const e6 = variant5.val;
      dataView(memory0).setInt8(arg1 + 0, 0, true);
      break;
    }
    case "err": {
      const e6 = variant5.val;
      dataView(memory0).setInt8(arg1 + 0, 1, true);
      var variant4 = e6;
      switch (variant4.tag) {
        case "last-operation-failed": {
          const e7 = variant4.val;
          dataView(memory0).setInt8(arg1 + 4, 0, true);
          if (!(e7 instanceof Error$1)) {
            throw new TypeError('Resource error: Not a valid "Error" resource.');
          }
          var handle3 = e7[symbolRscHandle];
          if (!handle3) {
            const rep = e7[symbolRscRep] || ++captureCnt0;
            captureTable0.set(rep, e7);
            handle3 = rscTableCreateOwn(handleTable0, rep);
          }
          dataView(memory0).setInt32(arg1 + 8, handle3, true);
          break;
        }
        case "closed": {
          dataView(memory0).setInt8(arg1 + 4, 1, true);
          break;
        }
        default: {
          throw new TypeError(`invalid variant tag value \`${JSON.stringify(variant4.tag)}\` (received \`${variant4}\`) specified for \`StreamError\``);
        }
      }
      break;
    }
    default: {
      throw new TypeError("invalid variant specified for result");
    }
  }
}
function trampoline27(arg0, arg1) {
  const ret = getRandomBytes(BigInt.asUintN(64, arg0));
  var val0 = ret;
  var len0 = val0.byteLength;
  var ptr0 = realloc0(0, 0, 1, len0 * 1);
  var src0 = new Uint8Array(val0.buffer || val0, val0.byteOffset, len0 * 1);
  new Uint8Array(memory0.buffer, ptr0, len0 * 1).set(src0);
  dataView(memory0).setInt32(arg1 + 4, len0, true);
  dataView(memory0).setInt32(arg1 + 0, ptr0, true);
}
function trampoline28(arg0) {
  const ret = getEnvironment();
  var vec3 = ret;
  var len3 = vec3.length;
  var result3 = realloc0(0, 0, 4, len3 * 16);
  for (let i6 = 0; i6 < vec3.length; i6++) {
    const e6 = vec3[i6];
    const base = result3 + i6 * 16;
    var [tuple0_0, tuple0_1] = e6;
    var ptr1 = utf8Encode(tuple0_0, realloc0, memory0);
    var len1 = utf8EncodedLen;
    dataView(memory0).setInt32(base + 4, len1, true);
    dataView(memory0).setInt32(base + 0, ptr1, true);
    var ptr2 = utf8Encode(tuple0_1, realloc0, memory0);
    var len2 = utf8EncodedLen;
    dataView(memory0).setInt32(base + 12, len2, true);
    dataView(memory0).setInt32(base + 8, ptr2, true);
  }
  dataView(memory0).setInt32(arg0 + 4, len3, true);
  dataView(memory0).setInt32(arg0 + 0, result3, true);
}
var handleTable3 = [T_FLAG, 0];
var captureTable3 = /* @__PURE__ */ new Map();
var captureCnt3 = 0;
handleTables[3] = handleTable3;
function trampoline29(arg0) {
  const ret = getTerminalStdin();
  var variant1 = ret;
  if (variant1 === null || variant1 === void 0) {
    dataView(memory0).setInt8(arg0 + 0, 0, true);
  } else {
    const e6 = variant1;
    dataView(memory0).setInt8(arg0 + 0, 1, true);
    if (!(e6 instanceof TerminalInput2)) {
      throw new TypeError('Resource error: Not a valid "TerminalInput" resource.');
    }
    var handle0 = e6[symbolRscHandle];
    if (!handle0) {
      const rep = e6[symbolRscRep] || ++captureCnt3;
      captureTable3.set(rep, e6);
      handle0 = rscTableCreateOwn(handleTable3, rep);
    }
    dataView(memory0).setInt32(arg0 + 4, handle0, true);
  }
}
var handleTable4 = [T_FLAG, 0];
var captureTable4 = /* @__PURE__ */ new Map();
var captureCnt4 = 0;
handleTables[4] = handleTable4;
function trampoline30(arg0) {
  const ret = getTerminalStdout();
  var variant1 = ret;
  if (variant1 === null || variant1 === void 0) {
    dataView(memory0).setInt8(arg0 + 0, 0, true);
  } else {
    const e6 = variant1;
    dataView(memory0).setInt8(arg0 + 0, 1, true);
    if (!(e6 instanceof TerminalOutput2)) {
      throw new TypeError('Resource error: Not a valid "TerminalOutput" resource.');
    }
    var handle0 = e6[symbolRscHandle];
    if (!handle0) {
      const rep = e6[symbolRscRep] || ++captureCnt4;
      captureTable4.set(rep, e6);
      handle0 = rscTableCreateOwn(handleTable4, rep);
    }
    dataView(memory0).setInt32(arg0 + 4, handle0, true);
  }
}
function trampoline31(arg0) {
  const ret = getTerminalStderr();
  var variant1 = ret;
  if (variant1 === null || variant1 === void 0) {
    dataView(memory0).setInt8(arg0 + 0, 0, true);
  } else {
    const e6 = variant1;
    dataView(memory0).setInt8(arg0 + 0, 1, true);
    if (!(e6 instanceof TerminalOutput2)) {
      throw new TypeError('Resource error: Not a valid "TerminalOutput" resource.');
    }
    var handle0 = e6[symbolRscHandle];
    if (!handle0) {
      const rep = e6[symbolRscRep] || ++captureCnt4;
      captureTable4.set(rep, e6);
      handle0 = rscTableCreateOwn(handleTable4, rep);
    }
    dataView(memory0).setInt32(arg0 + 4, handle0, true);
  }
}
var exports32;
var exports42;
var realloc1;
var postReturn0;
var handleTable6 = [T_FLAG, 0];
handleTables[6] = handleTable6;
function trampoline1(handle) {
  const handleEntry = rscTableRemove(handleTable6, handle);
  if (handleEntry.own) {
    throw new TypeError("unreachable resource trampoline");
  }
}
function trampoline2(handle) {
  const handleEntry = rscTableRemove(handleTable0, handle);
  if (handleEntry.own) {
    const rsc = captureTable0.get(handleEntry.rep);
    if (rsc) {
      if (rsc[symbolDispose3]) rsc[symbolDispose3]();
      captureTable0.delete(handleEntry.rep);
    } else if (Error$1[symbolCabiDispose]) {
      Error$1[symbolCabiDispose](handleEntry.rep);
    }
  }
}
function trampoline3(handle) {
  const handleEntry = rscTableRemove(handleTable1, handle);
  if (handleEntry.own) {
    const rsc = captureTable1.get(handleEntry.rep);
    if (rsc) {
      if (rsc[symbolDispose3]) rsc[symbolDispose3]();
      captureTable1.delete(handleEntry.rep);
    } else if (InputStream4[symbolCabiDispose]) {
      InputStream4[symbolCabiDispose](handleEntry.rep);
    }
  }
}
function trampoline4(handle) {
  const handleEntry = rscTableRemove(handleTable2, handle);
  if (handleEntry.own) {
    const rsc = captureTable2.get(handleEntry.rep);
    if (rsc) {
      if (rsc[symbolDispose3]) rsc[symbolDispose3]();
      captureTable2.delete(handleEntry.rep);
    } else if (OutputStream4[symbolCabiDispose]) {
      OutputStream4[symbolCabiDispose](handleEntry.rep);
    }
  }
}
function trampoline5(handle) {
  const handleEntry = rscTableRemove(handleTable5, handle);
  if (handleEntry.own) {
    const rsc = captureTable5.get(handleEntry.rep);
    if (rsc) {
      if (rsc[symbolDispose3]) rsc[symbolDispose3]();
      captureTable5.delete(handleEntry.rep);
    } else if (Descriptor2[symbolCabiDispose]) {
      Descriptor2[symbolCabiDispose](handleEntry.rep);
    }
  }
}
function trampoline6(handle) {
  const handleEntry = rscTableRemove(handleTable4, handle);
  if (handleEntry.own) {
    const rsc = captureTable4.get(handleEntry.rep);
    if (rsc) {
      if (rsc[symbolDispose3]) rsc[symbolDispose3]();
      captureTable4.delete(handleEntry.rep);
    } else if (TerminalOutput2[symbolCabiDispose]) {
      TerminalOutput2[symbolCabiDispose](handleEntry.rep);
    }
  }
}
function trampoline7(handle) {
  const handleEntry = rscTableRemove(handleTable3, handle);
  if (handleEntry.own) {
    const rsc = captureTable3.get(handleEntry.rep);
    if (rsc) {
      if (rsc[symbolDispose3]) rsc[symbolDispose3]();
      captureTable3.delete(handleEntry.rep);
    } else if (TerminalInput2[symbolCabiDispose]) {
      TerminalInput2[symbolCabiDispose](handleEntry.rep);
    }
  }
}
function optimize(arg0, arg1, arg2) {
  var ptr0 = realloc1(0, 0, 8, 200);
  var { k: v1_0, m: v1_1, delta: v1_2, beta: v1_3, sigmaObs: v1_4 } = arg0;
  dataView(memory0).setFloat64(ptr0 + 0, +v1_0, true);
  dataView(memory0).setFloat64(ptr0 + 8, +v1_1, true);
  var val2 = v1_2;
  var len2 = val2.length;
  var ptr2 = realloc1(0, 0, 8, len2 * 8);
  var src2 = new Uint8Array(val2.buffer, val2.byteOffset, len2 * 8);
  new Uint8Array(memory0.buffer, ptr2, len2 * 8).set(src2);
  dataView(memory0).setInt32(ptr0 + 20, len2, true);
  dataView(memory0).setInt32(ptr0 + 16, ptr2, true);
  var val3 = v1_3;
  var len3 = val3.length;
  var ptr3 = realloc1(0, 0, 8, len3 * 8);
  var src3 = new Uint8Array(val3.buffer, val3.byteOffset, len3 * 8);
  new Uint8Array(memory0.buffer, ptr3, len3 * 8).set(src3);
  dataView(memory0).setInt32(ptr0 + 28, len3, true);
  dataView(memory0).setInt32(ptr0 + 24, ptr3, true);
  dataView(memory0).setFloat64(ptr0 + 32, +v1_4, true);
  var ptr4 = utf8Encode(arg1, realloc1, memory0);
  var len4 = utf8EncodedLen;
  dataView(memory0).setInt32(ptr0 + 44, len4, true);
  dataView(memory0).setInt32(ptr0 + 40, ptr4, true);
  var { algorithm: v5_0, seed: v5_1, chain: v5_2, initAlpha: v5_3, tolObj: v5_4, tolRelObj: v5_5, tolGrad: v5_6, tolRelGrad: v5_7, tolParam: v5_8, historySize: v5_9, iter: v5_10, jacobian: v5_11, refresh: v5_12 } = arg2;
  var variant7 = v5_0;
  if (variant7 === null || variant7 === void 0) {
    dataView(memory0).setInt8(ptr0 + 48, 0, true);
  } else {
    const e6 = variant7;
    dataView(memory0).setInt8(ptr0 + 48, 1, true);
    var val6 = e6;
    let enum6;
    switch (val6) {
      case "newton": {
        enum6 = 0;
        break;
      }
      case "bfgs": {
        enum6 = 1;
        break;
      }
      case "lbfgs": {
        enum6 = 2;
        break;
      }
      default: {
        if (e6 instanceof Error) {
          console.error(e6);
        }
        throw new TypeError(`"${val6}" is not one of the cases of algorithm`);
      }
    }
    dataView(memory0).setInt8(ptr0 + 49, enum6, true);
  }
  var variant8 = v5_1;
  if (variant8 === null || variant8 === void 0) {
    dataView(memory0).setInt8(ptr0 + 52, 0, true);
  } else {
    const e6 = variant8;
    dataView(memory0).setInt8(ptr0 + 52, 1, true);
    dataView(memory0).setInt32(ptr0 + 56, toUint32(e6), true);
  }
  var variant9 = v5_2;
  if (variant9 === null || variant9 === void 0) {
    dataView(memory0).setInt8(ptr0 + 60, 0, true);
  } else {
    const e6 = variant9;
    dataView(memory0).setInt8(ptr0 + 60, 1, true);
    dataView(memory0).setInt32(ptr0 + 64, toUint32(e6), true);
  }
  var variant10 = v5_3;
  if (variant10 === null || variant10 === void 0) {
    dataView(memory0).setInt8(ptr0 + 72, 0, true);
  } else {
    const e6 = variant10;
    dataView(memory0).setInt8(ptr0 + 72, 1, true);
    dataView(memory0).setFloat64(ptr0 + 80, +e6, true);
  }
  var variant11 = v5_4;
  if (variant11 === null || variant11 === void 0) {
    dataView(memory0).setInt8(ptr0 + 88, 0, true);
  } else {
    const e6 = variant11;
    dataView(memory0).setInt8(ptr0 + 88, 1, true);
    dataView(memory0).setFloat64(ptr0 + 96, +e6, true);
  }
  var variant12 = v5_5;
  if (variant12 === null || variant12 === void 0) {
    dataView(memory0).setInt8(ptr0 + 104, 0, true);
  } else {
    const e6 = variant12;
    dataView(memory0).setInt8(ptr0 + 104, 1, true);
    dataView(memory0).setFloat64(ptr0 + 112, +e6, true);
  }
  var variant13 = v5_6;
  if (variant13 === null || variant13 === void 0) {
    dataView(memory0).setInt8(ptr0 + 120, 0, true);
  } else {
    const e6 = variant13;
    dataView(memory0).setInt8(ptr0 + 120, 1, true);
    dataView(memory0).setFloat64(ptr0 + 128, +e6, true);
  }
  var variant14 = v5_7;
  if (variant14 === null || variant14 === void 0) {
    dataView(memory0).setInt8(ptr0 + 136, 0, true);
  } else {
    const e6 = variant14;
    dataView(memory0).setInt8(ptr0 + 136, 1, true);
    dataView(memory0).setFloat64(ptr0 + 144, +e6, true);
  }
  var variant15 = v5_8;
  if (variant15 === null || variant15 === void 0) {
    dataView(memory0).setInt8(ptr0 + 152, 0, true);
  } else {
    const e6 = variant15;
    dataView(memory0).setInt8(ptr0 + 152, 1, true);
    dataView(memory0).setFloat64(ptr0 + 160, +e6, true);
  }
  var variant16 = v5_9;
  if (variant16 === null || variant16 === void 0) {
    dataView(memory0).setInt8(ptr0 + 168, 0, true);
  } else {
    const e6 = variant16;
    dataView(memory0).setInt8(ptr0 + 168, 1, true);
    dataView(memory0).setInt32(ptr0 + 172, toUint32(e6), true);
  }
  var variant17 = v5_10;
  if (variant17 === null || variant17 === void 0) {
    dataView(memory0).setInt8(ptr0 + 176, 0, true);
  } else {
    const e6 = variant17;
    dataView(memory0).setInt8(ptr0 + 176, 1, true);
    dataView(memory0).setInt32(ptr0 + 180, toUint32(e6), true);
  }
  var variant18 = v5_11;
  if (variant18 === null || variant18 === void 0) {
    dataView(memory0).setInt8(ptr0 + 184, 0, true);
  } else {
    const e6 = variant18;
    dataView(memory0).setInt8(ptr0 + 184, 1, true);
    dataView(memory0).setInt8(ptr0 + 185, e6 ? 1 : 0, true);
  }
  var variant19 = v5_12;
  if (variant19 === null || variant19 === void 0) {
    dataView(memory0).setInt8(ptr0 + 188, 0, true);
  } else {
    const e6 = variant19;
    dataView(memory0).setInt8(ptr0 + 188, 1, true);
    dataView(memory0).setInt32(ptr0 + 192, toUint32(e6), true);
  }
  const ret = exports1["augurs:prophet-wasmstan/optimizer#optimize"](ptr0);
  let variant29;
  switch (dataView(memory0).getUint8(ret + 0, true)) {
    case 0: {
      var ptr20 = dataView(memory0).getInt32(ret + 8, true);
      var len20 = dataView(memory0).getInt32(ret + 12, true);
      var result20 = utf8Decoder.decode(new Uint8Array(memory0.buffer, ptr20, len20));
      var ptr21 = dataView(memory0).getInt32(ret + 16, true);
      var len21 = dataView(memory0).getInt32(ret + 20, true);
      var result21 = utf8Decoder.decode(new Uint8Array(memory0.buffer, ptr21, len21));
      var ptr22 = dataView(memory0).getInt32(ret + 24, true);
      var len22 = dataView(memory0).getInt32(ret + 28, true);
      var result22 = utf8Decoder.decode(new Uint8Array(memory0.buffer, ptr22, len22));
      var ptr23 = dataView(memory0).getInt32(ret + 32, true);
      var len23 = dataView(memory0).getInt32(ret + 36, true);
      var result23 = utf8Decoder.decode(new Uint8Array(memory0.buffer, ptr23, len23));
      var ptr24 = dataView(memory0).getInt32(ret + 40, true);
      var len24 = dataView(memory0).getInt32(ret + 44, true);
      var result24 = utf8Decoder.decode(new Uint8Array(memory0.buffer, ptr24, len24));
      var ptr25 = dataView(memory0).getInt32(ret + 64, true);
      var len25 = dataView(memory0).getInt32(ret + 68, true);
      var result25 = new Float64Array(memory0.buffer.slice(ptr25, ptr25 + len25 * 8));
      var ptr26 = dataView(memory0).getInt32(ret + 72, true);
      var len26 = dataView(memory0).getInt32(ret + 76, true);
      var result26 = new Float64Array(memory0.buffer.slice(ptr26, ptr26 + len26 * 8));
      var ptr27 = dataView(memory0).getInt32(ret + 88, true);
      var len27 = dataView(memory0).getInt32(ret + 92, true);
      var result27 = new Float64Array(memory0.buffer.slice(ptr27, ptr27 + len27 * 8));
      variant29 = {
        tag: "ok",
        val: {
          logs: {
            debug: result20,
            info: result21,
            warn: result22,
            error: result23,
            fatal: result24
          },
          params: {
            k: dataView(memory0).getFloat64(ret + 48, true),
            m: dataView(memory0).getFloat64(ret + 56, true),
            delta: result25,
            beta: result26,
            sigmaObs: dataView(memory0).getFloat64(ret + 80, true),
            trend: result27
          }
        }
      };
      break;
    }
    case 1: {
      var ptr28 = dataView(memory0).getInt32(ret + 8, true);
      var len28 = dataView(memory0).getInt32(ret + 12, true);
      var result28 = utf8Decoder.decode(new Uint8Array(memory0.buffer, ptr28, len28));
      variant29 = {
        tag: "err",
        val: result28
      };
      break;
    }
    default: {
      throw new TypeError("invalid variant discriminant for expected");
    }
  }
  const retVal = variant29;
  postReturn0(ret);
  if (typeof retVal === "object" && retVal.tag === "err") {
    throw new ComponentError(retVal.val);
  }
  return retVal.val;
}
var $init = (() => {
  let gen = (function* init() {
    const module0 = fetchCompile(new URL("./prophet-wasmstan.core.wasm", import.meta.url));
    const module1 = fetchCompile(new URL("./prophet-wasmstan.core2.wasm", import.meta.url));
    const module2 = base64Compile("AGFzbQEAAAABSQxgAX8AYAJ/fwBgAn9/AX9gA39+fwBgBH9/f38Bf2AEf39/fwBgA39+fwF/YAF/AX9gA39/fwF/YAR/fn9/AX9gAAF/YAJ+fwADIiECAgYHAgIIBAkEAAoCAAABAQMDAQEBAwMBBQUBCwAAAAAEBQFwASEhB6cBIgEwAAABMQABATIAAgEzAAMBNAAEATUABQE2AAYBNwAHATgACAE5AAkCMTAACgIxMQALAjEyAAwCMTMADQIxNAAOAjE1AA8CMTYAEAIxNwARAjE4ABICMTkAEwIyMAAUAjIxABUCMjIAFgIyMwAXAjI0ABgCMjUAGQIyNgAaAjI3ABsCMjgAHAIyOQAdAjMwAB4CMzEAHwIzMgAgCCRpbXBvcnRzAQAKmQMhCwAgACABQQARAgALCwAgACABQQERAgALDQAgACABIAJBAhEGAAsJACAAQQMRBwALCwAgACABQQQRAgALCwAgACABQQURAgALDQAgACABIAJBBhEIAAsPACAAIAEgAiADQQcRBAALDwAgACABIAIgA0EIEQkACw8AIAAgASACIANBCREEAAsJACAAQQoRAAALBwBBCxEKAAsLACAAIAFBDBECAAsJACAAQQ0RAAALCQAgAEEOEQAACwsAIAAgAUEPEQEACwsAIAAgAUEQEQEACw0AIAAgASACQRERAwALDQAgACABIAJBEhEDAAsLACAAIAFBExEBAAsLACAAIAFBFBEBAAsLACAAIAFBFREBAAsNACAAIAEgAkEWEQMACw0AIAAgASACQRcRAwALCwAgACABQRgRAQALDwAgACABIAIgA0EZEQUACw8AIAAgASACIANBGhEFAAsLACAAIAFBGxEBAAsLACAAIAFBHBELAAsJACAAQR0RAAALCQAgAEEeEQAACwkAIABBHxEAAAsJACAAQSARAAALAC8JcHJvZHVjZXJzAQxwcm9jZXNzZWQtYnkBDXdpdC1jb21wb25lbnQHMC4yMTkuMQ");
    const module3 = base64Compile("AGFzbQEAAAABSQxgAX8AYAJ/fwBgAn9/AX9gA39+fwBgBH9/f38Bf2AEf39/fwBgA39+fwF/YAF/AX9gA39/fwF/YAR/fn9/AX9gAAF/YAJ+fwACzAEiAAEwAAIAATEAAgABMgAGAAEzAAcAATQAAgABNQACAAE2AAgAATcABAABOAAJAAE5AAQAAjEwAAAAAjExAAoAAjEyAAIAAjEzAAAAAjE0AAAAAjE1AAEAAjE2AAEAAjE3AAMAAjE4AAMAAjE5AAEAAjIwAAEAAjIxAAEAAjIyAAMAAjIzAAMAAjI0AAEAAjI1AAUAAjI2AAUAAjI3AAEAAjI4AAsAAjI5AAAAAjMwAAAAAjMxAAAAAjMyAAAACCRpbXBvcnRzAXABISEJJwEAQQALIQABAgMEBQYHCAkKCwwNDg8QERITFBUWFxgZGhscHR4fIAAvCXByb2R1Y2VycwEMcHJvY2Vzc2VkLWJ5AQ13aXQtY29tcG9uZW50BzAuMjE5LjE");
    const module4 = base64Compile("AGFzbQEAAAABBAFgAAACBQEAAAAACAEA");
    ({ exports: exports0 } = yield instantiateCore(yield module2));
    ({ exports: exports1 } = yield instantiateCore(yield module0, {
      wasi_snapshot_preview1: {
        clock_time_get: exports0["2"],
        environ_get: exports0["0"],
        environ_sizes_get: exports0["1"],
        fd_close: exports0["3"],
        fd_fdstat_get: exports0["4"],
        fd_prestat_dir_name: exports0["6"],
        fd_prestat_get: exports0["5"],
        fd_read: exports0["7"],
        fd_seek: exports0["8"],
        fd_write: exports0["9"],
        proc_exit: exports0["10"],
        random_get: exports0["12"],
        sched_yield: exports0["11"]
      }
    }));
    ({ exports: exports22 } = yield instantiateCore(yield module1, {
      __main_module__: {
        cabi_realloc: exports1.cabi_realloc
      },
      env: {
        memory: exports1.memory
      },
      "wasi:cli/environment@0.2.0": {
        "get-environment": exports0["29"]
      },
      "wasi:cli/exit@0.2.0": {
        exit: trampoline9
      },
      "wasi:cli/stderr@0.2.0": {
        "get-stderr": trampoline8
      },
      "wasi:cli/stdin@0.2.0": {
        "get-stdin": trampoline10
      },
      "wasi:cli/stdout@0.2.0": {
        "get-stdout": trampoline11
      },
      "wasi:cli/terminal-input@0.2.0": {
        "[resource-drop]terminal-input": trampoline7
      },
      "wasi:cli/terminal-output@0.2.0": {
        "[resource-drop]terminal-output": trampoline6
      },
      "wasi:cli/terminal-stderr@0.2.0": {
        "get-terminal-stderr": exports0["32"]
      },
      "wasi:cli/terminal-stdin@0.2.0": {
        "get-terminal-stdin": exports0["30"]
      },
      "wasi:cli/terminal-stdout@0.2.0": {
        "get-terminal-stdout": exports0["31"]
      },
      "wasi:clocks/monotonic-clock@0.2.0": {
        now: trampoline0
      },
      "wasi:clocks/wall-clock@0.2.0": {
        now: exports0["14"]
      },
      "wasi:filesystem/preopens@0.2.0": {
        "get-directories": exports0["13"]
      },
      "wasi:filesystem/types@0.2.0": {
        "[method]descriptor.append-via-stream": exports0["19"],
        "[method]descriptor.get-flags": exports0["20"],
        "[method]descriptor.get-type": exports0["15"],
        "[method]descriptor.read-via-stream": exports0["17"],
        "[method]descriptor.stat": exports0["21"],
        "[method]descriptor.write-via-stream": exports0["18"],
        "[resource-drop]descriptor": trampoline5,
        "[resource-drop]directory-entry-stream": trampoline1,
        "filesystem-error-code": exports0["16"]
      },
      "wasi:io/error@0.2.0": {
        "[resource-drop]error": trampoline2
      },
      "wasi:io/streams@0.2.0": {
        "[method]input-stream.blocking-read": exports0["23"],
        "[method]input-stream.read": exports0["22"],
        "[method]output-stream.blocking-flush": exports0["27"],
        "[method]output-stream.blocking-write-and-flush": exports0["26"],
        "[method]output-stream.check-write": exports0["24"],
        "[method]output-stream.write": exports0["25"],
        "[resource-drop]input-stream": trampoline3,
        "[resource-drop]output-stream": trampoline4
      },
      "wasi:random/random@0.2.0": {
        "get-random-bytes": exports0["28"]
      }
    }));
    memory0 = exports1.memory;
    realloc0 = exports22.cabi_import_realloc;
    ({ exports: exports32 } = yield instantiateCore(yield module3, {
      "": {
        $imports: exports0.$imports,
        "0": exports22.environ_get,
        "1": exports22.environ_sizes_get,
        "10": exports22.proc_exit,
        "11": exports22.sched_yield,
        "12": exports22.random_get,
        "13": trampoline12,
        "14": trampoline13,
        "15": trampoline14,
        "16": trampoline15,
        "17": trampoline16,
        "18": trampoline17,
        "19": trampoline18,
        "2": exports22.clock_time_get,
        "20": trampoline19,
        "21": trampoline20,
        "22": trampoline21,
        "23": trampoline22,
        "24": trampoline23,
        "25": trampoline24,
        "26": trampoline25,
        "27": trampoline26,
        "28": trampoline27,
        "29": trampoline28,
        "3": exports22.fd_close,
        "30": trampoline29,
        "31": trampoline30,
        "32": trampoline31,
        "4": exports22.fd_fdstat_get,
        "5": exports22.fd_prestat_get,
        "6": exports22.fd_prestat_dir_name,
        "7": exports22.fd_read,
        "8": exports22.fd_seek,
        "9": exports22.fd_write
      }
    }));
    ({ exports: exports42 } = yield instantiateCore(yield module4, {
      "": {
        "": exports1._initialize
      }
    }));
    realloc1 = exports1.cabi_realloc;
    postReturn0 = exports1["cabi_post_augurs:prophet-wasmstan/optimizer#optimize"];
  })();
  function run(g5) {
    return Promise.resolve((function step(v6) {
      const res = g5.next(v6);
      if (res.done) return res.value;
      return res.value.then(step);
    })());
  }
  return run(gen);
})();
await $init;
var optimizer = {
  optimize
};
export {
  optimizer as "augurs:prophet-wasmstan/optimizer",
  optimizer
};
/*! Bundled license information:

@jspm/core/nodelibs/browser/chunk-DtuTasat.js:
@jspm/core/nodelibs/browser/chunk-B738Er4n.js:
  (*! ieee754. BSD-3-Clause License. Feross Aboukhadijeh <https://feross.org/opensource> *)

@jspm/core/nodelibs/browser/chunk-CjPlbOtt.js:
  (*!
   * The buffer module from node.js, for the browser.
   *
   * @author   Feross Aboukhadijeh <feross@feross.org> <http://feross.org>
   * @license  MIT
   *)
*/
