---
name: web-search-google
description: 使用 Google Custom Search API 做精确网络搜索的最佳实践，包含查询构造、配额管理与错误处理。
primaryEnv: GOOGLE_CSE_API_KEY
requires:
  env:
    - GOOGLE_CSE_CX
emoji: 🔎
homepage: https://developers.google.com/custom-search/v1/overview
---

# web-search-google

本技能指导如何通过 Google Custom Search JSON API 发起搜索请求。

## 环境变量

| 变量 | 说明 |
|------|------|
| `GOOGLE_CSE_API_KEY` | Google Cloud 项目的 API Key |
| `GOOGLE_CSE_CX` | 自定义搜索引擎 ID（Custom Search Engine ID） |

## 使用方式

调用 `web_search` 工具时，指定 `engine: google` 参数：

```json
{
  "query": "Python asyncio 最佳实践",
  "engine": "google",
  "max_results": 5,
  "region": "zh-cn"
}
```

## 查询构造技巧

- 使用 `site:` 限定来源，如 `site:docs.python.org asyncio`
- 使用引号做精确匹配，如 `"event loop" Python`
- 使用 `-` 排除词，如 `asyncio -tornado`

## 配额说明

Google Custom Search 免费额度为每天 100 次查询，超出后需付费。建议：
1. 缓存已搜索的结果，避免重复请求
2. 合并多个子问题为一次宽泛查询

## 错误处理

| HTTP 状态码 | 含义 | 处理建议 |
|------------|------|----------|
| 400 | 参数错误 | 检查 `cx` 格式 |
| 403 | API Key 无效或配额耗尽 | 检查 key 和配额 |
| 429 | 请求频率过高 | 加间隔重试 |
