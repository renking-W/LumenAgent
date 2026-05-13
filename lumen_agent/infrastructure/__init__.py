"""基础设施层包：实现 `domain/ports.py` 中描述的协议（HTTP 客户端、数据库、向量库等）。

特点：
- 允许依赖第三方 SDK（httpx、sqlalchemy 等）。
- 尽量把「解析上游 JSON」与「业务决策」分开：前者在此，后者在 `application/`。
"""
