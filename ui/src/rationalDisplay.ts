/** Display only. Directional decimal rounding preserves an interval's enclosure. */
export function rationalDecimal(
  value: unknown,
  places = 6,
  direction: "lower" | "upper" | "nearest" = "nearest",
): string {
  if (typeof value === "number")
    return Number.isFinite(value)
      ? value.toLocaleString("en-US", { maximumFractionDigits: places })
      : "Not reported";
  if (
    typeof value !== "string" ||
    value.length > 10000 ||
    !/^-?\d+(\/-?\d+)?$/.test(value)
  )
    return "Not reported";
  const [a, b = "1"] = value.split("/");
  let n = BigInt(a),
    d = BigInt(b);
  if (!d) return "Not reported";
  if (d < 0n) {
    n = -n;
    d = -d;
  }
  const scale = 10n ** BigInt(places),
    scaled = n * scale,
    remainder = scaled % d;
  let rounded = scaled / d;
  if (direction === "lower" && remainder < 0n) rounded--;
  if (direction === "upper" && remainder > 0n) rounded++;
  if (
    direction === "nearest" &&
    (remainder < 0n ? -remainder : remainder) * 2n >= d
  )
    rounded += n < 0n ? -1n : 1n;
  const negative = rounded < 0n,
    absolute = negative ? -rounded : rounded,
    integer = absolute / scale;
  if (integer.toString().length > 18) return "See exact value";
  const fraction = (absolute % scale)
    .toString()
    .padStart(places, "0")
    .replace(/0+$/, "");
  return `${negative ? "−" : ""}${integer.toLocaleString("en-US")}${fraction ? `.${fraction}` : ""}`;
}

export function intervalDecimal(value: unknown, places = 3): string {
  if (!value || typeof value !== "object") return "Not reported";
  const v = value as Record<string, unknown>;
  if (typeof v.lower !== "string" || typeof v.upper !== "string")
    return "Not reported";
  const lower = rationalDecimal(v.lower, places, "lower"),
    upper = rationalDecimal(v.upper, places, "upper");
  if (lower === "Not reported" || upper === "Not reported")
    return "Not reported";
  return lower === upper ? lower : `${lower} to ${upper}`;
}
