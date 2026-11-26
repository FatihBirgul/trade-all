// Web derlemesinden (dist/) ekran görüntüsü alır: node tools/screenshots.cjs <çıktı klasörü> <yol=dosya>...
const { chromium } = require("playwright");
const http = require("http");
const fs = require("fs");
const path = require("path");

const dist = path.join(__dirname, "..", "dist");
const types = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".json": "application/json", ".ttf": "font/ttf", ".png": "image/png", ".ico": "image/x-icon" };
const server = http.createServer((req, res) => {
  const clean = decodeURIComponent(req.url.split("?")[0]);
  let file = path.join(dist, clean);
  if (!file.startsWith(dist) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) file = path.join(dist, "index.html");
  res.writeHead(200, { "content-type": types[path.extname(file)] || "application/octet-stream" });
  fs.createReadStream(file).pipe(res);
});

(async () => {
  const [out, ...shots] = process.argv.slice(2);
  fs.mkdirSync(out, { recursive: true });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const base = "http://127.0.0.1:" + server.address().port;
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 412, height: 892 }, deviceScaleFactor: 2 });
  const errors = [];
  page.on("pageerror", (error) => errors.push(String(error)));
  for (const shot of shots) {
    const [route, name] = shot.split("=");
    await page.goto(base + route);
    await page.waitForLoadState("networkidle");
    await page.evaluate(() => document.fonts.ready);
    await page.waitForTimeout(400);
    await page.screenshot({ path: path.join(out, name + ".png") });
    console.log(route, "->", name + ".png");
  }
  await browser.close();
  server.close();
  if (errors.length) { console.error(errors.join("\n")); process.exit(1); }
})();
