// Bun 런타임 부트스트랩: function.json 의 handler("파일.함수")를 불러 이벤트를 넘기고 결과를 마커 줄로 내보낸다.
import { existsSync, readFileSync } from "node:fs";

const TOKEN = process.env.FN_RESULT_TOKEN ?? "";
delete process.env.FN_RESULT_TOKEN;
const START = Date.now();
const TIMEOUT_MS = Number(process.env.FN_TIMEOUT_MS ?? "30000");

function emit(obj) {
  process.stdout.write(`\n__FN_RESULT_${TOKEN}__ ${JSON.stringify(obj)}\n`);
}

try {
  const cfg = JSON.parse(readFileSync("/var/task/function.json", "utf8"));
  const dot = cfg.handler.lastIndexOf(".");
  const file = cfg.handler.slice(0, dot), name = cfg.handler.slice(dot + 1);
  const path = ["ts", "js", "mjs", "cjs"].map((e) => `/var/task/${file}.${e}`).find(existsSync);
  if (!path) throw new Error(`핸들러 파일을 찾을 수 없습니다: ${file}.(ts|js|mjs|cjs)`);
  const mod = await import(path);
  const ctx = {
    runId: process.env.FN_RUN_ID, functionName: process.env.FN_FUNCTION, version: process.env.FN_VERSION,
    remainingMs: () => Math.max(0, TIMEOUT_MS - (Date.now() - START)), log: (m) => console.log(m),
  };
  const result = await (mod[name] ?? mod.default?.[name])(JSON.parse(readFileSync("/tmp/event.json", "utf8")), ctx);
  emit({ ok: true, result: result === undefined ? null : result });
} catch (e) {
  console.error(e?.stack ?? String(e));
  emit({ ok: false, error: { type: e?.name ?? "Error", message: String(e?.message ?? e).slice(0, 2000) } });
  process.exit(1);
}
