# --- build stage ---------------------------------------------------------
FROM node:20-alpine AS build

WORKDIR /app

# package files first, so the dependency layer stays cached when source changes
COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

# --- serve stage ---------------------------------------------------------
# No need to ship a Node runtime — after the build, only static files remain.
# The Nginx image is far smaller, and it also handles the /api proxy.
FROM nginx:alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
