# Frontend Dockerfile for Gmail Manager
FROM node:20-alpine AS builder

WORKDIR /app

# Copy package files
COPY package.json package-lock.json* ./

# Install dependencies
RUN npm ci

# Copy source code
COPY . .

# Build argument for API base URL
ARG VITE_API_BASE=http://localhost:8000
ENV VITE_API_BASE=$VITE_API_BASE

# Build the application
RUN npm run build

# Production stage
FROM node:20-alpine

WORKDIR /app

# Copy built assets from builder
COPY --from=builder /app/dist ./dist
COPY --from=builder /app/package.json ./

# Install serve to run the built app
RUN npm install -g serve

# Expose port 5173
EXPOSE 5173

# Serve the built application
CMD ["serve", "-s", "dist", "-l", "5173"]
