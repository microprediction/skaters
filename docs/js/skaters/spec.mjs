// Symbolic spec for skater pipelines — JS port of skaters/spec.py.

import { leaf } from "./leaf.mjs";
import { ema } from "./ema.mjs";
import { precisionWeightedEnsemble } from "./ensemble.mjs";
import { conjugate } from "./conjugate.mjs";
import { difference, fractionalDifference, standardize, emaTransform } from "./transform.mjs";

export function build(spec) {
  const op = spec.op;
  let f;
  if (op === "leaf") {
    f = leaf(spec.k);
  } else if (op === "ema") {
    f = ema(spec.alpha, spec.k);
  } else if (op === "ensemble") {
    const subs = spec.skaters.map(build);
    f = precisionWeightedEnsemble(subs, spec.k, spec.floor === undefined ? 1e-6 : spec.floor);
  } else if (op === "conjugate") {
    const inner = build(spec.skater);
    const t = buildTransform(spec.transform);
    f = conjugate(inner, t, inferK(spec.skater));
  } else {
    throw new Error(`Unknown op: ${op}`);
  }
  f.skaterName = name(spec);
  return f;
}

function buildTransform(spec) {
  const op = spec.op;
  if (op === "diff") return difference();
  if (op === "frac") return fractionalDifference(spec.d, spec.window === undefined ? 50 : spec.window);
  if (op === "std") return standardize(spec.alpha === undefined ? 0.05 : spec.alpha);
  if (op === "ema_t") return emaTransform(spec.alpha);
  throw new Error(`Unknown transform op: ${op}`);
}

function inferK(spec) {
  if ("k" in spec) return spec.k;
  if ("skater" in spec) return inferK(spec.skater);
  if ("skaters" in spec) return inferK(spec.skaters[0]);
  throw new Error("Cannot infer k from spec");
}

// --- canonical name ---

function fmt(x) {
  // Python's _fmt: str(int(x)) when integral, else "%.6g".
  if (x === Math.trunc(x)) return Math.abs(x) < 1e21 ? String(Math.trunc(x)) : BigInt(x).toString();
  const [mant, expStr] = x.toExponential(5).split("e");   // 6 significant digits
  const exp = Number(expStr);
  const strip = (t) => (t.indexOf(".") >= 0 ? t.replace(/0+$/, "").replace(/\.$/, "") : t);
  if (exp < -4 || exp >= 6) {
    const e = Math.abs(exp) < 10 ? `0${Math.abs(exp)}` : `${Math.abs(exp)}`;
    return `${strip(mant)}e${exp < 0 ? "-" : "+"}${e}`;
  }
  return strip(x.toFixed(5 - exp));
}

export function name(spec) {
  const op = spec.op;
  if (op === "leaf") return "leaf";
  if (op === "ema") return `ema(${fmt(spec.alpha)})`;
  if (op === "ensemble") return `ensemble(${spec.skaters.map(name).join(",")})`;
  if (op === "conjugate") return `${transformName(spec.transform)}|${name(spec.skater)}`;
  throw new Error(`Unknown op: ${op}`);
}

function transformName(spec) {
  const op = spec.op;
  if (op === "diff") return "diff";
  if (op === "frac") {
    const w = spec.window === undefined ? 50 : spec.window;
    return w === 50 ? `frac(${fmt(spec.d)})` : `frac(${fmt(spec.d)},w=${w})`;
  }
  if (op === "std") return `std(${fmt(spec.alpha === undefined ? 0.05 : spec.alpha)})`;
  if (op === "ema_t") return `ema_t(${fmt(spec.alpha)})`;
  throw new Error(`Unknown transform op: ${op}`);
}

// --- serialization ---

// Python's json.dumps(spec, separators=(",", ":")), byte for byte. JSON.stringify
// differs in two ways: number formatting (Python writes 1e-05 and 0.1 where JS
// writes 0.00001 and 0.1, and 1.0 where JS writes 1), and non-ASCII escaping.
// JS numbers carry no int/float distinction, so the spec grammar decides: the
// float fields (alpha, d, floor) are written as Python floats, every other
// integral number as an int.
const FLOAT_FIELDS = new Set(["alpha", "d", "floor"]);

export function pyFloatRepr(x) {
  if (Number.isNaN(x)) return "NaN";
  if (x === Infinity) return "Infinity";
  if (x === -Infinity) return "-Infinity";
  if (x === 0) return Object.is(x, -0) ? "-0.0" : "0.0";
  // Shortest round-trip digits, as both languages choose them.
  const [mant, expStr] = x.toExponential().split("e");
  const exp = Number(expStr);
  const neg = mant.startsWith("-");
  const digits = mant.replace("-", "").replace(".", "");
  const sign = neg ? "-" : "";
  if (exp >= -4 && exp < 16) {
    if (exp >= digits.length - 1) return `${sign}${digits}${"0".repeat(exp - digits.length + 1)}.0`;
    if (exp >= 0) return `${sign}${digits.slice(0, exp + 1)}.${digits.slice(exp + 1)}`;
    return `${sign}0.${"0".repeat(-exp - 1)}${digits}`;
  }
  const m = digits.length > 1 ? `${digits[0]}.${digits.slice(1)}` : digits;
  const e = Math.abs(exp) < 10 ? `0${Math.abs(exp)}` : `${Math.abs(exp)}`;
  return `${sign}${m}e${exp < 0 ? "-" : "+"}${e}`;
}

function pyString(str) {
  let out = '"';
  for (const ch of str) {
    const c = ch.codePointAt(0);
    if (ch === '"') out += '\\"';
    else if (ch === "\\") out += "\\\\";
    else if (ch === "\n") out += "\\n";
    else if (ch === "\r") out += "\\r";
    else if (ch === "\t") out += "\\t";
    else if (ch === "\b") out += "\\b";
    else if (ch === "\f") out += "\\f";
    else if (c < 0x20 || (c > 0x7e && c <= 0xffff)) out += "\\u" + c.toString(16).padStart(4, "0");
    else if (c > 0xffff) {
      const v = c - 0x10000;
      out += "\\u" + (0xd800 + (v >> 10)).toString(16) + "\\u" + (0xdc00 + (v & 0x3ff)).toString(16);
    } else out += ch;
  }
  return out + '"';
}

function pyDumps(v, key) {
  if (v === null || v === undefined) return "null";
  if (v === true) return "true";
  if (v === false) return "false";
  if (typeof v === "number") {
    if (Number.isInteger(v) && !FLOAT_FIELDS.has(key)) return String(v);
    return pyFloatRepr(v);
  }
  if (typeof v === "string") return pyString(v);
  if (Array.isArray(v)) return "[" + v.map((x) => pyDumps(x, key)).join(",") + "]";
  return "{" + Object.keys(v).map((kk) => `${pyString(kk)}:${pyDumps(v[kk], kk)}`).join(",") + "}";
}

export function toJson(spec) {
  return pyDumps(spec, null);
}

export function fromJson(s) {
  return JSON.parse(s);
}

// --- spec constructors ---

export const leafSpec = (k = 1) => ({ op: "leaf", k });
export const emaSpec = (alpha = 0.05, k = 1) => ({ op: "ema", alpha, k });
export const ensembleSpec = (skaterSpecs, k = 1) => ({ op: "ensemble", k, skaters: skaterSpecs });
export const conjugateSpec = (skaterSpec, transformSpec) => ({ op: "conjugate", skater: skaterSpec, transform: transformSpec });
export const diffSpec = () => ({ op: "diff" });
export const fracSpec = (d = 0.4, window = 50) => ({ op: "frac", d, window });
export const stdSpec = (alpha = 0.05) => ({ op: "std", alpha });
export const emaTSpec = (alpha = 0.05) => ({ op: "ema_t", alpha });
