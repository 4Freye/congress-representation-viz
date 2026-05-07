import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "test",
  timeout: 30_000,
  fullyParallel: false,
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: "http://localhost:8765",
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { browserName: "chromium" } }],
  webServer: {
    command: "python3 -m http.server 8765",
    url: "http://localhost:8765",
    reuseExistingServer: true,
    timeout: 30_000,
  },
});
