// Deterministic local checks; no request, telemetry or package metadata upload.
// This is explicitly NOT a substitute result for the full Expo Doctor service checks.
const fs = require("node:fs"),
  assert = require("node:assert/strict"),
  semver = require("semver");
const pkg = require("../package.json"),
  app = require("../app.json").expo,
  lock = require("../package-lock.json");
const bundled = require("expo/bundledNativeModules.json");
let checked = 0;
for (const [name, range] of Object.entries({
  ...pkg.dependencies,
  ...pkg.devDependencies,
})) {
  const actual = JSON.parse(
    fs.readFileSync("node_modules/" + name + "/package.json", "utf8"),
  ).version;
  assert(
    semver.satisfies(actual, range),
    name + " does not match package.json",
  );
  if (bundled[name]) {
    assert(
      semver.satisfies(actual, bundled[name]),
      name + " does not match installed Expo SDK",
    );
    checked++;
  }
  assert.equal(
    lock.packages["node_modules/" + name].version,
    actual,
    name + " lock mismatch",
  );
}
for (const [name, entry] of Object.entries(lock.packages)) {
  if (entry.resolved?.startsWith("https://registry.npmjs.org/"))
    assert(
      entry.resolved.endsWith("-" + entry.version + ".tgz"),
      name + " tarball/version mismatch",
    );
}
assert.equal(pkg.version, app.version);
assert.equal(lock.version, pkg.version);
assert.equal(lock.packages[""].version, pkg.version);
assert.equal(app.android.allowBackup, false);
assert.equal(pkg.main, "expo-router/entry");
assert(
  !fs.existsSync("trade_gateway"),
  "Server package must remain outside Android source",
);
console.log(
  "PASS: local dependency/lock checks; " +
    checked +
    " Expo SDK compatibility checks; version/config/server separation checks. Full online Expo Doctor not executed.",
);
