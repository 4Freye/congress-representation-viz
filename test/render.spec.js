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

  test("renders all state geometries (50 states + DC, plus optional territories)", async ({ page }) => {
    const count = await page.locator("svg#map path.state").count();
    expect(count).toBeGreaterThanOrEqual(50);
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
      if (!target) throw new Error("no colored state path found to click");
      target.dispatchEvent(new MouseEvent("click", { bubbles: true, clientX: 100, clientY: 100 }));
    });
    const tooltip = page.locator("#tooltip");
    await expect(tooltip).not.toHaveClass(/hidden/);
    const text = (await tooltip.textContent()) || "";
    expect(text).toMatch(/Voters|House|bias|fit/i);
  });

  test("controls, national bar, scatter all rendered", async ({ page }) => {
    await expect(page.locator("#controls .mode-btn")).toHaveCount(3);
    await expect(page.locator("#seats-slider")).toBeVisible();
    await page.waitForFunction(
      () => document.querySelectorAll("#scatter circle.dot").length > 0,
      { timeout: 5_000 }
    );
    const dots = await page.locator("#scatter circle.dot").count();
    expect(dots).toBeGreaterThanOrEqual(45);
    const natBars = await page.locator("#national-bar rect").count();
    expect(natBars).toBeGreaterThanOrEqual(4);
  });

  test("switching to absolute fit mode recolors map", async ({ page }) => {
    const before = await page.$$eval("#map path.state", (nodes) =>
      nodes.slice(0, 5).map((n) => n.getAttribute("fill"))
    );
    await page.click('.mode-btn[data-mode="abs"]');
    await page.waitForTimeout(150);
    const after = await page.$$eval("#map path.state", (nodes) =>
      nodes.slice(0, 5).map((n) => n.getAttribute("fill"))
    );
    expect(after).not.toEqual(before);
    await expect(page.locator('.mode-btn[data-mode="abs"]')).toHaveClass(/is-active/);
  });

  test("seat slider mutes small-delegation states", async ({ page }) => {
    await page.fill("#seats-slider", "10");
    await page.dispatchEvent("#seats-slider", "input");
    await page.waitForTimeout(100);
    const muted = await page.locator("#map path.state.muted").count();
    expect(muted).toBeGreaterThan(0);
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
