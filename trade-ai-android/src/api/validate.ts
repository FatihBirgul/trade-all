import spec from "../../docs/backend/V2_OPENAPI.json";
type Schema = {
  type?: string;
  $ref?: string;
  const?: unknown;
  enum?: unknown[];
  anyOf?: Schema[];
  properties?: Record<string, Schema>;
  required?: string[];
  items?: Schema;
  additionalProperties?: boolean | Schema;
};
const schemas = spec.components.schemas as Record<string, Schema>;
function matches(schema: Schema, value: unknown): boolean {
  if (schema.$ref)
    return matches(schemas[schema.$ref.split("/").pop()!], value);
  if (schema.const !== undefined) return value === schema.const;
  if (schema.enum) return schema.enum.includes(value);
  if (schema.anyOf) return schema.anyOf.some((s) => matches(s, value));
  if (schema.type === "null") return value === null;
  if (schema.type === "array")
    return (
      Array.isArray(value) && value.every((v) => matches(schema.items!, v))
    );
  if (schema.type === "integer")
    return typeof value === "number" && Number.isSafeInteger(value);
  if (schema.type === "number")
    return typeof value === "number" && Number.isFinite(value);
  if (schema.type === "object") {
    if (!value || typeof value !== "object" || Array.isArray(value))
      return false;
    const v = value as Record<string, unknown>;
    if (schema.required?.some((k) => !(k in v))) return false;
    return Object.entries(v).every(([k, x]) =>
      schema.properties?.[k]
        ? matches(schema.properties[k], x)
        : schema.additionalProperties === false
          ? false
          : typeof schema.additionalProperties === "object"
            ? matches(schema.additionalProperties, x)
            : true,
    );
  }
  return typeof value === schema.type;
}
export function validateResponse(
  path: string,
  method: string,
  value: unknown,
): boolean {
  const pathname = "/api/v2" + path.split("?")[0];
  const entry = Object.entries(spec.paths).find(([pattern]) =>
    new RegExp("^" + pattern.replace(/\{[^}]+\}/g, "[^/]+") + "$").test(
      pathname,
    ),
  );
  if (!entry) return false;
  const operation = (entry[1] as Record<string, unknown>)[
    method.toLowerCase()
  ] as
    | {
        responses: Record<
          string,
          { content: { "application/json": { schema: Schema } } }
        >;
      }
    | undefined;
  if (!operation) return false;
  const schema =
    operation.responses["200"]?.content?.["application/json"]?.schema;
  if (!schema || !matches(schema, value)) return false;
  // A live gateway must never return fixture balances or analyses.
  const rows = Array.isArray(value) ? value : [value];
  return rows.every(
    (row) =>
      !row ||
      typeof row !== "object" ||
      !("data_mode" in row) ||
      row.data_mode === "live",
  );
}
