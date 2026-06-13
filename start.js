#!/usr/bin/env node
const { spawn, execSync } = require("child_process");
const path = require("path");

const ROOT = __dirname;
const FRONTEND_DIR = path.join(ROOT, "webChannel");
const PORT = 1675;

// ── 构建前端 ─────────────────────────────────────────
console.log("=== 构建前端 ===");
try {
  execSync("npm run build", { cwd: FRONTEND_DIR, stdio: "inherit" });
} catch {
  console.error("❌ 前端构建失败");
  process.exit(1);
}

// ── 启动后端 ─────────────────────────────────────────
const pyCmd = process.platform === "win32" ? "python" : "python3";
console.log(`\n=== 启动后端 (${pyCmd}) ===`);

const pyProcess = spawn(pyCmd, ["-m", "lumen_agent.app"], {
  cwd: ROOT,
  stdio: "inherit",
  env: { ...process.env },
});

pyProcess.on("close", (code) => {
  console.log(`\n项目已退出，退出码：${code}`);
});

console.log(`\n✅ 启动成功，访问地址：http://localhost:${1675}`);
console.log("   按 Ctrl+C 停止服务\n");
