const { execSync } = require("child_process");
const path = require("path");

// ── 配置 ─────────────────────────────────────────────
const ROOT = __dirname;
const BACKEND_DIR = path.join(ROOT, "lumen_agent");
const FRONTEND_DIR = path.join(ROOT, "webChannel");

// ── Node.js 版本校验 ────────────────────────────────
const NODE_MIN = 18;

const nodeVer = process.version; // e.g. "v20.19.0"
const parts = nodeVer.slice(1).split(".").map(Number);
if (parts[0] < NODE_MIN) {
  console.error(`❌ Node.js 版本过低：当前 ${nodeVer}，需要 v${NODE_MIN}+`);
  process.exit(1);
}
console.log(`✅ Node.js ${nodeVer}`);

// ── 工具函数 ─────────────────────────────────────────
const run = (cmd, opts = {}) => {
  console.log(`\n> ${cmd}`);
  execSync(cmd, { stdio: "inherit", ...opts });
};

const getPyCmd = () => {
  // Windows 上优先用 py，否则 python；Unix 用 python3
  if (process.platform === "win32") {
    try {
      execSync("py --version", { stdio: "ignore" });
      return "py";
    } catch {
      return "python";
    }
  }
  return "python3";
};

// ── 主流程 ───────────────────────────────────────────
try {
  // 1. 安装 Python 依赖
  console.log("\n=== 1/2 安装 Python 依赖 ===");
  const pyCmd = getPyCmd();

  // 检查 pip 是否可用
  try {
    execSync(`${pyCmd} -m pip --version`, { stdio: "ignore" });
  } catch {
    console.error(`❌ pip 不可用，请确认 ${pyCmd} 已安装 pip`);
    process.exit(1);
  }

  run(`${pyCmd} -m pip install -r requirements.txt`, { cwd: BACKEND_DIR });
  console.log("✅ Python 依赖安装完成");

  // 2. 安装前端依赖
  console.log("\n=== 2/2 安装前端依赖 ===");
  run("npm install", { cwd: FRONTEND_DIR });

  console.log("\n=== ✅ 全部安装完成 ===");
} catch (err) {
  console.error("\n❌ 安装失败：", err.message);
  process.exit(1);
}
