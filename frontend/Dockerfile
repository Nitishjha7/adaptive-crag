# --- build stage ---------------------------------------------------------
FROM node:20-alpine AS build

WORKDIR /app

# package files pehle — source badalne pe npm install layer cached rehti hai
COPY package.json ./
RUN npm install

COPY . .
RUN npm run build

# --- serve stage ---------------------------------------------------------
# Node runtime ship karne ki zaroorat nahi — build ke baad sirf static files
# bachti hain. Nginx image bahut chhoti hai aur /api proxy bhi wahi karta hai.
FROM nginx:alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
