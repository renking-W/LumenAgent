"""领域层包：放「不依赖外部 I/O」的核心概念与端口（Protocol）。

注意依赖方向：
- `domain` 不应 import `infrastructure`（否则容易循环依赖，且违背整洁架构边界）。
- `infrastructure` 可以实现 `domain` 描述的协议（结构子类型）。
"""
