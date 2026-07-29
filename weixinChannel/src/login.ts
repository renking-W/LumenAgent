import { login } from "../vendor/weixin-agent-sdk/packages/sdk/index.js";

/** 保留终端扫码入口，便于前端不可用时进行故障恢复。 */
login().catch((error: unknown) => {
  const message = error instanceof Error ? error.stack ?? error.message : String(error);
  console.error(`[weixinChannel] 登录失败: ${message}`);
  process.exitCode = 1;
});
