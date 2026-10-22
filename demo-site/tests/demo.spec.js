import { test, expect } from "@playwright/test";
import fs from "node:fs/promises";

test("customer journey: model, source facts, solver, persistence, report and local IFC", async ({
  page,
}) => {
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Build with less waste." }),
  ).toBeVisible();
  await expect(page.locator("canvas")).toBeVisible();
  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({ path: "qa/overview-desktop.png", fullPage: true });
  await expect(
    page.getByRole("button", { name: "Heating & cooling", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  await page
    .getByRole("button", { name: "Heating & cooling", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Heating & cooling", exact: true }),
  ).toHaveAttribute("aria-pressed", "false");
  await page.getByLabel("Visible building level").selectOption("2");
  await page
    .getByRole("button", { name: "Separate floors", exact: true })
    .click();
  await page.getByRole("button", { name: "Reset camera", exact: true }).click();
  await page
    .getByRole("button", { name: "Expand viewer", exact: true })
    .click();
  await expect(page.locator(".viewer-card")).toHaveClass(/expanded/);
  await page.keyboard.press("Escape");
  await expect(page.locator(".viewer-card")).not.toHaveClass(/expanded/);
  await page.locator(".source-details summary").click();
  await page
    .getByRole("button", { name: "Inspect Electrical", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toContainText("2,798");
  await page.getByRole("button", { name: "Close dialog" }).click();
  await page.locator(".opportunity").click();
  await expect(page.getByRole("dialog")).toContainText("4.625 m");
  await expect(page.getByRole("dialog")).toContainText("small test");
  await page.getByRole("button", { name: "Close dialog" }).click();
  await page
    .getByRole("button", { name: "Cost calculator", exact: true })
    .click();
  await expect(page.locator(".saving-summary")).toContainText("$972");
  await page
    .getByRole("spinbutton", { name: "Material price per metre" })
    .fill("30");
  await page.getByRole("button", { name: "Calculate savings" }).click();
  await expect(page.locator(".saving-summary")).toContainText("$1,620");
  await page.screenshot({ path: "qa/scenario-desktop.png", fullPage: true });
  await page
    .getByRole("button", { name: "Save calculation", exact: true })
    .click();
  await page.getByRole("button", { name: /Saved calculations/ }).click();
  await expect(page.locator(".history-row")).toHaveCount(1);
  await page.reload();
  await page.getByRole("button", { name: /Saved calculations/ }).click();
  await expect(page.locator(".history-row")).toHaveCount(1);
  await page.locator(".history-row").click();
  await expect(page.locator(".saving-summary")).toContainText("$1,620");
  const downloading = page.waitForEvent("download");
  await page
    .getByRole("button", { name: "Download results", exact: true })
    .click();
  const file = await downloading;
  const report = JSON.parse(await fs.readFile(await file.path(), "utf8"));
  expect(report.evidence.project.productCount).toBe(149822);
  expect(report.sampleScenario.savedCost).toBe(1620);
  await page
    .getByRole("button", { name: "Open building file", exact: true })
    .click();
  await page.locator("input[type=file]").setInputFiles({
    name: "demo.ifc",
    mimeType: "text/plain",
    buffer: Buffer.from(
      "ISO-10303-21;\nHEADER;FILE_SCHEMA(('IFC4'));ENDSEC;\nDATA;\n#1=IFCWALL();\n#2=IFCPIPESEGMENT();\nENDSEC;END-ISO-10303-21;",
    ),
  });
  await expect(page.locator(".file-result")).toContainText("2 file records");
  await page.locator("input[type=file]").setInputFiles({
    name: "invalid.ifc",
    mimeType: "text/plain",
    buffer: Buffer.from("not an IFC file"),
  });
  await expect(page.getByRole("alert")).toContainText("not a recognizable IFC");
  await page.getByRole("button", { name: "Close dialog" }).click();
  await page
    .getByRole("button", { name: "What was tested", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "See how the results were checked." }),
  ).toBeVisible();
  await page.screenshot({ path: "qa/evidence-desktop.png", fullPage: true });
  expect(errors).toEqual([]);
});

test("mobile layouts keep actions reachable and do not overflow", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await expect(page.locator("canvas")).toBeVisible();
  await page.evaluate(() => document.fonts.ready);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({ path: "qa/overview-mobile.png", fullPage: true });
  await page
    .getByRole("button", { name: "Open navigation", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Cost calculator", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "How much could you save on material?" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "3 m", exact: true }).click();
  await page.getByRole("button", { name: "Calculate savings" }).click();
  await expect(
    page.getByText("All 48 pieces still fit", { exact: true }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({ path: "qa/scenario-mobile.png", fullPage: true });
});
