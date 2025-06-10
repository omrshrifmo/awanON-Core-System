# Stage 1: Build the React application
FROM node:18-alpine AS builder

WORKDIR /app

# Copy package.json and package-lock.json (or yarn.lock)
COPY package*.json ./

# Install dependencies
RUN npm install

# Copy the rest of the application source code
COPY . .

# Declare ARGs that can be passed during build time
# Cloud Build will populate these if matching --substitutions are provided (without the underscore)
# OR if passed via --build-arg in local docker build
ARG VITE_CORE_API_URL="http://localhost:3000"
ARG VITE_BRIDGE_API_URL="http://localhost:3001"

# Set ENV vars for the Vite build process using the ARGs
ENV VITE_CORE_API_URL=${VITE_CORE_API_URL}
ENV VITE_BRIDGE_API_URL=${VITE_BRIDGE_API_URL}

RUN echo "BUILD_STEP: VITE_CORE_API_URL is $VITE_CORE_API_URL" && \
    echo "BUILD_STEP: VITE_BRIDGE_API_URL is $VITE_BRIDGE_API_URL" && \
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