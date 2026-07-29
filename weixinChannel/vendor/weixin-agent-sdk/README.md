# weixin-agent-sdk

> 本项目非微信官方项目，代码由 [@tencent-weixin/openclaw-weixin](https://npmx.dev/package/@tencent-weixin/openclaw-weixin) 改造而来，仅供学习交流使用。

微信 AI Agent 桥接框架 —— 通过简单的 Agent 接口，将任意 AI 后端接入微信。

## 项目结构

```
packages/
  sdk/                  weixin-agent-sdk —— 微信桥接 SDK
  weixin-acp/           ACP (Agent Client Protocol) 适配器
  example-openai/       基于 OpenAI 的示例
```

## 通过 ACP 接入 Claude Code, Codex, kimi-cli 等 Agent

[ACP (Agent Client Protocol)](https://agentclientprotocol.com/) 是一个开放的 Agent 通信协议。如果你已有兼容 ACP 的 agent，可以直接通过 [`weixin-acp`](https://www.npmjs.com/package/weixin-acp) 接入微信，无需编写任何代码。


### Claude Code

```bash
npx weixin-acp claude-code
```

### Codex

```bash
npx weixin-acp codex
```

### 其它 ACP Agent

比如 kimi-cli：

```bash
npx weixin-acp start -- kimi acp
```

`--` 后面的部分就是你的 ACP agent 启动命令，`weixin-acp` 会自动以子进程方式启动它，通过 JSON-RPC over stdio 进行通信。

更多 ACP 兼容 agent 请参考 [ACP agent 列表](https://agentclientprotocol.com/get-started/agents)。

## 自定义 Agent

SDK 主要导出三样东西：

- **`Agent`** 接口 —— 实现它就能接入微信
- **`login()`** —— 扫码登录
- **`start(agent)`** —— 启动消息循环，立即返回可主动发消息的 `Bot`

### Agent 接口

```typescript
interface Agent {
  chat(request: ChatRequest): Promise<ChatResponse>;
}

interface ChatRequest {
  conversationId: string;         // 用户标识，可用于维护多轮对话
  text: string;                   // 文本内容
  media?: {                       // 附件（图片/语音/视频/文件）
    type: "image" | "audio" | "video" | "file";
    filePath: string;             // 本地文件路径（已下载解密）
    mimeType: string;
    fileName?: string;
  };
}

interface ChatResponse {
  text?: string;                  // 回复文本（支持 markdown，发送前自动转纯文本）
  media?: {                       // 回复媒体
    type: "image" | "video" | "file";
    url: string;                  // 本地路径或 HTTPS URL
    fileName?: string;
  };
}
```

### 最简示例

```typescript
import { login, start, type Agent } from "weixin-agent-sdk";

const echo: Agent = {
  async chat(req) {
    return { text: `你说了: ${req.text}` };
  },
};

await login();
const bot = start(echo);
await bot.wait();
```

### 完整示例（自己管理对话历史）

```typescript
import { login, start, type Agent } from "weixin-agent-sdk";

const conversations = new Map<string, string[]>();

const myAgent: Agent = {
  async chat(req) {
    const history = conversations.get(req.conversationId) ?? [];
    history.push(req.text);

    // 调用你的 AI 服务...
    const reply = await callMyAI(history);

    history.push(reply);
    conversations.set(req.conversationId, history);
    return { text: reply };
  },
};

await login();
const bot = start(myAgent);
await bot.wait();
```

### 主动发送消息

`start()` 会立即返回 `Bot` 实例。`Bot` 提供了 `sendMessage()`，可以在收到微信消息之外，主动给当前登录用户发送内容；如果是 CLI/脚本程序，可以用 `bot.wait()` 等待消息循环结束。

```typescript
import { login, start, type Agent } from "weixin-agent-sdk";

const agent: Agent = {
  async chat(req) {
    if (req.text === "ping") {
      return { text: "pong" };
    }
    return { text: `收到：${req.text}` };
  },
};

await login();
const bot = start(agent);

setInterval(() => {
  void bot.sendMessage("定时提醒：记得查看最新状态");
}, 60_000);

await bot.wait();
```

也可以主动发送完整的 `ChatResponse`，包括图片、视频或文件：

```typescript
await bot.sendMessage({
  text: "这是最新报表",
  media: {
    type: "file",
    url: "./reports/daily.pdf",
    fileName: "daily.pdf",
  },
});
```

注意事项：

- 主动发送依赖微信下发的 `context_token`
- 需要在 `start()` 运行期间，至少先收到过当前账号的一条入站消息
- `context_token` 有时效，可能是 24 小时；过期后需要再次收到新消息才能继续主动发送

### OpenAI 示例

`packages/example-openai/` 是一个完整的 OpenAI Agent 实现，支持多轮对话和图片输入：

```bash
pnpm install

# 扫码登录微信
pnpm run login -w packages/example-openai

# 启动 bot
OPENAI_API_KEY=sk-xxx pnpm run start -w packages/example-openai
```

支持的环境变量：

| 变量 | 必填 | 说明 |
|------|------|------|
| `OPENAI_API_KEY` | 是 | OpenAI API Key |
| `OPENAI_BASE_URL` | 否 | 自定义 API 地址（兼容 OpenAI 接口的第三方服务） |
| `OPENAI_MODEL` | 否 | 模型名称，默认 `gpt-5.4` |
| `SYSTEM_PROMPT` | 否 | 系统提示词 |

## 支持的消息类型

### 接收（微信 → Agent）

| 类型 | `media.type` | 说明 |
|------|-------------|------|
| 文本 | — | `request.text` 直接拿到文字 |
| 图片 | `image` | 自动从 CDN 下载解密，`filePath` 指向本地文件 |
| 语音 | `audio` | SILK 格式自动转 WAV（需安装 `silk-wasm`） |
| 视频 | `video` | 自动下载解密 |
| 文件 | `file` | 自动下载解密，保留原始文件名 |
| 引用消息 | — | 被引用的文本拼入 `request.text`，被引用的媒体作为 `media` 传入 |
| 语音转文字 | — | 微信侧转写的文字直接作为 `request.text` |

### 发送（Agent → 微信）

| 类型 | 用法 |
|------|------|
| 文本 | 返回 `{ text: "..." }` |
| 图片 | 返回 `{ media: { type: "image", url: "/path/to/img.png" } }` |
| 视频 | 返回 `{ media: { type: "video", url: "/path/to/video.mp4" } }` |
| 文件 | 返回 `{ media: { type: "file", url: "/path/to/doc.pdf" } }` |
| 文本 + 媒体 | `text` 和 `media` 同时返回，文本作为附带说明发送 |
| 远程图片 | `url` 填 HTTPS 链接，SDK 自动下载后上传到微信 CDN |
| 主动发送 | 通过 `const bot = start(agent)` 后调用 `bot.sendMessage(...)` |

## 内置斜杠命令

在微信中发送以下命令：

- `/echo <消息>` —— 直接回复（不经过 Agent），附带通道耗时统计
- `/toggle-debug` —— 开关 debug 模式，启用后每条回复追加全链路耗时

## 技术细节

- 使用 **长轮询** (`getUpdates`) 接收消息，无需公网服务器
- 媒体文件通过微信 CDN 中转，**AES-128-ECB** 加密传输
- 单账号模式：每次 `login` 覆盖之前的账号
- 断点续传：`get_updates_buf` 持久化到 `~/.openclaw/`，重启后从上次位置继续
- 会话过期自动重连（errcode -14 触发 1 小时冷却后恢复）
- Node.js >= 22

## Star History

<a href="https://www.star-history.com/?repos=wong2%2Fweixin-agent-sdk&type=date&legend=top-left">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/image?repos=wong2/weixin-agent-sdk&type=date&theme=dark&legend=top-left" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/image?repos=wong2/weixin-agent-sdk&type=date&legend=top-left" />
   <img alt="Star History Chart" src="https://api.star-history.com/image?repos=wong2/weixin-agent-sdk&type=date&legend=top-left" />
 </picture>
</a>
