/* Optional browser QA of the actual exported app. HTTP responses below are controlled
 * fixtures, never real-market evidence. No Windows service or production endpoint is used.
 * Requires Playwright outside the app runtime; set PLAYWRIGHT_MODULE / CHROMIUM_EXECUTABLE.
 */
const fs = require("fs"),
  http = require("http"),
  path = require("path");
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");
const root = process.cwd(),
  exported = process.env.WEB_EXPORT_DIR || "/tmp/trade8-web";
const output = process.env.VISUAL_OUTPUT_DIR || "/tmp/trade8-visual";
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
  scopes: ["read", "analyze", "scanner:write"],
  capabilities: ["market-quotes-v1", "analysis-follow-v1"],
};
const portfolios = require(
  path.join(root, "docs/backend/v2_examples/portfolios.json"),
).map((p) => ({ ...p, data_mode: "live" }));
const prior = {
  ...analysis,
  analysis_id: "d".repeat(64),
  created_at_ms: now - 3600000,
  price_time_ms: now - 3660000,
  expires_at_ms: now - 1,
  direction: "WAIT",
  reason: "regime_not_eligible",
  levels: null,
  regime: { ...analysis.regime, regime: "range" },
};
let track = {
  tracking_id: "b".repeat(64),
  origin_analysis_id: id,
  last_analysis_id: id,
  portfolio_id: "AUTO",
  symbol: analysis.symbol,
  timeframe: analysis.timeframe,
  data_mode: "live",
  enabled: true,
  status: "monitoring",
  last_checked_ms: now - 60000,
  last_direction: "WAIT",
  last_reason: "regime_not_eligible",
  notified_changes: 1,
  worker_running: false,
};
let watch = {
  watch_id: "BTCUSDT:1H",
  symbol: "BTCUSDT",
  timeframe: "1H",
  enabled: true,
  auto_paper: false,
};
let unavailable = false;
let gatewayDown = false;
let notificationMode = "queue";
const requests = [];
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
    requests.push({ path: url.pathname, method: route.request().method() });
    if (gatewayDown) return route.abort("failed");
    if (
      url.pathname.endsWith("/notifications") &&
      notificationMode !== "queue"
    ) {
      if (notificationMode === "failed") return route.abort("failed");
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: "[]",
      });
    }
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
    else if (url.pathname.includes("/analysis-tracking")) {
      if (route.request().method() === "POST") {
        track = {
          ...track,
          enabled: JSON.parse(route.request().postData()).enabled ?? true,
        };
        body = track;
      } else body = [track];
    } else if (url.pathname.endsWith("/notifications"))
      body = [
        {
          notification_id: "n".repeat(64),
          kind: "analysis",
          data_mode: "live",
          created_at_ms: now - 60000,
          delivery_status: "pending",
          delivery_service: "not_configured",
          details: {
            tracking_id: track.tracking_id,
            portfolio_id: "AUTO",
            analysis_id: id,
            change_kind: "analysis_condition_changed",
            direction: "WAIT",
            reason: "regime_not_eligible",
          },
        },
      ];
    else if (url.pathname.endsWith("/scanner"))
      body = {
        paused: true,
        lease_id: null,
        lease_until_ms: 0,
        last_tick_ms: null,
        last_error: null,
        max_analyses_per_tick: 2,
        interval_seconds: 60,
      };
    else if (url.pathname.endsWith("/watchlist")) {
      if (route.request().method() === "POST") {
        watch = { ...watch, ...JSON.parse(route.request().postData()) };
        body = watch;
      } else body = [watch];
    } else if (url.pathname.endsWith("/scanner/jobs"))
      body = [
        {
          job_id: "j",
          symbol: analysis.symbol,
          timeframe: "1H",
          closed_bar_ms: now - 1,
          status: "completed",
          started_at_ms: now - 10000,
          analysis_id: id,
          reason: null,
        },
      ];
    else if (url.pathname.endsWith("/performance"))
      body = {
        ...require(
          path.join(root, "docs/backend/v2_examples/performance.json"),
        ),
        data_mode: "live",
      };
    else if (url.pathname.endsWith("/transactions")) {
      const account = url.pathname.includes("/MANUAL/") ? "MANUAL" : "AUTO";
      body = [1, 2].map((i) => ({
        transaction_id: String(i).repeat(64),
        portfolio_id: account,
        order_id: id,
        position_id: id,
        event_id: id,
        kind: "manual_close:" + id,
        quantity: "1",
        price: "100",
        fee_quote: "0",
        cash_delta_quote: "1",
        realized_pnl_quote: i === 1 ? "0.1" : "0.2",
        time_ms: now - (3 - i) * 60000,
        data_mode: "live",
        paper_only: true,
      }));
    } else if (url.pathname.endsWith("/candles")) body = candles;
    else if (url.pathname.endsWith("/analyses/" + id)) body = analysis;
    else if (url.pathname.endsWith("/analyses/" + prior.analysis_id))
      body = prior;
    else if (url.pathname.endsWith("/analyses")) body = [analysis, prior];
    else body = [];
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      headers: { "Access-Control-Allow-Origin": "*" },
      body: JSON.stringify(body),
    });
  });
  async function capture(name) {
    const tabs = page.getByRole("tab");
    for (let i = 0; i < (await tabs.count()); i++) {
      const tab = tabs.nth(i),
        itemBox = await tab.boundingBox();
      const labelBox = await tab.locator('[dir="auto"]').last().boundingBox();
      if (
        itemBox &&
        labelBox &&
        labelBox.y + labelBox.height > itemBox.y + itemBox.height + 1
      )
        throw new Error("Tab label clipped: " + name);
    }
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
    if (process.env.VISUAL_TASK9 === "1") {
      await page.getByText("Analiz Et", { exact: true }).click();
      await page.getByText("Analizi başlat", { exact: true }).click();
      await page.getByText("Detaylı analizi aç", { exact: true }).click();
      await page.getByText("Teknik değerlendirme", { exact: true }).waitFor();
      if (
        (await page.getByText("range", { exact: true }).count()) ||
        (await page.getByText("neutral", { exact: true }).count())
      )
        throw new Error("Unassessed raw market state leaked");
      await capture("task9-demo-detail");
      await page.goto(origin);
      await page.getByText("Bildirimler", { exact: true }).click();
      await page.getByText(/sunucunun bildirim durumu bilinmiyor/).waitFor();
      await capture("task9-demo-notifications");
      await page.goto(origin);
      if (requests.length) throw new Error("DEMO contacted gateway");
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
    await page
      .getByRole("button", { name: "BTCUSDT analiz et", exact: true })
      .waitFor();
    await capture("controlled-market-basic-390");
    unavailable = true;
    await page.getByText("Piyasayı yenile", { exact: true }).click();
    await page
      .getByText("Güncel değil · Son başarılı fiyatlar gösteriliyor.", {
        exact: true,
      })
      .waitFor();
    await capture("controlled-stale-390");
    await page.getByText("Son analizi aç", { exact: true }).first().click();
    await page.getByText("Detaylı analizi aç", { exact: true }).waitFor();
    await capture("controlled-summary-basic-390");
    await page.getByText("Detaylı analizi aç", { exact: true }).click();
    await page.getByText("Analiz mumlarını yükle", { exact: true }).click();
    await page.getByTestId("snapshot-plot").waitFor();
    await capture("controlled-snapshot-basic-390");
    await page.getByText("Yakınlaştır", { exact: true }).click();
    await page.getByText("Uzaklaştır", { exact: true }).click();
    await page.goBack();
    await page.goBack();
    await page.getByText("Ayarlar", { exact: true }).last().click();
    await page.getByText("PRO", { exact: true }).click();
    await page.getByText("Ana Sayfa", { exact: true }).last().click();
    await page.getByText("Son analizi aç", { exact: true }).first().click();
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
    await page.goBack();
    await page.getByText("Analiz takipleri", { exact: true }).click();
    await page.getByText("PC işçisi kapalı", { exact: true }).waitFor();
    await page.getByText("Takibi durdur", { exact: true }).click();
    await page.getByText("Takibe devam et", { exact: true }).click();
    await page.getByText("PC işçisi kapalı", { exact: true }).waitFor();
    await page
      .getByText("Son koşul değişikliklerini yükle", { exact: true })
      .click();
    await page.getByText(/Son kaydedilen değişim:/).waitFor();
    await capture("controlled-follows-390");
    await page.goBack();
    await page.getByText("Analiz geçmişini aç", { exact: true }).click();
    await page.getByText(/Filtreler ve sıralama/).click();
    await page
      .getByRole("button", { name: "ETHUSDT", exact: true })
      .last()
      .click();
    await page
      .getByText(/Yüklenen kayıtlarda filtreye uygun analiz yok/)
      .waitFor();
    if (await page.getByText("Detayı aç", { exact: true }).count())
      throw new Error("History symbol filter failed");
    await page
      .getByRole("button", { name: "BTCUSDT", exact: true })
      .last()
      .click();
    await page
      .getByText("Karşılaştırma için seç", { exact: true })
      .first()
      .click();
    await page
      .getByText("Seçilen kayıtla karşılaştır", { exact: true })
      .click();
    await page.getByText("Gerekçe · bu / diğer", { exact: true }).waitFor();
    await capture("controlled-comparison-390");
    await page.goBack();
    await page.goBack();
    await page.getByText("Tarayıcı", { exact: true }).last().click();
    await page.getByText("İzleme listesi", { exact: true }).waitFor();
    await page
      .getByRole("button", { name: "İzlemeyi kapat · BTCUSDT:1H", exact: true })
      .click();
    await page
      .getByRole("button", { name: "İzlemeyi aç · BTCUSDT:1H", exact: true })
      .waitFor();
    await capture("controlled-scanner-390");
    await page.getByText("Portföyler", { exact: true }).last().click();
    await page.getByText("MANUAL", { exact: true }).click();
    await page
      .getByText("TOPLAM SANAL VARLIK · MANUAL", { exact: true })
      .waitFor();
    await capture("controlled-manual-portfolio-390");
    await page.getByText("Ana Sayfa", { exact: true }).last().click();
    await page.getByText("Performans", { exact: true }).click();
    await page
      .getByText("Gerçekleşen PnL kayıtlarını yükle", { exact: true })
      .click();
    await page
      .getByText("Yüklenen işlemlerin PnL toplamı", { exact: true })
      .waitFor();
    await capture("controlled-pnl-window-390");
    await page.goBack();
    await page.getByText("Son analizi aç", { exact: true }).first().click();
    await page
      .getByText("Analiz mumlarını yükle", { exact: true })
      .or(page.getByTestId("snapshot-plot"))
      .first()
      .waitFor();
    if (await page.getByText("Analiz mumlarını yükle", { exact: true }).count())
      await page.getByText("Analiz mumlarını yükle", { exact: true }).click();
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
    if (process.env.VISUAL_TASK9 === "1") {
      await page.setViewportSize({ width: 390, height: 844 });
      await page.goto(origin);
      await page.getByText("Ayarlar", { exact: true }).last().click();
      // Web deliberately never persists mobile credentials. Re-pair this controlled session.
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
      await page.getByText("Bildirimler", { exact: true }).click();
      notificationMode = "failed";
      await page.getByText("Bildirimleri yenile", { exact: true }).click();
      await page.getByText("Yeniden dene", { exact: true }).waitFor();
      if (await page.getByText(/boş bildirim listesi döndürdü/).count())
        throw new Error("Failed read claimed empty success");
      await capture("task9-live-notifications-failed");
      notificationMode = "empty";
      await page.getByText("Yeniden dene", { exact: true }).click();
      await page
        .getByText("Sunucu bu sayfa için boş bildirim listesi döndürdü.", {
          exact: true,
        })
        .waitFor();
      await capture("task9-live-notifications-empty");
      await page.goBack();
      await page.getByText("Ayarlar", { exact: true }).last().click();
      await page.getByText("DEMO", { exact: true }).click();
      await page.getByText("PRO", { exact: true }).click();
      gatewayDown = true;
      await page
        .getByText("Oturumu yenile / yeniden bağlan", { exact: true })
        .click();
      await page.getByText(/kesin neden belirlenemedi/).waitFor();
      await capture("task9-settings-unreachable");
      const before = requests.length;
      await page.getByText("Tarayıcı", { exact: true }).last().click();
      await page.getByText("Örnek izleme listesi", { exact: true }).waitFor();
      await page.getByText("DEMO örneğini sürdür", { exact: true }).click();
      await page.getByText("Yerel kontrolü dene", { exact: true }).click();
      await page
        .getByText(
          "Demo kontrolü tamamlandı. Piyasa verisi veya emir üretilmedi.",
          { exact: true },
        )
        .waitFor();
      if (requests.length !== before)
        throw new Error("Offline DEMO scanner contacted gateway");
      await capture("task9-demo-scanner-unreachable");
    }
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
