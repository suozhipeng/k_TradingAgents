import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(fileURLToPath(new URL("..", import.meta.url)));
const api = readFileSync(resolve(root, "src/hooks/useApi.ts"), "utf8");
const hub = readFileSync(resolve(root, "src/components/DataHub.tsx"), "utf8");

const required = [
  [api, "getRefreshOptions()", "API client must expose the server refresh-options contract"],
  [api, '"/api/v1/data/refresh/options"', "refresh-options endpoint must be used"],
  [hub, "api.getRefreshOptions()", "Data Hub must load server-owned options"],
  [hub, "refreshOptions?.intervals.map", "Data Hub intervals must be rendered from the server contract"],
  [hub, "refreshOptions?.modes.map", "Data Hub modes must be rendered from the server contract"],
];

for (const [source, needle, message] of required) {
  if (!source.includes(needle)) throw new Error(message);
}

console.log("WebUI release contract checks passed");
