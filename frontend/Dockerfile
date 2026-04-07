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

# Production stage with Nginx
FROM nginx:alpine

# Copy built files
COPY --from=build /app/build /app/build

# Copy nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Remove default nginx config
RUN rm -f /etc/nginx/conf.d/default.conf.bak

EXPOSE 3000

CMD ["nginx", "-g", "daemon off;"]
