import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./tests",
  fullyParallel: false,
  workers: 1,
  reporter: "list",
  outputDir: "./qa/test-results",
  use: {
    baseURL: process.env.DEMO_URL || "http://127.0.0.1:5188",
    headless: true,
    viewport: { width: 1440, height: 1000 },
    screenshot: "only-on-failure",
  },
});
