# --- build stage ---------------------------------------------------------
FROM node:20-alpine AS build

WORKDIR /app

# package files first, so the dependency layer stays cached when source changes
COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

# --- serve stage ---------------------------------------------------------
# Node runtime ship karne ki zaroorat nahi — build ke baad sirf static files
# bachti hain. Nginx image bahut chhoti hai aur /api proxy bhi wahi karta hai.
FROM nginx:alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
