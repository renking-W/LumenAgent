# 技能模块

## 1. 技能机制代码

| 文件 | 作用 |
|---|---|
| `lumen_agent/agent/skills/__init__.py` | 技能子包入口 |
| `lumen_agent/agent/skills/loader.py` | `load_skills()` — 扫描 `work_space/skills/` 目录，读取 SKILL.md 解析技能定义 |
| `lumen_agent/agent/skills/meta.py` | 技能元数据模型（`SkillMeta` 等数据类） |

## 2. 技能定义文件

| 文件 | 作用 |
|---|---|
| `work_space/skills/web-search-google/SKILL.md` | Google 搜索技能 |
| `work_space/skills/self-improving-agent/SKILL.md` | 自我改进 Agent 技能 |
| `work_space/skills/self-improving-agent/_meta.json` | 技能元信息（版本、描述） |
| `work_space/skills/self-improving-agent/README.md` | 说明文档 |
| `work_space/skills/self-improving-agent/assets/` | 相关文档资产 |
| `work_space/skills/self-improving-agent/references/` | 参考文档 |
| `work_space/skills/self-improving-agent/hooks/` | 钩子脚本 |
| `work_space/skills/self-improving-agent/scripts/` | 辅助脚本 |

## 3. 使用技能的调用方

| 文件 | 作用 |
|---|---|
| `lumen_agent/agent/prompts/builder.py` | `build_system_prompt()` — 把技能定义序列化进 system prompt |
| `lumen_agent/application/chat_service.py` | `reply_with_agent()` — 调用 `load_skills()` 获取技能列表 |
| `lumen_agent/api/routers/skills.py` | API 路由 — 暴露技能列表给前端 |
| `lumen_agent/app.py` | 挂载 skills 路由 |

## 加载流程

```
chat_service.py
    → load_skills()
        → 扫描 work_space/skills/ 子目录
        → 读取每个子目录下的 SKILL.md
        → 解析为 SkillMeta 对象列表

    → build_system_prompt(tools, skills)
        → 把技能描述格式化拼到 system prompt 里
```