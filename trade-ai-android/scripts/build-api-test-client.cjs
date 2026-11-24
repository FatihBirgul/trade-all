// Compile the real production API modules for the independent HTTPS integration test.
const fs = require("node:fs"),
  path = require("node:path"),
  ts = require("typescript");
const out = path.resolve(process.argv[2]);
for (const file of [
  "src/api/client.ts",
  "src/api/renewal.ts",
  "src/api/paper.ts",
  "src/api/intent.ts",
  "src/domain/snapshot.ts",
  "src/api/gateway.ts",
  "src/api/validate.ts",
  "src/domain/safety.ts",
]) {
  const target = path.join(out, file.replace(/\.ts$/, ".js"));
  fs.mkdirSync(path.dirname(target), { recursive: true });
  fs.writeFileSync(
    target,
    ts.transpileModule(fs.readFileSync(file, "utf8"), {
      compilerOptions: {
        module: ts.ModuleKind.CommonJS,
        target: ts.ScriptTarget.ES2022,
        esModuleInterop: true,
      },
    }).outputText,
  );
}
const spec = path.join(out, "docs/backend/V2_OPENAPI.json");
fs.mkdirSync(path.dirname(spec), { recursive: true });
fs.copyFileSync("docs/backend/V2_OPENAPI.json", spec);
