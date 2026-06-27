# syntax=docker/dockerfile:1
FROM node:20-alpine

WORKDIR /app

# Copy package files first for better caching
COPY package.json package-lock.json* ./
RUN npm install

# Copy source code
COPY . .

EXPOSE 3000

# Default: Vite dev server with HMR
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "3000"]
