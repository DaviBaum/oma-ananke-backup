// Deliberately small, synthetic stock-cutting demonstration. Not Hospital quantities.
// Integer millimetres keep coverage and kerf accounting exact.
export const sampleTypes = {
  plumbing: { label: "Plumbing pipe", rate: 18, color: "#447eaf" },
  hvac: { label: "Round duct", rate: 26, color: "#2e8b79" },
  electrical: { label: "Electrical conduit", rate: 9, color: "#b98632" },
  fire: { label: "Sprinkler pipe", rate: 22, color: "#be675d" },
};
export function samplePieces(type = "plumbing") {
  if (!sampleTypes[type]) throw new Error("Select a sample discipline.");
  const lengths = [1820, 1420, 2610, 840, 2160, 1220, 650, 2780];
  return Array.from({ length: 48 }, (_, i) => ({
    id: `piece-${i + 1}`,
    batch: Math.floor(i / 4),
    length: lengths[i % lengths.length],
  }));
}
function pack(pieces, stock, kerf, pooled) {
  const bins = [];
  for (const piece of [...pieces].sort(
    (a, b) => b.length - a.length || a.id.localeCompare(b.id),
  )) {
    const options = bins.filter(
      (b) =>
        (pooled || b.batch === piece.batch) &&
        b.used + piece.length + kerf <= stock,
    );
    const bin = pooled
      ? options.sort((a, b) => b.used - a.used)[0]
      : options[0];
    const chosen = bin || { batch: piece.batch, used: 0, cuts: [] };
    if (!bin) bins.push(chosen);
    chosen.cuts.push({ ...piece });
    chosen.used += piece.length + kerf;
  }
  return bins;
}
export function calculateScenario({
  type = "plumbing",
  stockM = 6,
  price = 18,
  kerfMm = 3,
} = {}) {
  if (
    !sampleTypes[type] ||
    ![3, 6, 12].includes(Number(stockM)) ||
    !Number.isFinite(Number(price)) ||
    price < 0 ||
    price > 1000 ||
    ![0, 3, 5].includes(Number(kerfMm))
  ) {
    throw new Error("Invalid scenario inputs.");
  }
  const stock = Number(stockM) * 1000,
    kerf = Number(kerfMm),
    pieces = samplePieces(type);
  if (pieces.some((p) => p.length + kerf > stock))
    throw new Error("A piece exceeds the selected stock length.");
  const before = pack(pieces, stock, kerf, false),
    pooled = pack(pieces, stock, kerf, true);
  const after = pooled.length <= before.length ? pooled : before;
  for (const bins of [before, after]) {
    const ids = bins.flatMap((b) => b.cuts.map((p) => p.id));
    if (
      ids.length !== pieces.length ||
      new Set(ids).size !== pieces.length ||
      bins.some((b) => b.used > stock)
    )
      throw new Error("Cut-plan verification failed.");
  }
  const required = pieces.reduce((a, p) => a + p.length, 0) / 1000;
  const totals = (bins) => ({
    bars: bins.length,
    purchasedM: bins.length * Number(stockM),
    wasteM: bins.length * Number(stockM) - required,
    cost: bins.length * Number(stockM) * Number(price),
  });
  const baseline = totals(before),
    selected = totals(after);
  return {
    type,
    label: sampleTypes[type].label,
    stockM: Number(stockM),
    price: Number(price),
    kerfMm: kerf,
    pieces,
    before,
    after,
    baseline,
    selected,
    requiredM: required,
    savedM: baseline.purchasedM - selected.purchasedM,
    savedCost: baseline.cost - selected.cost,
    savedPercent:
      ((baseline.purchasedM - selected.purchasedM) / baseline.purchasedM) * 100,
    verified: true,
    scope:
      "Synthetic 48-piece demonstration, grouped into 12 purchasing batches. Pooled best-fit decreasing compared with batch-wise first-fit decreasing. Feasible heuristic; global optimality not claimed. All lengths and unit prices are illustrative inputs. Gross stock-material difference only; labor, end preparation, connections, and delivery excluded. No Hospital savings or engineering approval inferred.",
  };
}
export function inspectIfcText(text, filename) {
  if (
    !text.trimStart().startsWith("ISO-10303-21;") ||
    !/FILE_SCHEMA\s*\(/i.test(text)
  )
    throw new Error("This file is not a recognizable IFC STEP file.");
  const schema =
    text.match(/FILE_SCHEMA\s*\(\s*\(\s*'([^']+)'/i)?.[1] || "Unknown";
  const counts = {};
  for (const match of text.matchAll(
    /(?:^|[;\r\n])\s*#\d+\s*=\s*(IFC[A-Z0-9_]+)\s*\(/g,
  ))
    counts[match[1]] = (counts[match[1]] || 0) + 1;
  return {
    filename,
    schema,
    records: Object.values(counts).reduce((a, n) => a + n, 0),
    classes: Object.entries(counts).sort((a, b) => b[1] - a[1]),
    scope:
      "Browser-local STEP record scan only; not a semantic IFC import, geometry load or engineering check.",
  };
}
