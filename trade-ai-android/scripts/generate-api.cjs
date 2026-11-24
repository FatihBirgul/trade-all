const fs = require("node:fs");
const spec = JSON.parse(
  fs.readFileSync("docs/backend/V2_OPENAPI.json", "utf8"),
);
function type(s) {
  if (s.$ref)
    return (
      "components['schemas'][" + JSON.stringify(s.$ref.split("/").pop()) + "]"
    );
  if (s.const !== undefined) return JSON.stringify(s.const);
  if (s.enum) return s.enum.map((v) => JSON.stringify(v)).join(" | ");
  if (s.anyOf) return s.anyOf.map(type).join(" | ");
  if (s.type === "null") return "null";
  if (s.type === "integer" || s.type === "number") return "number";
  if (s.type === "boolean" || s.type === "string") return s.type;
  if (s.type === "array") return "(" + type(s.items) + ")[]";
  if (s.type === "object") {
    const fields = Object.entries(s.properties || {})
      .map(
        ([k, v]) =>
          JSON.stringify(k) +
          (s.required?.includes(k) ? "" : "?") +
          ": " +
          type(v) +
          ";",
      )
      .join("\n");
    const extra = s.additionalProperties
      ? "[key: string]: " +
        (s.additionalProperties === true
          ? "unknown"
          : type(s.additionalProperties)) +
        ";"
      : "";
    return "{\n" + fields + "\n" + extra + "\n}";
  }
  throw new Error("Unsupported schema: " + JSON.stringify(s));
}
const output =
  "// Generated from the unchanged backend OpenAPI. Do not hand edit.\nexport interface components { schemas: {\n" +
  Object.entries(spec.components.schemas)
    .map(([name, s]) => JSON.stringify(name) + ": " + type(s) + ";")
    .join("\n") +
  "\n}}\n";
fs.writeFileSync("src/api/schema.ts", output);
console.log(
  "Generated " + Object.keys(spec.components.schemas).length + " API models.",
);
