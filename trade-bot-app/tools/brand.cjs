/* global __dirname */
// Uygulama simgesi ve açılış logosu. Çizim burada tanımlıdır (SVG); PNG'ler bu betikle üretilir:
//   node tools/brand.cjs
// Çıktı: assets/ (icon, adaptive ön/arka/tek renk katman, açılış logosu) ve screenshots/00-logo*.png (önizleme).
// Android'in farklı yoğunluk (mdpi…xxxhdpi) dosyalarını `expo prebuild` bu 1024 px kaynaklardan üretir.
const { chromium } = require("playwright");
const path = require("path");

const INK = "#2A2D7C"; // tema: hero
const GLOW = "#3D41A6"; // tema: heroSoft
const MINT = "#1BD79A";

// Nabız çizgisi yükselen bir eğilime dönüşür ve yeşil bir noktada biter: "bot piyasayı izliyor".
// `scale` 1 iken çizim 100×100 alanın ~%68'ini kaplar. Adaptive simgede Android katmanın yalnızca ortadaki
// %66'sını gösterir ve onu daire/kare olarak kırpar; bu yüzden ön katmanda çizim 0,7 ölçekle (köşeleri dahil
// güvenli dairenin içinde) çizilir.
const mark = (dot = MINT, scale = 1) => `
  <g transform="translate(50 50) scale(${scale}) translate(-52.75 -50.6)">
    <path d="M19 61 H34 L42 41 L53 71 L62 51 L80 33" fill="none" stroke="#FFFFFF" stroke-width="7.5" stroke-linecap="round" stroke-linejoin="round"/>
    <circle cx="80" cy="33" r="6.5" fill="${dot}"/>
  </g>`;
const SAFE = 0.7;
const background = `
  <rect width="100" height="100" fill="${INK}"/>
  <circle cx="50" cy="50" r="29" fill="${GLOW}" opacity="0.55"/>
  <circle cx="50" cy="50" r="20.5" fill="${GLOW}" opacity="0.55"/>`;
const svg = (body, size = 1024, box = "0 0 100 100") => `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="${box}">${body}</svg>`;
const VISIBLE = "16.667 16.667 66.667 66.667"; // Android'in adaptive katmandan gösterdiği orta bölüm
const uri = (body, box) => "data:image/svg+xml;utf8," + encodeURIComponent(svg(body, 1024, box));

(async () => {
  const assets = path.join(__dirname, "..", "assets");
  const shots = path.join(__dirname, "..", "screenshots");
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1024, height: 1024 } });
  const render = async (body, file, transparent, box) => {
    await page.setContent(`<body style="margin:0;background:transparent">${svg(body, 1024, box)}</body>`);
    await page.screenshot({ path: path.join(assets, file), omitBackground: transparent });
  };
  // Eski Android sürümleri ve genel simge: adaptive simgenin görünen bölümüyle aynı görüntü.
  await render(background + mark(MINT, SAFE), "icon.png", false, VISIBLE);
  await render(background, "adaptive-background.png", false);
  await render(mark(MINT, SAFE), "adaptive-foreground.png", true);
  await render(mark("#FFFFFF", SAFE), "adaptive-monochrome.png", true); // Android 13+ temalı simge
  await render(mark(), "splash-logo.png", true);

  // Önizleme 1: simgenin Android'in kırptığı biçimlerde ve farklı boyutlarda görünüşü.
  const full = uri(background + mark(MINT, SAFE), VISIBLE);
  const shapes = [["Daire", "50%"], ["Yuvarlak kare", "28%"], ["Kare", "12%"]];
  const tile = (size, radius) => `<div style="width:${size}px;height:${size}px;border-radius:${radius};background:url('${full}') center/cover no-repeat;box-shadow:0 10px 24px rgba(42,45,124,.28)"></div>`;
  const preview = await browser.newPage({ viewport: { width: 412, height: 892 }, deviceScaleFactor: 2 });
  await preview.setContent(`<body style="margin:0;font-family:system-ui,sans-serif;background:#F2F3FA;color:#16183A">
    <div style="padding:28px 22px;display:flex;flex-direction:column;gap:22px">
      <div><div style="font-size:26px;font-weight:900">Trade Bot simgesi</div>
      <div style="color:#7A7F9D;font-size:14px;margin-top:4px">Adaptive simge: ön katman (çizim) + arka katman (zemin). Android biçimi kendisi kırpar.</div></div>
      <div style="background:#fff;border-radius:26px;padding:20px;display:flex;justify-content:space-between">
        ${shapes.map(([name, radius]) => `<div style="display:flex;flex-direction:column;align-items:center;gap:10px">${tile(96, radius)}<div style="font-size:13px;color:#7A7F9D">${name}</div></div>`).join("")}
      </div>
      <div style="background:#fff;border-radius:26px;padding:20px;display:flex;align-items:flex-end;justify-content:space-between">
        ${[["mdpi", 48], ["hdpi", 72], ["xhdpi", 96], ["xxhdpi", 144]].map(([name, size]) => `<div style="display:flex;flex-direction:column;align-items:center;gap:8px">${tile(size / 1.5, "50%")}<div style="font-size:12px;color:#7A7F9D">${name}</div></div>`).join("")}
      </div>
      <div style="background:#fff;border-radius:26px;padding:20px;display:flex;gap:16px;align-items:center">
        <div style="width:96px;height:96px;border-radius:50%;background:#DDE3F0 url('${uri(mark("#3B4A6B", SAFE).replace(/#FFFFFF/g, "#3B4A6B"), VISIBLE)}') center/cover no-repeat"></div>
        <div style="flex:1"><div style="font-weight:800">Temalı (tek renk) simge</div><div style="font-size:13px;color:#7A7F9D">Android 13+ duvar kâğıdı renklerine uyar.</div></div>
      </div>
      <div style="border-radius:26px;padding:26px 20px;background:linear-gradient(160deg,#4B6CB7,#182848);display:flex;justify-content:space-around">
        ${["Telefon", "Trade Bot", "Ayarlar"].map((name, i) => `<div style="display:flex;flex-direction:column;align-items:center;gap:8px">${i === 1 ? tile(60, "50%") : `<div style="width:60px;height:60px;border-radius:50%;background:rgba(255,255,255,.28)"></div>`}<div style="font-size:12px;color:#fff">${name}</div></div>`).join("")}
      </div>
    </div></body>`);
  await preview.screenshot({ path: path.join(shots, "00-logo.png") });
  // Önizleme 2: açılış ekranı (app.json: zemin INK, ortada 200 px logo).
  await preview.setContent(`<body style="margin:0;background:${INK};height:100vh;display:flex;align-items:center;justify-content:center"><img src="${uri(mark())}" width="200" height="200"></body>`);
  await preview.screenshot({ path: path.join(shots, "00b-acilis-ekrani.png") });
  await browser.close();
})();
