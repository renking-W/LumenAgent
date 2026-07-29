import { createParser } from "eventsource-parser";
import type {
  Agent,
  ChatRequest,
  ChatResponse,
} from "../vendor/weixin-agent-sdk/packages/sdk/index.js";

type IntermediateSender = (text: string) => Promise<void>;

type LumenStreamEvent = {
  type: string;
  data?: {
    delta?: unknown;
    message?: unknown;
  };
};

export type LumenAgentOptions = {
  baseUrl: string;
  apiKey: string;
  sessionId: string;
  timeoutMs: number;
};

/**
 * 将微信 SDK 的单轮请求转换为 LumenAgent SSE 对话。
 * 会话、历史、记忆、工具和 Skill 均继续由 LumenAgent 后端统一管理。
 */
export class LumenAgentBridge implements Agent {
  private readonly baseUrl: string;
  private readonly apiKey: string;
  private readonly sessionId: string;
  private readonly timeoutMs: number;
  private sendIntermediate: IntermediateSender | undefined;

  constructor(options: LumenAgentOptions) {
    this.baseUrl = options.baseUrl.replace(/\/+$/, "");
    this.apiKey = options.apiKey;
    this.sessionId = options.sessionId;
    this.timeoutMs = options.timeoutMs;
  }

  /** Bot 创建完成后注入中间消息发送能力，避免 SDK 初始化时的循环依赖。 */
  setIntermediateSender(sender: IntermediateSender): void {
    this.sendIntermediate = sender;
  }

  async chat(request: ChatRequest): Promise<ChatResponse> {
    if (request.media) {
      return { text: "当前微信接入暂只支持文字消息，图片和文件将在后续版本接入。" };
    }

    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), this.timeoutMs);

    try {
      const response = await fetch(`${this.baseUrl}/v1/chat/stream`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${this.apiKey}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          message: request.text,
          session_id: this.sessionId,
          mode: "agent",
          // none 表示不进入人工审批，Agent 可以直接执行已注册工具。
          approval_mode: "none",
          mcp_server_ids: [],
          image_urls: null,
          file_attachments: [],
        }),
        signal: controller.signal,
      });

      if (!response.ok) {
        const detail = await response.text();
        throw new Error(`LumenAgent 请求失败 (${response.status}): ${detail}`);
      }
      if (!response.body) {
        throw new Error("LumenAgent 没有返回可读取的事件流。");
      }

      return await this.consumeStream(response.body);
    } catch (error) {
      if (error instanceof Error && error.name === "AbortError") {
        throw new Error(`LumenAgent 对话超过 ${this.timeoutMs}ms，已停止等待。`);
      }
      throw error;
    } finally {
      clearTimeout(timeout);
    }
  }

  private async consumeStream(stream: ReadableStream<Uint8Array>): Promise<ChatResponse> {
    const reader = stream.getReader();
    const decoder = new TextDecoder();
    const eventDataQueue: string[] = [];
    let pendingText = "";
    let streamCompleted = false;

    const parser = createParser({
      onEvent(event) {
        eventDataQueue.push(event.data);
      },
    });

    /** 顺序处理当前网络块解析出的事件，确保工具前文本先发完再继续读取。 */
    const processQueuedEvents = async (): Promise<void> => {
      while (eventDataQueue.length > 0) {
        const rawData = eventDataQueue.shift();
        if (!rawData) continue;
        if (rawData === "[DONE]") {
          streamCompleted = true;
          continue;
        }

        let event: LumenStreamEvent;
        try {
          event = JSON.parse(rawData) as LumenStreamEvent;
        } catch {
          throw new Error(`LumenAgent 返回了无法解析的 SSE 数据: ${rawData}`);
        }

        if (event.type === "text" && typeof event.data?.delta === "string") {
          pendingText += event.data.delta;
          continue;
        }

        // tool_calls 是模型决定调用工具的通知，tool_use 是单个工具开始执行的通知。
        if (event.type === "tool_calls" || event.type === "tool_use") {
          if (pendingText.trim() && this.sendIntermediate) {
            await this.sendIntermediate(pendingText.trim());
            pendingText = "";
          }
          continue;
        }

        if (event.type === "error") {
          const message = event.data?.message;
          throw new Error(typeof message === "string" ? message : "LumenAgent 对话失败。");
        }
      }
    };

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        parser.feed(decoder.decode(value, { stream: true }));
        await processQueuedEvents();
      }
      parser.feed(decoder.decode());
      await processQueuedEvents();
    } finally {
      reader.releaseLock();
    }

    if (!streamCompleted) {
      throw new Error("LumenAgent 事件流在完成标记前中断。");
    }

    const finalText = pendingText.trim();
    return finalText ? { text: finalText } : {};
  }
}
