import json
import re
from pathlib import Path
from jsonschema import Draft202012Validator

SPEC = json.loads(Path(__file__).with_name("openapi.json").read_text(encoding="utf-8"))
SCHEMAS = SPEC["components"]["schemas"]
READ = {path: value["get"] for path, value in SPEC["paths"].items() if "get" in value}
WRITES = {p: SPEC["paths"][p]["post"] for p in ["/api/v2/analyze", "/api/v2/watchlist", "/api/v2/scanner/pause", "/api/v2/scanner/tick", "/api/v2/analysis-tracking", "/api/v2/analysis-tracking/{tracking_id}", "/api/v2/analysis-tracking/{tracking_id}/notification-policy"]}

PROFILE_WRITES = {p: v["post"] for p,v in SPEC["paths"].items() if "post" in v and "strategy-profiles" in p}

RESEARCH_READS = {p:v["post"] for p,v in SPEC["paths"].items() if p.endswith("/research")}

NOTIFICATION_WRITES = {p:v["post"] for p,v in SPEC["paths"].items() if p.endswith("/notification-preferences")}

DISCOVERY_WRITES = {p:v["post"] for p,v in SPEC["paths"].items() if "post" in v and "/market-scanner" in p}

PAPER_WRITES = {p: v["post"] for p, v in SPEC["paths"].items() if "post" in v and p.startswith("/api/v2/portfolios/") and "strategy-profiles" not in p and "notification-preferences" not in p and "/market-scanner" not in p}

def validate(schema, value):
    Draft202012Validator({**schema, "components": {"schemas": SCHEMAS}}).validate(value)


def route(path, method, paper_enabled=False):
    routes = READ if method == "GET" else {**WRITES, **RESEARCH_READS, **PROFILE_WRITES, **NOTIFICATION_WRITES, **DISCOVERY_WRITES, **(PAPER_WRITES if paper_enabled else {})} if method == "POST" else {}
    for pattern, operation in routes.items():
        regex = pattern.replace("{analysis_id}", "(?P<analysis_id>[a-f0-9]{64})").replace("{portfolio_id}", "(?P<portfolio_id>AUTO|MANUAL)")
        regex = regex.replace("{order_id}", "(?P<order_id>[a-f0-9]{64})").replace("{position_id}", "(?P<position_id>[a-f0-9]{64})")
        regex = regex.replace("{tracking_id}", "(?P<tracking_id>[a-f0-9]{64})")
        regex = regex.replace("{profile_id}", "(?P<profile_id>[a-f0-9]{64})")
        regex = regex.replace("{opportunity_id}", "(?P<opportunity_id>[a-f0-9]{64})")
        match = re.fullmatch(regex, path)
        if match:
            return operation, match.groupdict()
    return None, {}


def query_parameters(operation, params):
    allowed = {p["name"]: p["schema"] for p in operation.get("parameters", []) if p["in"] == "query"}
    items = list(params.multi_items())
    if len({k for k, _ in items}) != len(items) or any(k not in allowed for k, _ in items):
        raise ValueError("Query not allowed")
    for key, value in items:
        schema = allowed[key]
        if schema.get("type") == "integer":
            value = int(value)
        elif schema.get("type") == "boolean":
            if value not in ("true", "false"):
                raise ValueError("Boolean required")
            value = value == "true"
        validate(schema, value)
    return items
