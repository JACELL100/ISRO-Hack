# ─── ISRO Lunar Ice Explorer — Frontend Docker Image ─────────────────────────
# Used for self-hosted / docker-compose deployment only.
# For Vercel deployment, this file is not used.
#
# Build: docker build -f frontend/Dockerfile -t isro-frontend ./frontend
# Run:   docker run -p 3000:3000 -e NEXT_PUBLIC_API_URL=http://backend:8000 isro-frontend

FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
# NEXT_PUBLIC_API_URL must be passed as a build arg so it's baked in at build time
ARG NEXT_PUBLIC_API_URL=http://backend:8000
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
# Copy the built Next.js output (standard mode, not standalone)
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public
COPY --from=builder /app/package*.json ./
RUN npm ci --omit=dev
EXPOSE 3000
CMD ["npm", "start"]
