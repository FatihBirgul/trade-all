import fs from "fs";
import path from "path";

// Gerçek telefonda görülen hata (0.9.2): "Bağlantı" ekranı gizli sekmeydi (href: null) ve
// router.push("/connection") hiçbir şey yapmıyordu; Jest'te router sahte olduğu için yakalanmadı.
// Bu test kaynak dosyalarını okur: push edilen her rota ya kök Stack ekranı ya da görünür sekme olmalı.
const root = path.join(__dirname, "..");
const read = (file: string) => fs.readFileSync(path.join(root, file), "utf8");

function sources(dir: string): string[] {
  return fs.readdirSync(path.join(root, dir), { withFileTypes: true }).flatMap((entry) => {
    const file = path.join(dir, entry.name);
    if (entry.isDirectory()) return sources(file);
    return /\.tsx?$/.test(entry.name) ? [file] : [];
  });
}

const tabsLayout = read("app/(tabs)/_layout.tsx");
const hiddenTabs = [...tabsLayout.matchAll(/\["([\w-]+)",[^\]]*?(true|false)\]/g)]
  .filter((match) => match[2] === "false")
  .map((match) => match[1]);
const visibleTabs = [...tabsLayout.matchAll(/\["([\w-]+)",[^\]]*?(true|false)\]/g)]
  .filter((match) => match[2] === "true")
  .map((match) => match[1]);
const stackScreens = [...read("app/_layout.tsx").matchAll(/<Stack\.Screen\s+name="([\w()-]+)"/g)].map(
  (match) => match[1],
);
// Eski kripto ekranları kendileri gizlidir ve artık ulaşılmaz; içlerindeki geçişler bilerek bırakıldı.
const LEGACY = ["app/(tabs)/legacy.tsx", "app/(tabs)/scanner.tsx", "src/ui.tsx"];

test("the layouts are read correctly", () => {
  expect(visibleTabs).toEqual(["index", "positions", "reports", "events", "settings-bot"]);
  expect(hiddenTabs).toContain("legacy");
  expect(stackScreens).toContain("manual-trade");
});

test("every screen opened with router.push is a root stack route, never a hidden tab", () => {
  const pushed: [string, string][] = [];
  for (const file of [...sources("app"), ...sources("src")]) {
    if (LEGACY.includes(file.split(path.sep).join("/"))) continue;
    for (const match of read(file).matchAll(/router\.(?:push|replace|navigate)\(\s*["'`]\/([\w-]*)/g))
      pushed.push([file, match[1]]);
  }
  expect(pushed.map(([, route]) => route)).toContain("connection");
  for (const [file, name] of pushed) {
    const route = name || "index"; // "/" = Panel sekmesi
    expect([file, route, hiddenTabs.includes(route)]).toEqual([file, route, false]);
    expect([file, route, stackScreens.includes(route) || visibleTabs.includes(route)]).toEqual([file, route, true]);
    if (stackScreens.includes(route)) expect(fs.existsSync(path.join(root, "app", route + ".tsx"))).toBe(true);
  }
});

test("the connection screen is a root stack route", () => {
  expect(stackScreens).toContain("connection");
  expect(fs.existsSync(path.join(root, "app/connection.tsx"))).toBe(true);
  expect(fs.existsSync(path.join(root, "app/(tabs)/connection.tsx"))).toBe(false);
});
