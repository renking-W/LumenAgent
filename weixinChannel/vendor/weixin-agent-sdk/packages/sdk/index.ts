export type { Agent, ChatRequest, ChatResponse } from "./src/agent/interface.js";
export { Bot, isLoggedIn, login, logout, start } from "./src/bot.js";
export type { LoginOptions, StartOptions } from "./src/bot.js";
export {
  DEFAULT_ILINK_BOT_TYPE,
  startWeixinLoginWithQr,
  waitForWeixinLogin,
} from "./src/auth/login-qr.js";
export type {
  WeixinQrStartResult,
  WeixinQrWaitResult,
} from "./src/auth/login-qr.js";
export {
  DEFAULT_BASE_URL,
  clearAllWeixinAccounts,
  normalizeAccountId,
  registerWeixinAccountId,
  saveWeixinAccount,
} from "./src/auth/accounts.js";
