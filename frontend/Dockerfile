# Stage 1: Build the React application
FROM node:18-alpine AS builder

WORKDIR /app

# Copy package.json and package-lock.json (or yarn.lock)
COPY package*.json ./

# Install dependencies
RUN npm install

# Copy the rest of the application source code
COPY . .

# _VITE_CORE_API_URL and _VITE_BRIDGE_API_URL are expected to be set as
# environment variables in the Cloud Build step by the --substitutions flag.
# Vite picks up env vars prefixed with VITE_.
# We ensure they are passed to the npm run build command's environment.
RUN echo "BUILD_STEP: Raw _VITE_CORE_API_URL is $_VITE_CORE_API_URL" && \
    echo "BUILD_STEP: Raw _VITE_BRIDGE_API_URL is $_VITE_BRIDGE_API_URL" && \
    VITE_CORE_API_URL=${_VITE_CORE_API_URL:-http://localhost:3000} \
    VITE_BRIDGE_API_URL=${_VITE_BRIDGE_API_URL:-http://localhost:3001} \
    npm run build

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