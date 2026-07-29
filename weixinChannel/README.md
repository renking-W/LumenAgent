# LumenAgent 微信通道

该模块通过仓库内置的 weixin-agent-sdk 接收个人微信消息，并调用 LumenAgent 的完整 Agent API。微信消息会共享后端的会话历史、用户信息、记忆文件、工具系统和 Skill 系统，不是独立的单轮 Chat 接口。

当前支持：

- 管理员在前端扫码绑定和解除绑定
- FastAPI 启动时自动拉起微信通道，异常退出后自动重启
- 纯文本多轮对话，固定使用个人会话 wechat-personal
- Agent 工具直接执行，不进入人工审批
- 遇到工具调用时，先发送当前已经生成的增量正文
- Agent 完成后发送剩余正文

暂不支持图片、语音、视频和文件。

## 本地开发

微信通道需要 Node.js 22 或更高版本。首次安装依赖：

    cd weixinChannel
    npm install

正常使用时只需启动 LumenAgent 后端，后端生命周期会自动运行 src/main.ts。登录状态和内部 API Key 保存在 weixinChannel/data/，该目录不进入 Git。

终端扫码入口仅作为前端不可用时的故障恢复方式：

    npm run login

## Docker 部署

Docker 镜像已包含 Node.js 22 和微信依赖。运行容器时持久化绑定目录：

    -v "$(pwd)/weixinChannel/data:/app/weixinChannel/data"

容器对外仍然只开放 FastAPI 的 1675 端口；微信控制服务只监听容器内的 127.0.0.1:1676。

可选环境变量：

| 变量 | 默认值 | 说明 |
|---|---:|---|
| LUMEN_WECHAT_SESSION_ID | wechat-personal | 微信使用的固定会话 ID |
| LUMEN_REQUEST_TIMEOUT_MS | 600000 | 单轮 Agent 请求超时毫秒数 |
| WEIXIN_MESSAGE_CHUNK_SIZE | 1800 | 微信单条消息的最大 Unicode 字符数 |

approval_mode 固定为 none，表示工具直接执行，不等待人工审批。
