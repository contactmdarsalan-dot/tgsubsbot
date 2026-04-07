FROM node:20-alpine AS build

WORKDIR /app

# Copy package files
COPY package.json package-lock.json* yarn.lock* .npmrc* ./

# Install dependencies
RUN npm cache clean --force && \
    npm install -g yarn && \
    yarn install --frozen-lockfile || yarn install

# Copy application code
COPY . .

# Build the app
RUN CI=false yarn build

# Production stage
FROM node:20-alpine

WORKDIR /app

# Install production server dependencies
RUN npm install express@4 http-proxy-middleware@2

# Copy built files and server
COPY --from=build /app/build ./build
COPY --from=build /app/server.js ./server.js

EXPOSE 3000

CMD ["node", "server.js"]
