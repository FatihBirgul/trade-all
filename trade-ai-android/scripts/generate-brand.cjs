/* Optional design tool. PNGs are committed; no app runtime dependency is added.
 * Requires sharp as a local design tool; renderer version recorded in manifest. */
const fs = require("node:fs"),
  path = require("node:path"),
  crypto = require("node:crypto");
const sharp = require("sharp");
const { Buffer } = require("node:buffer");
const root = path.join(
  path.dirname(require.resolve("../package.json")),
  "assets/brand",
);
const t = "M284 308H740V408H572V728H452V408H284Z";
const silver =
  '<defs><linearGradient id="silver" x1="0" y1="0" x2="0" y2="1"><stop stop-color="#E8EAEC"/><stop offset=".48" stop-color="#A4ABB2"/><stop offset="1" stop-color="#CDD1D5"/></linearGradient><linearGradient id="gold" x1="0" x2="1" y1="0" y2="1"><stop stop-color="#CFAD6C"/><stop offset="1" stop-color="#9D7840"/></linearGradient></defs>';
const mark = `${silver}<path d="${t}" fill="url(#silver)"/><path d="M658 308H740V408H706L658 360Z" fill="url(#gold)"/>`;
const svg = (body) =>
  `<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="1024" viewBox="0 0 1024 1024"><title>TRADE AI geometric T</title>${body}</svg>\n`;
const files = {
  "icon.svg": svg(
    `<rect width="1024" height="1024" fill="#111316"/><g transform="translate(-128 -128) scale(1.25)">${mark}</g>`,
  ),
  "adaptive-foreground.svg": svg(mark),
  "adaptive-background.svg": svg(
    '<rect width="1024" height="1024" fill="#111316"/>',
  ),
  "adaptive-monochrome.svg": svg(`<path d="${t}" fill="#FFFFFF"/>`),
};
async function main() {
  fs.mkdirSync(root, { recursive: true });
  for (const [name, value] of Object.entries(files)) {
    fs.writeFileSync(path.join(root, name), value);
    await sharp(Buffer.from(value))
      .png()
      .toFile(path.join(root, name.replace(".svg", ".png")));
  }
  const manifest = {
    version: "trade-ai-t-1",
    design:
      "Original vector interpretation of described concept6; original six-image sheet unavailable. Not a traced identical reproduction.",
    renderer: { sharp: sharp.versions.sharp },
    adaptive_safe_circle: { cx: 512, cy: 512, radius: 313 },
    files: {},
  };
  for (const name of fs
    .readdirSync(root)
    .filter((n) => /\.(svg|png)$/.test(n))
    .sort()) {
    manifest.files[name] = crypto
      .createHash("sha256")
      .update(fs.readFileSync(path.join(root, name)))
      .digest("hex");
  }
  fs.writeFileSync(
    path.join(root, "manifest.json"),
    JSON.stringify(manifest, null, 2) + "\n",
  );
  const sizes = [24, 48, 96, 160];
  const tiles = [];
  let left = 24;
  for (const size of sizes) {
    tiles.push({
      input: await sharp(path.join(root, "icon.png"))
        .resize(size, size)
        .toBuffer(),
      left,
      top: Math.floor((208 - size) / 2),
    });
    left += size + 28;
  }
  await sharp({
    create: { width: 480, height: 208, channels: 4, background: "#23272D" },
  })
    .composite(tiles)
    .png()
    .toFile(
      process.argv[2] ??
        path.join(require("node:os").tmpdir(), "trade-ai-brand-preview.png"),
    );
  console.log(
    "Generated SVG/PNG assets; concept reference interpretation; preview outside runtime assets.",
  );
}
main().catch((e) => {
  console.error(e.message);
  process.exitCode = 1;
});
