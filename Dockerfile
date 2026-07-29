# 前端构建阶段仅负责生成 Vue 静态资源。
FROM node:22-bookworm-slim AS frontend-builder

WORKDIR /build/webChannel
COPY webChannel/package.json webChannel/package-lock.json ./
RUN npm ci
COPY webChannel/ ./
RUN npm run build

# 微信通道安装独立依赖，最终镜像只复制运行所需文件。
FROM node:22-bookworm-slim AS weixin-builder

WORKDIR /build/weixinChannel
COPY weixinChannel/package.json weixinChannel/package-lock.json ./
RUN npm ci
COPY weixinChannel/ ./

# 最终镜像保留 Python、Node.js 和前端构建产物。
FROM python:3.12-slim AS runtime

# 默认使用国内镜像并放宽网络重试参数，构建时仍可通过 --build-arg 覆盖。
ARG PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/
ARG PIP_TIMEOUT=120
ARG PIP_RETRIES=10
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
# Node 子进程由 FastAPI 生命周期托管，外部仍只开放一个 1675 端口。
COPY --from=weixin-builder /usr/local/bin/node /usr/local/bin/node
COPY --from=weixin-builder --chown=lumen:lumen /build/weixinChannel/node_modules /app/weixinChannel/node_modules

# BuildKit 缓存会复用已下载的依赖，但不会被写入最终镜像。
RUN --mount=type=cache,target=/root/.cache/pip,sharing=locked \
    pip install \
        --index-url "${PIP_INDEX_URL}" \
        --timeout "${PIP_TIMEOUT}" \
        --retries "${PIP_RETRIES}" \
        . \
    && mkdir -p /app/lumen_agent/data/chroma /app/work_space /app/log /app/weixinChannel/data \
    && chown -R lumen:lumen /app

USER lumen

EXPOSE 1675

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl --fail --silent http://127.0.0.1:1675/health > /dev/null || exit 1

CMD ["python", "-m", "lumen_agent.app"]
