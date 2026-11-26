/* global __dirname */
// Ekran görüntüsü testlerinin düzeneği: web derlemesini (dist/) sunar, sunucu isteklerini fixture'larla
// yanıtlar (https://bot.test), her test için temiz bir sayfa açar.
const { chromium } = require("playwright");
const assert = require("node:assert/strict");
const http = require("http");
const fs = require("fs");
const path = require("path");

const root = path.join(__dirname, "..");
const dist = path.join(root, "dist");
const shots = path.join(root, "screenshots");
const ORIGIN = "https://bot.test";
const TYPES = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".json": "application/json", ".ttf": "font/ttf", ".png": "image/png", ".ico": "image/x-icon" };
const ROUTES = [
  [/^\/status$/, "status"], [/^\/positions$/, "positions"], [/^\/settings$/, "settings"],
  [/^\/reports\?period=day/, "reports_day"], [/^\/reports\?period=week/, "reports_week"], [/^\/reports\?period=month/, "reports_month"],
  [/^\/scorecard/, "scorecard"], [/^\/strategies$/, "strategies"], [/^\/news/, "news"], [/^\/events/, "events"],
  [/^\/symbols/, "symbols"], [/^\/health\/summary/, "summary"], [/^\/health$/, "health"], [/^\/pair$/, "pair"],
];
const CORS = { "access-control-allow-origin": "*", "access-control-allow-headers": "*", "access-control-allow-methods": "*" };

function fixture(scenario, name) {
  return JSON.parse(fs.readFileSync(path.join(root, "fixtures", scenario, name + ".json"), "utf8"));
}

// `overrides`: { "GET /status": { status, body } | "hang" | (request) => ({ status, body }) }
async function mock(page, scenario, overrides = {}) {
  const calls = [];
  await page.route(ORIGIN + "/**", async (route) => {
    const request = route.request();
    if (request.method() === "OPTIONS") return route.fulfill({ status: 204, headers: CORS });
    const url = request.url().slice(ORIGIN.length);
    const key = request.method() + " " + url.split("?")[0];
    calls.push({ method: request.method(), url, body: request.postDataJSON?.() ?? null });
    const reply = (status, body) => route.fulfill({ status, headers: CORS, contentType: "application/json", body: JSON.stringify(body) });
    const custom = overrides[key];
    if (custom === "hang") return; // yanıt hiç gelmez: "yükleniyor" durumu
    if (typeof custom === "function") { const r = await custom(request, url); return reply(r.status ?? 200, r.body); }
    if (custom) return reply(custom.status ?? 200, custom.body);
    if (request.method() !== "GET" && !/^\/pair$/.test(url)) return reply(404, { detail: "testte tanımlı değil: " + key });
    const hit = ROUTES.find(([pattern]) => pattern.test(url));
    if (!hit) return reply(404, { detail: "bulunamadı" });
    if (hit[1] === "events" && /after=/.test(url)) return reply(200, { events: [] });
    reply(200, fixture(scenario, hit[1]));
  });
  return calls;
}

async function pair(page) {
  await page.goto(page.base + "/");
  await page.getByLabel("Sunucu adresi").fill("bot.test");
  await page.getByLabel("Eşleştirme kodu").fill("123456");
  await page.getByTestId("pair").click();
  await page.getByTestId("screen-panel").waitFor();
}

// `into`: görüntüden önce ekrana getirilecek bölümün testID'si (uzun ekranların alt kısımları için).
async function shot(page, name, into) {
  if (into) await page.getByTestId(into).scrollIntoViewIfNeeded();
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(350);
  await page.screenshot({ path: path.join(shots, name + ".png") });
}

async function run(tests) {
  fs.mkdirSync(shots, { recursive: true });
  const server = http.createServer((request, response) => {
    let file = path.join(dist, decodeURIComponent(request.url.split("?")[0]));
    if (!file.startsWith(dist) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) file = path.join(dist, "index.html");
    response.writeHead(200, { "content-type": TYPES[path.extname(file)] || "application/octet-stream" });
    fs.createReadStream(file).pipe(response);
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const base = "http://127.0.0.1:" + server.address().port;
  const browser = await chromium.launch();
  const only = process.argv[2];
  let failed = 0;
  for (const [name, body] of tests) {
    if (only && !name.includes(only)) continue;
    const context = await browser.newContext({ viewport: { width: 412, height: 892 }, deviceScaleFactor: 2, locale: "tr-TR", timezoneId: "Europe/Istanbul" });
    const page = await context.newPage();
    page.base = base;
    page.setDefaultTimeout(8000);
    const errors = [];
    page.on("pageerror", (error) => errors.push(String(error)));
    try {
      await body(page);
      assert.deepEqual(errors, [], "sayfa hatası");
      console.log("✓ " + name);
    } catch (error) {
      failed += 1;
      console.log("✗ " + name + "\n  " + String(error.message || error).split("\n").slice(0, 6).join("\n  "));
      await page.screenshot({ path: path.join(shots, "_hata-" + name.replace(/[^a-z0-9]+/gi, "-") + ".png") }).catch(() => {});
    }
    await context.close();
  }
  await browser.close();
  server.close();
  if (failed) { console.log(failed + " test başarısız"); process.exit(1); }
}

module.exports = { run, mock, pair, shot, fixture, assert };
