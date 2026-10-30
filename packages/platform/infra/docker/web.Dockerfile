# FrameForge Next.js 15 image (multi-stage)
# build 阶段：装 pnpm + 装依赖 + Next build
# runtime 阶段：仅保留 server + 必备资源

FROM node:20-alpine AS deps
RUN apk add --no-cache libc6-compat
RUN corepack enable && corepack prepare pnpm@10.19.0 --activate
WORKDIR /repo
COPY pnpm-workspace.yaml package.json pnpm-lock.yaml* ./
COPY tsconfig.base.json ./
COPY packages/ ./packages/
COPY apps/ ./apps/
RUN pnpm install --frozen-lockfile=false

FROM node:20-alpine AS build
ARG APP=web-uploader
ENV NEXT_TELEMETRY_DISABLED=1
RUN corepack enable && corepack prepare pnpm@10.19.0 --activate
WORKDIR /repo
COPY --from=deps /repo /repo
RUN pnpm --filter @ff/${APP} build

FROM node:20-alpine AS runtime
ARG APP=web-uploader
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV PORT=3000
RUN apk add --no-cache ffmpeg tini
RUN corepack enable && corepack prepare pnpm@10.19.0 --activate
WORKDIR /repo
COPY --from=build /repo /repo
WORKDIR /repo/apps/${APP}
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=5s CMD wget -qO- http://localhost:3000/api/health || exit 1
ENTRYPOINT ["/sbin/tini", "--"]
CMD ["sh", "-c", "pnpm --filter @ff/shared build && node server.js || pnpm start"]
