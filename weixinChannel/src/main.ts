import { createServer, type IncomingMessage, type ServerResponse } from "node:http";

import {
  DEFAULT_BASE_URL,
  DEFAULT_ILINK_BOT_TYPE,
  clearAllWeixinAccounts,
  isLoggedIn,
  normalizeAccountId,
  registerWeixinAccountId,
  saveWeixinAccount,
  start,
  startWeixinLoginWithQr,
  waitForWeixinLogin,
  type Bot,
} from "../vendor/weixin-agent-sdk/packages/sdk/index.js";

import { LumenAgentBridge } from "./lumen-agent.js";

type ChannelPhase = "unbound" | "waiting_scan" | "scanned" | "bound" | "running" | "error";

type ChannelStatus = {
  phase: ChannelPhase;
  bound: boolean;
  running: boolean;
  qrcode_url?: string;
  account_id?: string;
  last_error?: string;
};

function requiredEnvironment(name: string): string {
  const value = process.env[name]?.trim();
  if (!value) throw new Error(`缺少环境变量 ${name}。`);
  return value;
}

function positiveInteger(value: string | undefined, fallback: number): number {
  if (!value) return fallback;
  const parsed = Number.parseInt(value, 10);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : fallback;
}

const controlToken = requiredEnvironment("WEIXIN_CONTROL_TOKEN");
const lumenApiKey = requiredEnvironment("LUMEN_API_KEY");
const lumenBaseUrl = process.env.LUMEN_BASE_URL?.trim() || "http://127.0.0.1:1675";
const sessionId = process.env.LUMEN_WECHAT_SESSION_ID?.trim() || "wechat-personal";
const controlPort = positiveInteger(process.env.WEIXIN_CONTROL_PORT, 1676);
const requestTimeoutMs = positiveInteger(process.env.LUMEN_REQUEST_TIMEOUT_MS, 10 * 60 * 1000);
const messageChunkSize = positiveInteger(process.env.WEIXIN_MESSAGE_CHUNK_SIZE, 1800);

let status: ChannelStatus = {
  phase: isLoggedIn() ? "bound" : "unbound",
  bound: isLoggedIn(),
  running: false,
};
let bot: Bot | undefined;
let botAbortController: AbortController | undefined;
let bindingTask: Promise<void> | undefined;
let bindingGeneration = 0;

const bridge = new LumenAgentBridge({
  baseUrl: lumenBaseUrl,
  apiKey: lumenApiKey,
  sessionId,
  timeoutMs: requestTimeoutMs,
});

/** 按 Unicode 字符切分微信文本，避免长消息发送失败或截断代理对。 */
function splitMessage(text: string): string[] {
  const characters = Array.from(text);
  const chunks: string[] = [];
  for (let index = 0; index < characters.length; index += messageChunkSize) {
    chunks.push(characters.slice(index, index + messageChunkSize).join(""));
  }
  return chunks;
}

async function stopBot(): Promise<void> {
  const currentBot = bot;
  bot = undefined;
  botAbortController?.abort();
  botAbortController = undefined;
  if (currentBot) await currentBot.wait().catch(() => undefined);
}

/** 已绑定时启动消息长轮询；异常退出后由 Python 守护进程重启整个通道。 */
function startBot(): void {
  if (bot || !isLoggedIn()) return;

  const controller = new AbortController();
  botAbortController = controller;
  bot = start(bridge, { abortSignal: controller.signal });
  bridge.setIntermediateSender(async (text) => {
    if (!bot) throw new Error("微信 Bot 尚未运行。");
    for (const chunk of splitMessage(text)) await bot.sendMessage(chunk);
  });

  status = { ...status, phase: "running", bound: true, running: true, last_error: undefined };
  bot.wait().catch((error: unknown) => {
    if (controller.signal.aborted) return;
    const message = error instanceof Error ? error.message : String(error);
    bot = undefined;
    botAbortController = undefined;
    status = { ...status, phase: "error", running: false, last_error: message };
    console.error(`[weixinChannel] 微信消息循环异常: ${message}`);
  });
}

async function startBinding(): Promise<ChannelStatus> {
  if (status.bound) throw new Error("微信已经绑定，如需更换账号请先解绑。");
  if (bindingTask) return status;

  const started = await startWeixinLoginWithQr({
    apiBaseUrl: DEFAULT_BASE_URL,
    botType: DEFAULT_ILINK_BOT_TYPE,
    force: true,
  });
  if (!started.qrcodeUrl) throw new Error(started.message || "无法生成微信登录二维码。");

  status = { phase: "waiting_scan", bound: false, running: false, qrcode_url: started.qrcodeUrl };
  const generation = ++bindingGeneration;
  bindingTask = (async () => {
    const result = await waitForWeixinLogin({
      sessionKey: started.sessionKey,
      apiBaseUrl: DEFAULT_BASE_URL,
      botType: DEFAULT_ILINK_BOT_TYPE,
      timeoutMs: 8 * 60 * 1000,
      onStatus(update) {
        status = {
          ...status,
          phase: update.status === "scaned" ? "scanned" : status.phase,
          qrcode_url: update.qrcodeUrl ?? status.qrcode_url,
        };
      },
    });

    if (!result.connected || !result.botToken || !result.accountId) {
      throw new Error(result.message || "微信绑定失败。");
    }

    // 解绑会使当前绑定代次失效，避免旧轮询稍后完成后重新写入凭据。
    if (generation !== bindingGeneration) return;

    const accountId = normalizeAccountId(result.accountId);
    saveWeixinAccount(accountId, {
      token: result.botToken,
      baseUrl: result.baseUrl,
      userId: result.userId,
    });
    registerWeixinAccountId(accountId);
    status = { phase: "bound", bound: true, running: false, account_id: accountId };
    startBot();
  })()
    .catch((error: unknown) => {
      if (generation !== bindingGeneration) return;
      const message = error instanceof Error ? error.message : String(error);
      status = { phase: "error", bound: false, running: false, last_error: message };
      console.error(`[weixinChannel] 微信绑定失败: ${message}`);
    })
    .finally(() => {
      bindingTask = undefined;
    });

  return status;
}

async function unbind(): Promise<ChannelStatus> {
  bindingGeneration += 1;
  await stopBot();
  clearAllWeixinAccounts();
  status = { phase: "unbound", bound: false, running: false };
  return status;
}

function writeJson(response: ServerResponse, code: number, body: unknown): void {
  response.writeHead(code, { "Content-Type": "application/json; charset=utf-8" });
  response.end(JSON.stringify(body));
}

function authorized(request: IncomingMessage): boolean {
  return request.headers.authorization === `Bearer ${controlToken}`;
}

const server = createServer(async (request, response) => {
  if (!authorized(request)) {
    writeJson(response, 401, { detail: "invalid control token" });
    return;
  }

  try {
    const method = request.method ?? "GET";
    const path = new URL(request.url ?? "/", "http://127.0.0.1").pathname;
    if (method === "GET" && path === "/status") {
      writeJson(response, 200, status);
      return;
    }
    if (method === "POST" && path === "/binding") {
      writeJson(response, 202, await startBinding());
      return;
    }
    if (method === "DELETE" && path === "/binding") {
      writeJson(response, 200, await unbind());
      return;
    }
    writeJson(response, 404, { detail: "not found" });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    writeJson(response, 409, { detail: message });
  }
});

async function shutdown(): Promise<void> {
  await stopBot();
  server.close();
}

process.once("SIGINT", () => void shutdown());
process.once("SIGTERM", () => void shutdown());

server.listen(controlPort, "127.0.0.1", () => {
  console.log(`[weixinChannel] 控制服务已启动: 127.0.0.1:${controlPort}`);
  if (status.bound) startBot();
});
