FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:22-alpine AS build
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# Rewrite Next.js dibekukan ke routes-manifest saat build, jadi alamat API harus
# sudah benar DI SINI — menyetelnya saat runtime saja tidak berpengaruh.
ARG SHERLOCK_API_URL=http://sherlock-api:8000
ENV SHERLOCK_API_URL=$SHERLOCK_API_URL NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:22-alpine AS run
WORKDIR /app
# HOSTNAME wajib disetel: server.js standalone memakai $HOSTNAME sebagai alamat bind,
# dan Docker mengisinya dengan ID kontainer — Next lalu hanya mendengar di satu antarmuka
# sehingga port yang dipublikasikan ke host menolak koneksi.
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000 HOSTNAME=0.0.0.0
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
COPY --from=build /app/public ./public
USER node
EXPOSE 3000
CMD ["node", "server.js"]
