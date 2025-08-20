FROM node:18-slim
WORKDIR /app
COPY package.json tsconfig.json jest.config.js ./
RUN npm install
COPY src ./src
RUN npm run build
CMD ["node", "dist/index.js"]
