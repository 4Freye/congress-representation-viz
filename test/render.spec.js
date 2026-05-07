import { test, expect } from "@playwright/test";

test.describe("map renders correctly", () => {
  let pageErrors;
  let consoleErrors;

  test.beforeEach(async ({ page }) => {
    pageErrors = [];
    consoleErrors = [];
    page.on("pageerror", (e) => pageErrors.push(e.message));
    page.on("console", (msg) => {
      if (msg.type() === "error") consoleErrors.push(msg.text());
    });
    await page.goto("/", { waitUntil: "networkidle" });
    await page.waitForFunction(
      () => document.querySelectorAll("#map path.state").length > 0,
      { timeout: 15_000 }
    );
  });

  test("no error banner shown", async ({ page }) => {
    const banner = await page.$("#error-banner");
    expect(banner).toBeNull();
  });

  test("svg has non-zero rendered height", async ({ page }) => {
    const box = await page.locator("svg#map").boundingBox();
    expect(box).not.toBeNull();
    expect(box.height).toBeGreaterThan(100);
  });

  test("renders 56 state geometries", async ({ page }) => {
    const count = await page.locator("svg#map path.state").count();
    expect(count).toBe(56);
  });

  test("at least 45 states have a colored (non-fallback) fill", async ({ page }) => {
    const fills = await page.$$eval("svg#map path.state", (nodes) =>
      nodes.map((n) => n.getAttribute("fill"))
    );
    const colored = fills.filter(
      (f) => f && f.toLowerCase() !== "#ddd" && f !== "rgb(221, 221, 221)"
    );
    expect(colored.length).toBeGreaterThanOrEqual(45);
  });

  test("inter-state mesh path is present", async ({ page }) => {
    const meshCount = await page.locator('svg#map > path[stroke="#fff"]').count();
    expect(meshCount).toBeGreaterThanOrEqual(1);
  });

  test("clicking a state path shows tooltip with state info", async ({ page }) => {
    await page.evaluate(() => {
      const paths = document.querySelectorAll("svg#map path.state");
      let target = null;
      let bestArea = 0;
      paths.forEach((p) => {
        const b = p.getBBox();
        const a = b.width * b.height;
        if (a > bestArea && p.getAttribute("fill") !== "#ddd") {
          target = p;
          bestArea = a;
        }
      });
      target.dispatchEvent(new MouseEvent("click", { bubbles: true, clientX: 100, clientY: 100 }));
    });
    const tooltip = page.locator("#tooltip");
    await expect(tooltip).not.toHaveClass(/hidden/);
    const text = (await tooltip.textContent()) || "";
    expect(text).toMatch(/Voters|House|Deviation/);
  });

  test("generated footer is populated from data payload", async ({ page }) => {
    const text = await page.locator("#generated").textContent();
    expect(text.trim().length).toBeGreaterThan(0);
    expect(text).toMatch(/Congress/);
  });

  test("no console or page errors during load", async () => {
    expect(pageErrors).toEqual([]);
    expect(consoleErrors).toEqual([]);
  });
});
