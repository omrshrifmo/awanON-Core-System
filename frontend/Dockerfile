# Stage 1: Build the React application
FROM node:18-alpine AS builder

WORKDIR /app

# Copy package.json and package-lock.json (or yarn.lock)
COPY package*.json ./

# Install dependencies
RUN npm install

# Copy the rest of the application source code
COPY . .

# ARG for build-time environment variables with default values
# These ARGs are used to pass values during the `docker build` command.
# Example: docker build --build-arg _VITE_CORE_API_URL="https://actual-api.example.com" ...
ARG _VITE_CORE_API_URL="http://localhost:8080/api/v1"
ARG _VITE_BRIDGE_API_URL="http://localhost:3001/api/v1"

# Set ENV vars from ARGs so Vite can pick them up during the build process.
# Vite accesses these as `import.meta.env.VITE_CORE_API_URL`, etc.
ENV VITE_CORE_API_URL=${_VITE_CORE_API_URL}
ENV VITE_BRIDGE_API_URL=${_VITE_BRIDGE_API_URL}

# Build the application
# Vite will replace import.meta.env.VITE_* with these ENV values
RUN npm run build

# Stage 2: Serve the static files with Nginx
FROM nginx:1.25-alpine

# Copy built static files from the builder stage to Nginx html directory
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy a custom Nginx configuration if needed (optional)
# COPY nginx.conf /etc/nginx/nginx.conf
# A default Nginx configuration usually works for serving static files.
# For SPAs (Single Page Applications) like React, you might need to configure Nginx
# to redirect all 404s to index.html.
# Create a simple nginx.conf for SPA routing
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose port 80 (Nginx default port)
EXPOSE 80

# Command to start Nginx in the foreground
CMD ["nginx", "-g", "daemon off;"]