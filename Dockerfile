# 前端构建阶段仅负责生成 Vue 静态资源。
FROM node:22-alpine AS frontend-builder

WORKDIR /build/webChannel
COPY webChannel/package.json webChannel/package-lock.json ./
RUN npm ci
COPY webChannel/ ./
RUN npm run build

# 最终镜像仅保留 Python 运行环境和前端构建产物。
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=1675 \
    RELOAD=false

WORKDIR /app

# libmagic 用于识别上传文件类型，curl 用于容器健康检查。
RUN apt-get update \
    && apt-get install --no-install-recommends -y curl libmagic1 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system lumen \
    && useradd --system --gid lumen --home-dir /app lumen

COPY --chown=lumen:lumen . /app
COPY --from=frontend-builder --chown=lumen:lumen /build/webChannel/dist /app/webChannel/dist

RUN pip install --no-cache-dir . \
    && mkdir -p /app/lumen_agent/data/chroma /app/work_space /app/log \
    && chown -R lumen:lumen /app

USER lumen

EXPOSE 1675

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl --fail --silent http://127.0.0.1:1675/health > /dev/null || exit 1

CMD ["python", "-m", "lumen_agent.app"]
