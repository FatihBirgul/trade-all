/* Optional browser QA of the actual exported app. HTTP responses below are controlled
 * fixtures, never real-market evidence. No Windows service or production endpoint is used.
 * Requires Playwright outside the app runtime; set PLAYWRIGHT_MODULE / CHROMIUM_EXECUTABLE.
 */
const fs = require("fs"),
  http = require("http"),
  path = require("path");
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");
const root = process.cwd(),
  exported = process.env.WEB_EXPORT_DIR || "/tmp/trade7-web";
const output = process.env.VISUAL_OUTPUT_DIR || "/tmp/trade7-visual";
fs.mkdirSync(output, { recursive: true });
const sample = require(
  path.join(root, "docs/backend/v2_examples/analysis.json"),
);
const now = Date.now(),
  id = "a".repeat(64);
const analysis = {
  ...sample,
  analysis_id: id,
  data_mode: "live",
  created_at_ms: now,
  expires_at_ms: now + 900000,
  price_time_ms: now - 60000,
};
const candles = {
  analysis_id: id,
  source_record_id: "b".repeat(64),
  symbol: analysis.symbol,
  timeframe: analysis.timeframe,
  provider: analysis.provider,
  venue: analysis.venue,
  data_mode: "live",
  source: "immutable",
  as_of_ms: now,
  price_kind: "last",
  contract_type: "spot",
  quote_currency: "USDT",
  snapshot_only: true,
  volume_kind: "real",
  candles: Array.from({ length: 80 }, (_, i) => {
    const p =
      Number(analysis.price) * (1 + Math.sin(i / 6) * 0.01 + i * 0.0004);
    return {
      open_time_ms: now - (80 - i) * 3600000,
      close_time_ms: now - (79 - i) * 3600000 - 1,
      is_final: true,
      open: String(p),
      close: String(p * 1.001),
      high: String(p * 1.003),
      low: String(p * 0.998),
      volume: "10",
    };
  }),
};
const metadata = {
  session_id: "qa",
  device_id: "qa",
  device_name: "Controlled visual QA",
  protocol_version: 1,
  expires_at_ms: now + 3600000,
  accounts: ["AUTO", "MANUAL"],
  scopes: ["read", "analyze"],
  capabilities: ["market-quotes-v1"],
};
const portfolios = require(
  path.join(root, "docs/backend/v2_examples/portfolios.json"),
).map((p) => ({ ...p, data_mode: "live" }));
let unavailable = false;
(async () => {
  const server = http.createServer((req, res) => {
    let file = path.join(exported, decodeURIComponent(req.url.split("?")[0]));
    if (!fs.existsSync(file) || fs.statSync(file).isDirectory())
      file = path.join(exported, "index.html");
    res.setHeader(
      "Content-Type",
      file.endsWith(".js")
        ? "application/javascript"
        : file.endsWith(".ttf")
          ? "font/ttf"
          : file.endsWith(".png")
            ? "image/png"
            : "text/html",
    );
    fs.createReadStream(file).pipe(res);
  });
  await new Promise((r) => server.listen(0, "127.0.0.1", r));
  const origin = "http://127.0.0.1:" + server.address().port;
  const browser = await chromium.launch({
    headless: true,
    executablePath: process.env.CHROMIUM_EXECUTABLE,
    args: [
      "--no-sandbox",
      "--disable-dev-shm-usage",
      "--disable-gpu",
      "--disable-software-rasterizer",
      "--no-zygote",
    ],
  });
  const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
  const errors = [],
    results = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.route("https://qa.example.test/**", async (route) => {
    const url = new URL(route.request().url());
    let body;
    if (url.pathname === "/gateway/pair")
      body = { ...metadata, session: "tg_" + "a".repeat(43) };
    else if (url.pathname === "/gateway/session") body = metadata;
    else if (url.pathname.endsWith("/health"))
      body = {
        status: "ok",
        version: "2.0",
        data_mode: "live",
        storage: "sqlite",
        provider: analysis.provider,
        provider_status: "available",
        real_execution: false,
      };
    else if (url.pathname.endsWith("/quotes")) {
      if (unavailable)
        return route.fulfill({
          status: 503,
          contentType: "application/json",
          body: JSON.stringify({
            error: { code: "PROVIDER_UNAVAILABLE", message: "QA outage" },
          }),
        });
      body = {
        fetched_at_ms: Date.now(),
        stale: false,
        real_execution: false,
        data_mode: "live",
        provider: "binance_public_spot",
        provider_status: "available",
        items: ["BTCUSDT", "ETHUSDT", "SOLUSDT"].map((symbol, i) => ({
          symbol,
          price: String((i + 1) * 100),
          change_percent_24h: i ? "1.25" : "-0.5",
          source_time_ms: Date.now(),
          chart_status: "available",
          history: Array.from({ length: 24 }, (_, j) => ({
            time_ms: now - (24 - j) * 3600000,
            price: String((i + 1) * 100 + Math.sin(j)),
          })),
        })),
      };
    } else if (url.pathname.endsWith("/portfolios")) body = portfolios;
    else if (url.pathname.endsWith("/candles")) body = candles;
    else if (url.pathname.endsWith("/analyses/" + id)) body = analysis;
    else if (url.pathname.endsWith("/analyses")) body = [analysis];
    else body = [];
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      headers: { "Access-Control-Allow-Origin": "*" },
      body: JSON.stringify(body),
    });
  });
  async function capture(name) {
    if (name.includes("snapshot"))
      await page.getByTestId("snapshot-plot").scrollIntoViewIfNeeded();
    await page.screenshot({
      path: path.join(output, name + ".png"),
      fullPage: true,
    });
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth > innerWidth,
    );
    if (overflow) throw new Error("Horizontal overflow: " + name);
    results.push({
      name,
      width: page.viewportSize().width,
      horizontalOverflow: overflow,
    });
  }
  try {
    await page.goto(origin);
    await page.getByText("Analiz Et", { exact: true }).waitFor();
    await capture("demo-basic-390");
    if (process.env.VISUAL_BASELINE_ONLY === "1") {
      console.log("Baseline captured");
      return;
    }
    await page.getByText("Ayarlar", { exact: true }).last().click();
    await page
      .getByLabel("HTTPS gateway adresi", { exact: true })
      .fill("https://qa.example.test");
    await page
      .getByLabel("Tek kullanımlık eşleştirme kodu", { exact: true })
      .fill("a".repeat(32));
    await page
      .getByText("Bağlantıyı test et ve kaydet", { exact: true })
      .click();
    await page.getByText("Bu oturumda doğrulandı", { exact: true }).waitFor();
    await page.getByText("CANLI", { exact: true }).click();
    await page.getByText("Ana Sayfa", { exact: true }).last().click();
    await page.getByText("BTCUSDT analiz et", { exact: true }).waitFor();
    await capture("controlled-market-basic-390");
    unavailable = true;
    await page.getByText("Piyasayı yenile", { exact: true }).click();
    await page
      .getByText("Güncel değil · Son başarılı fiyatlar gösteriliyor.", {
        exact: true,
      })
      .waitFor();
    await capture("controlled-stale-390");
    await page.getByText("Son analizi aç", { exact: true }).click();
    await page.getByText("Analiz mumlarını yükle", { exact: true }).click();
    await page.getByTestId("snapshot-plot").waitFor();
    await capture("controlled-snapshot-basic-390");
    await page.getByText("Yakınlaştır", { exact: true }).click();
    await page.getByText("Uzaklaştır", { exact: true }).click();
    await page.goBack();
    await page.getByText("Ayarlar", { exact: true }).last().click();
    await page.getByText("PRO", { exact: true }).click();
    await page.getByText("Ana Sayfa", { exact: true }).last().click();
    await page.getByText("Son analizi aç", { exact: true }).click();
    await page
      .getByText("Analiz mumlarını yükle", { exact: true })
      .or(page.getByTestId("snapshot-plot"))
      .first()
      .waitFor();
    if (await page.getByText("Analiz mumlarını yükle", { exact: true }).count())
      await page.getByText("Analiz mumlarını yükle", { exact: true }).click();
    await page.getByText("EMA20 kapalı", { exact: true }).click();
    await page.getByText("EMA50 kapalı", { exact: true }).click();
    await page.getByText("VWAP kapalı", { exact: true }).click();
    await capture("controlled-snapshot-pro-390");
    await page.setViewportSize({ width: 320, height: 740 });
    await capture("controlled-snapshot-pro-320");
    await page.evaluate(() => {
      const styles = [...document.querySelectorAll('[dir="auto"]')].map((e) => [
        e,
        getComputedStyle(e).fontSize,
        getComputedStyle(e).lineHeight,
      ]);
      for (const [element, font, line] of styles) {
        element.style.fontSize = parseFloat(font) * 1.5 + "px";
        if (line !== "normal")
          element.style.lineHeight = parseFloat(line) * 1.5 + "px";
      }
    });
    await capture("controlled-snapshot-pro-320-text150");
    if (errors.length) throw new Error(errors.join("\n"));
    fs.writeFileSync(
      path.join(output, "results.json"),
      JSON.stringify(
        {
          evidence:
            "Actual exported app; controlled HTTP fixtures; not a real backend or phone test",
          results,
          errors,
        },
        null,
        2,
      ),
    );
    console.log(JSON.stringify({ results, errors }));
  } catch (error) {
    console.error((await page.locator("body").innerText()).slice(-6000));
    await page.screenshot({ path: path.join(output, "failure.png") });
    throw error;
  } finally {
    await browser.close();
    server.close();
  }
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
