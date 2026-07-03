const { execSync } = require("child_process");
const path = require("path");
const fs = require("fs");

// ── 配置 ─────────────────────────────────────────────
const ROOT = __dirname;
const BACKEND_DIR = path.join(ROOT, "lumen_agent");
const FRONTEND_DIR = path.join(ROOT, "webChannel");
const VENV_DIR = path.join(ROOT, ".venv");
const PY_NEEDED = "3.11";

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

const runCapture = (cmd) => {
  try {
    return execSync(cmd, { encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] }).trim();
  } catch {
    return null;
  }
};

// 将 uv 所在的目录加入 PATH
const addUvToPath = () => {
  const uvHome = process.platform === "win32"
    ? path.join(process.env.USERPROFILE || "", ".cargo", "bin")
    : path.join(process.env.HOME || "/root", ".cargo", "bin");
  if (fs.existsSync(uvHome)) {
    process.env.PATH = `${uvHome}${path.delimiter}${process.env.PATH}`;
  }
  // Windows 上 uv 也可能装在 LOCALAPPDATA
  if (process.platform === "win32") {
    const uvLocal = path.join(process.env.LOCALAPPDATA || "", "uv", "bin");
    if (fs.existsSync(uvLocal)) {
      process.env.PATH = `${uvLocal}${path.delimiter}${process.env.PATH}`;
    }
  }
};

const isUvAvailable = () => {
  addUvToPath();
  return runCapture("uv --version") !== null;
};

const installUv = () => {
  console.log("→ 正在安装 uv...");
  if (process.platform === "win32") {
    run('powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"');
  } else {
    run('curl -LsSf https://astral.sh/uv/install.sh | sh');
  }
  addUvToPath();
};

// ── 主流程 ───────────────────────────────────────────
try {
  // ── 1. 检测 Python 版本 ──────────────────────────
  console.log("\n=== 1/3 检测 Python 环境 ===");

  // 确定候选命令
  const pyCandidates = process.platform === "win32"
    ? ["py", "python", "python3"]
    : ["python3", "python"];

  let pyCmd = null;    // 最终使用的 Python 命令
  let pyVer = null;    // 检测到的版本号 "x.y"
  let useVenv = false; // 是否使用虚拟环境

  for (const cmd of pyCandidates) {
    const ver = runCapture(`${cmd} --version`);
    if (ver) {
      const m = ver.match(/Python\s+(\d+)\.(\d+)/);
      if (m) {
        pyCmd = cmd;
        pyVer = `${m[1]}.${m[2]}`;
        console.log(`  检测到 ${ver}（${cmd}）`);
        break;
      }
    }
  }

  if (pyVer === PY_NEEDED) {
    // ✅ 系统已经是 Python 3.11，直接使用
    console.log(`✅ 系统 Python ${PY_NEEDED} 已就绪，直接使用`);
  } else {
    // ⚠️ 版本不对或未安装，通过 uv 强制安装 Python 3.11
    console.log(`⚠️  需要 Python ${PY_NEEDED}，当前: ${pyVer || "未安装"}`);
    console.log(`  将通过 uv 强制安装 Python ${PY_NEEDED} 到虚拟环境`);

    // 确保 uv 可用
    if (!isUvAvailable()) {
      // 如果有 pip 则优先用 pip 安装 uv
      if (pyCmd) {
        try {
          run(`${pyCmd} -m pip install uv -q`);
        } catch {
          installUv();
        }
      } else {
        installUv();
      }
    }

    if (!isUvAvailable()) {
      console.error("❌ uv 安装失败，请手动安装: https://docs.astral.sh/uv/");
      process.exit(1);
    }

    console.log(`✅ uv 就绪：${runCapture("uv --version")}`);

    // 安装 Python 3.11
    console.log(`→ 通过 uv 安装 Python ${PY_NEEDED}...`);
    run(`uv python install ${PY_NEEDED}`);

    // 创建 .venv（如果已存在则跳过）
    if (!fs.existsSync(VENV_DIR)) {
      console.log(`→ 创建虚拟环境 (.venv) › Python ${PY_NEEDED}...`);
      run(`uv venv --python ${PY_NEEDED}`, { cwd: ROOT });
    }

    // 设置 venv 中的 Python 路径
    pyCmd = process.platform === "win32"
      ? path.join(VENV_DIR, "Scripts", "python.exe")
      : path.join(VENV_DIR, "bin", "python3");

    // 验证 venv Python
    const venvVer = runCapture(`"${pyCmd}" --version`);
    console.log(`  虚拟环境 Python：${venvVer}`);
    useVenv = true;
  }

  // ── 2. 安装 Python 依赖 ──────────────────────────
  console.log("\n=== 2/3 安装 Python 依赖 ===");
  if (useVenv) {
    run(`uv pip install -r requirements.txt`, { cwd: BACKEND_DIR });
  } else {
    run(`${pyCmd} -m pip install -r requirements.txt`, { cwd: BACKEND_DIR });
  }
  console.log("✅ Python 依赖安装完成");

  // ── 3. 安装前端依赖 ──────────────────────────────
  console.log("\n=== 3/3 安装前端依赖 ===");
  run("npm install", { cwd: FRONTEND_DIR });

  // ── 4. 可选：安装 ACP 编码 agent 适配器 ──────────────────
  console.log("\n=== 可选：安装 ACP Sub-Agent 适配器 ===");
  console.log("  若需使用 Lumen 编排本地 Claude Code，可安装 ACP 适配器：");
  console.log("  npm install -g @agentclientprotocol/claude-agent-acp");
  // 检测是否已安装
  const acpVer = runCapture("claude-agent-acp --version") || runCapture("npx -y @agentclientprotocol/claude-agent-acp --version");
  if (acpVer) {
    console.log(`  ✅ claude-agent-acp 已就绪 (${acpVer})`);
  } else {
    console.log("  ℹ️  claude-agent-acp 未安装（跳过，不影响其他功能）");
  }

  console.log("\n=== ✅ 全部安装完成 ===");
} catch (err) {
  console.error("\n❌ 安装失败：", err.message);
  process.exit(1);
}
