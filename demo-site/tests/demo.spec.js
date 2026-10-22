import { test, expect } from "@playwright/test";
import fs from "node:fs/promises";

async function readDownload(page, action) {
  const pending = page.waitForEvent("download");
  await action();
  const download = await pending;
  return JSON.parse(await fs.readFile(await download.path(), "utf8"));
}

async function expectNoPageOverflow(page) {
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
}

test("hospital comparisons preserve their baseline, scope and downloadable evidence", async ({ page }) => {
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "The hospital. Less waste." })).toBeVisible();
  await expect(page.locator(".hero-result")).toContainText("$35,064");
  await expect(page.locator(".hero-budget-note")).toHaveText("Materials only. This is not the hospital construction budget.");
  await expect(page.locator(".hero-budget-note")).toBeVisible();
  await expect(page.locator(".budget-scope")).toBeVisible();
  await expect(page.locator(".budget-scope")).toContainText("labor");
  await expect(page.locator(".order-panel .price-scope")).toHaveCount(2);
  for (const panel of ["before", "after"]) {
    await expect(page.locator(`.order-panel.${panel} .price-scope`)).toBeVisible();
    await expect(page.locator(`.order-panel.${panel} .price-scope`)).toHaveText("Pipe, duct, conduit & tray only");
  }
  await expect(page.locator(".hero-note")).toContainText("Engineering review required");
  await expect(page.locator(".order-panel.before")).toContainText("$556,774");
  await expect(page.locator(".order-panel.after")).toContainText("$521,710");
  await expect(page.locator(".saving-line")).toContainText("$35,064");

  await expect(page.locator("canvas")).toBeVisible();
  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({ path: "qa/hospital-desktop.png", fullPage: true });
  const heating = page.getByRole("button", { name: "Heating & cooling", exact: true });
  await heating.click();
  await expect(heating).toHaveAttribute("aria-pressed", "false");
  await heating.click();
  await expect(heating).toHaveAttribute("aria-pressed", "true");
  await page.getByLabel("Visible building level").selectOption("2");
  await expect(page.getByLabel("Visible building level")).toHaveValue("2");
  await page.getByRole("button", { name: "Separate floors", exact: true }).click();
  await expect(page.getByRole("button", { name: "Separate floors", exact: true })).toHaveAttribute("aria-pressed", "true");
  await page.getByRole("button", { name: "Reset camera", exact: true }).click();
  await page.getByRole("button", { name: "Expand viewer", exact: true }).click();
  await expect(page.locator(".model-panel")).toHaveClass(/expanded/);
  await page.keyboard.press("Escape");
  await expect(page.locator(".model-panel")).not.toHaveClass(/expanded/);

  await page.getByRole("button", { name: "Orders already combined", exact: true }).click();
  await expect(page.locator(".saving-line")).toContainText("$292");
  await expect(page.locator(".hero-result")).toContainText("$292");
  await expect(page.locator(".order-panel.before")).toContainText("$522,002");
  await expect(page.locator(".comparison-footnote")).toContainText("3,457 added joints");
  await page.getByLabel("Purchasing option").selectOption("noSplice");
  await expect(page.locator(".saving-line")).toContainText("$761");
  await expect(page.locator(".comparison-footnote")).toContainText("2,113 longer sections");
  await page.getByRole("button", { name: "Separate orders", exact: true }).click();
  await expect(page.locator(".saving-line")).toContainText("$29,405");
  await expect(page.locator(".comparison-footnote")).toContainText("16,446 measured sections");
  await expect(page.locator(".hero-result")).toContainText("$29,405");
  await expect(page.locator(".study-strip")).toContainText("16,446");

  await page.getByLabel("Purchasing option").selectOption("broad");
  await expect(page.locator(".trade-table tbody tr")).toHaveCount(4);
  await page.getByRole("link", { name: "Compare Electrical", exact: true }).click();
  await expect(page.locator(".comparison-context")).toContainText("Electrical");
  await expect(page.locator(".order-panel.before")).toContainText("$16,833");
  await expect(page.locator(".order-panel.after")).toContainText("$16,749");
  await expect(page.locator(".saving-line")).toContainText("$84");
  await expect(page.locator(".trade-table tfoot")).toContainText("$35,064");
  await page.getByRole("button", { name: "Show all trades", exact: true }).click();
  await expect(page.locator(".saving-line")).toContainText("$35,064");

  await page.locator(".review-details summary").click();
  await expect(page.locator(".review-body")).toContainText("Neither plan is cleared for construction or confirmed code-compliant");
  await expect(page.locator(".review-body")).toContainText("149 new cut pieces");
  await page.locator(".source-details summary").click();
  await expect(page.locator(".source-list")).toContainText("793 could not be measured");
  await expect(page.locator(".source-list > div")).toHaveCount(7);

  const report = await readDownload(page, () => page.locator("header.site-header").getByRole("button", { name: "Download study", exact: true }).click());
  expect(report.hospital.productCount).toBe(149822);
  expect(report.hospital.review.constructionApproved).toBe(false);
  expect(report.selectedComparison.scenarioId).toBe("broad");
  expect(report.selectedComparison.baselineId).toBe("perNetwork");
  expect(report.selectedComparison.savings.costUsd).toBeCloseTo(35063.93428, 2);
  expect(errors).toEqual([]);
});

test("sample calculator saves, restores and downloads cuts; file preview stays scoped", async ({ page }) => {
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.goto("/");
  await page.getByRole("button", { name: "Open cost calculator", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toContainText("48 sample pieces are separate from the hospital");
  await expect(dialog.locator(".sample-saving")).toHaveText("$972");
  await dialog.getByRole("spinbutton", { name: "Material price per metre" }).fill("30");
  await dialog.getByRole("button", { name: "Calculate savings", exact: true }).click();
  await expect(dialog.locator(".sample-saving")).toHaveText("$1,620");
  await dialog.getByRole("button", { name: "Save calculation", exact: true }).click();
  await page.screenshot({ path: "qa/calculator-desktop.png", fullPage: true });
  await page.reload();
  await page.getByRole("button", { name: "Open cost calculator", exact: true }).click();
  await dialog.locator(".saved-calculations summary").click();
  await expect(dialog.locator(".saved-calculations button")).toHaveCount(1);
  await dialog.locator(".saved-calculations button").click();
  await expect(dialog.locator(".sample-saving")).toHaveText("$1,620");
  await expect(dialog.getByRole("spinbutton", { name: "Material price per metre" })).toHaveValue("30");
  const cuts = await readDownload(page, () => dialog.getByRole("button", { name: "Download cuts", exact: true }).click());
  expect(cuts.savedCost).toBe(1620);
  expect(cuts.pieces).toHaveLength(48);
  expect(cuts.after.flatMap(stock => stock.cuts)).toHaveLength(48);
  expect(cuts.after.every(stock => stock.used <= cuts.stockM * 1000)).toBe(true);
  await dialog.getByRole("button", { name: "Close dialog", exact: true }).click();

  await page.getByRole("button", { name: "Open a building file", exact: true }).click();
  await expect(dialog).toContainText("file stays in this browser");
  await page.locator("input[type=file]").setInputFiles({
    name: "demo.ifc", mimeType: "text/plain",
    buffer: Buffer.from("ISO-10303-21;\nHEADER;FILE_SCHEMA(('IFC4'));ENDSEC;\nDATA;\n#1=IFCWALL();\n#2=IFCPIPESEGMENT();\nENDSEC;END-ISO-10303-21;")
  });
  await expect(dialog.locator(".file-result")).toContainText("2 file records");
  await expect(dialog.locator(".file-result")).toContainText("IFC4");
  await page.locator("input[type=file]").setInputFiles({ name: "invalid.ifc", mimeType: "text/plain", buffer: Buffer.from("not an IFC file") });
  await expect(dialog.getByRole("alert")).toContainText("not a recognizable IFC");
  await expect(dialog.locator(".file-result")).toHaveCount(0);
  await expect(dialog).toContainText("does not import geometry");
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  expect(errors).toEqual([]);
});

test("mobile comparisons, navigation and calculator remain usable without page overflow", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await expect(page.locator("canvas")).toBeVisible();
  await page.evaluate(() => document.fonts.ready);
  await expect(page.locator(".hero-budget-note")).toBeVisible();
  await expect(page.locator(".hero-budget-note")).toContainText("not the hospital construction budget");
  await expect(page.locator(".budget-scope")).toBeVisible();
  await expect(page.locator(".order-panel.before .price-scope")).toBeVisible();
  await expect(page.locator(".order-panel.after .price-scope")).toBeVisible();
  await expectNoPageOverflow(page);
  await page.screenshot({ path: "qa/hospital-mobile.png", fullPage: true });
  await page.getByRole("button", { name: "Open navigation", exact: true }).click();
  await page.getByRole("navigation", { name: "Main navigation" }).getByRole("link", { name: "Before & after", exact: true }).click();
  await expect(page.getByRole("button", { name: "Open navigation", exact: true })).toHaveAttribute("aria-expanded", "false");
  await page.getByRole("button", { name: "Orders already combined", exact: true }).click();
  await expect(page.locator(".saving-line")).toContainText("$292");
  await page.getByLabel("Purchasing option").selectOption("noSplice");
  await expect(page.locator(".saving-line")).toContainText("$761");
  await expectNoPageOverflow(page);
  await page.getByRole("button", { name: "Open cost calculator", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Length sold by the supplier").selectOption("3");
  await dialog.getByRole("button", { name: "Calculate savings", exact: true }).click();
  await expect(dialog).toContainText("All 48 pieces still fit");
  await expectNoPageOverflow(page);
  expect(await dialog.evaluate(el => el.scrollWidth <= el.clientWidth)).toBe(true);
  await page.screenshot({ path: "qa/calculator-mobile.png", fullPage: true });
  await dialog.getByRole("button", { name: "Close dialog", exact: true }).click();
  await expect(dialog).toHaveCount(0);
});
