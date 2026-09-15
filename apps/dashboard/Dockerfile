FROM node:22-alpine AS build
WORKDIR /app
COPY package.json ./
RUN npm install --ignore-scripts
COPY . .
RUN npm run build
FROM node:22-alpine
WORKDIR /app
RUN npm install -g serve@14.2.4 && adduser -D -u 10001 app
COPY --from=build /app/dist ./dist
USER app
EXPOSE 4173
CMD ["serve", "-s", "dist", "-l", "4173"]

