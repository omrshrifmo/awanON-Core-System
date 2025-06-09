# Stage 1: Build the React application
FROM node:18-alpine AS builder

WORKDIR /app

# Copy package.json and package-lock.json (or yarn.lock)
COPY package*.json ./

# Install dependencies
RUN npm install

# Copy the rest of the application source code
COPY . .

# These ENV variables will be populated by Cloud Build's --substitutions
# Default values are provided here in case the variables are not set (e.g., local Docker build without --build-arg)
# Vite expects these as environment variables during the build process.
# Note: _VITE_CORE_API_URL and _VITE_BRIDGE_API_URL are substitution variable names often used in cloudbuild.yaml.
# The Dockerfile itself will see VITE_CORE_API_URL and VITE_BRIDGE_API_URL as environment variables.
ENV VITE_CORE_API_URL=${_VITE_CORE_API_URL:-http://localhost:8080}
ENV VITE_BRIDGE_API_URL=${_VITE_BRIDGE_API_URL:-http://localhost:3001}

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