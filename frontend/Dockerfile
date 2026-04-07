FROM node:20-alpine

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

# Install serve for production
RUN npm install -g serve

# Expose port
EXPOSE 3000

# Start the application
CMD ["serve", "-s", "build", "-l", "3000"]
