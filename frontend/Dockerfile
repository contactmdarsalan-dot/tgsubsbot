FROM node:20-alpine

WORKDIR /app

# Copy package files and npmrc
COPY package.json package-lock.json* .npmrc* ./

# Install dependencies with legacy peer deps
RUN npm install --legacy-peer-deps

# Copy application code
COPY . .

# Build the app
RUN npm run build

# Install serve for production
RUN npm install -g serve

# Expose port
EXPOSE 3000

# Start the application
CMD ["serve", "-s", "build", "-l", "3000"]
