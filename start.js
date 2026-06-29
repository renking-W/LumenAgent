#!/usr/bin/env node
const { spawn, execSync } = require("child_process");
const path = require("path");
const fs = require("fs");

const ROOT = __dirname;
const BACKEND_DIR = path.join(ROOT, "lumen_agent");
const FRONTEND_DIR = path.join(ROOT, "webChannel");
const DIST_DIR = path.join(FRONTEND_DIR, "dist");
const VENV_DIR = path.join(ROOT, ".venv");

// Flask 代理端口（反向代理到 FastAPI 21675）
const PROXY_PORT = 1675;

// ── 工具函数 ─────────────────────────────────────────
function getPyCmd() {
  // 优先使用虚拟环境中的 Python
  const venvPython = process.platform === "win32"
    ? path.join(VENV_DIR, "Scripts", "python.exe")
    : path.join(VENV_DIR, "bin", "python3");

  if (fs.existsSync(venvPython)) {
    return venvPython;
  }

  // 回退到系统 Python
  if (process.platform === "win32") {
    try {
      execSync("py --version", { stdio: "ignore" });
      return "py";
    } catch {
      return "python";
    }
  }
  return "python3";
}

// ── 依赖检查 ─────────────────────────────────────────
try {
  // Python 可用性
  const pyCmd = getPyCmd();
  execSync(`"${pyCmd}" --version`, { stdio: "ignore" });

  // 前端产物
  if (!fs.existsSync(path.join(DIST_DIR, "index.html"))) {
    console.log("⚠️  未检测到前端构建产物，开始构建...");
    execSync("npm run build", { cwd: FRONTEND_DIR, stdio: "inherit" });
  }

  // Python 依赖
  try {
    execSync(`"${pyCmd}" -c "import fastapi"`, { stdio: "ignore" });
  } catch {
    console.log("⚠️  未检测到 Python 依赖，开始安装...");
    execSync(`"${pyCmd}" -m pip install -r requirements.txt`, { cwd: BACKEND_DIR, stdio: "inherit" });
  }

  // Node 依赖
  if (!fs.existsSync(path.join(FRONTEND_DIR, "node_modules"))) {
    console.log("⚠️  未检测到前端依赖，开始安装...");
    execSync("npm install", { cwd: FRONTEND_DIR, stdio: "inherit" });
  }
} catch (err) {
  console.error("❌ 环境检查失败：", err.message);
  process.exit(1);
}

// ── 启动后端 ─────────────────────────────────────────
const pyCmd = getPyCmd();
console.log(`\n=== 启动后端 (${pyCmd}) ===`);

const pyProcess = spawn(pyCmd, ["-m", "lumen_agent.app"], {
  cwd: ROOT,
  stdio: "inherit",
  env: { ...process.env },
});

pyProcess.on("close", (code) => {
  console.log(`\n项目已退出，退出码：${code}`);
});

const url = `http://localhost:${PROXY_PORT}`;
console.log(`\n✅ 启动成功，访问地址：${url}`);
console.log("   按 Ctrl+C 停止服务\n");
