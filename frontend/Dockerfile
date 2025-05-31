# Stage 1: Build the React application
FROM node:18-alpine AS builder

WORKDIR /app

# Copy package.json and package-lock.json (or yarn.lock)
COPY package*.json ./

# Install dependencies
RUN npm install

# Copy the rest of the application source code
COPY . .

# Build the application
RUN npm run build

# Stage 2: Serve the static files from the build output
FROM node:18-alpine

WORKDIR /app

# Install 'serve' to act as the static file server
RUN npm install -g serve

# Copy only the build output from the builder stage
COPY --from=builder /app/dist ./dist

# Expose port 80 (standard for web servers, can be overridden by PORT env var)
EXPOSE 80

# Command to serve the built application
# Listens on PORT environment variable, falls back to 80 if PORT is not set.
# 'serve -s dist' serves the 'dist' folder.
# '-l tcp://0.0.0.0:${PORT:-80}' makes serve listen on all interfaces, on the value of PORT or 80 if PORT is not set.
# Note: The syntax for serve to listen on env:PORT:default can vary.
# Simpler approach for `serve` is often to let it pick up PORT directly if supported,
# or use a wrapper script. `serve` v14+ should pick up PORT automatically.
# If not, a common pattern is `CMD sh -c "serve -s dist -l ${PORT:-80}"` but this has caveats with signal handling.
# For `serve`, using its built-in capability to respect PORT is best.
# The `-l` flag with `env:PORT:default_port` is more for npx/local usage.
# `serve` documentation states it listens on `process.env.PORT` by default.
# So, we can simplify the CMD if `serve` handles `PORT` directly.
# Let's assume modern `serve` behavior.
CMD ["serve", "-s", "dist"]
# If PORT needs to be explicitly passed and serve doesn't pick it up:
# CMD sh -c "serve -s dist -l ${PORT:-80}"
# For Render/similar platforms, they set the PORT env var, and `serve` should pick it up.
# The default port for `serve` if PORT is not set is 3000.
# To make it default to 80 if PORT is not set (and EXPOSE 80), we can adjust.
# However, many platforms (like Render) inject PORT, so `serve -s dist` will listen on $PORT.
# If we want to ensure it's 80 when PORT is NOT set by platform:
# CMD ["sh", "-c", "serve -s dist -l ${PORT:-80}"]
# Let's stick to the simpler CMD for now, assuming `serve` picks up PORT,
# and platforms like Render will set PORT. If not, the sh -c version is an alternative.
# The EXPOSE 80 is a good hint for default.
# The task specifically asks for respecting PORT env var and fallback.
# `serve -s dist -l tcp://0.0.0.0:${PORT:-80}` is explicit but might be too complex for basic `serve`.
# Let's try a common `serve` pattern that respects PORT and has a fallback.
# `serve` itself listens on `process.env.PORT` or its own default (3000).
# To make it default to 80 for this container if PORT is not set:
# We'll rely on the platform setting PORT, and `serve` picking it up.
# If we need to force a different default *within the container* when PORT is unset,
# it's trickier with `serve` without a shell wrapper.
# The spirit of the request: "respects the PORT environment variable, for example: CMD ["serve", "-s", "dist", "-l", "env:PORT:5173"]"
# The `serve -l env:PORT:default` syntax is more for its programmatic API or CLI convenience.
# The simplest CMD that respects PORT is just `CMD ["serve", "-s", "dist"]` because `serve` does this by default.
# The fallback behavior (if PORT is not set by environment) will be `serve`'s own default (3000).
# If the EXPOSE is 80, and we want it to run on 80 if PORT is not set, we need to tell `serve` to listen on 80.
# `CMD ["serve", "-s", "dist", "-l", "80"]` would hardcode 80 and NOT respect PORT.
# The example `CMD ["serve", "-s", "dist", "-l", "env:PORT:5173"]` implies `serve` has such a feature.
# Checking `serve` docs: `serve -l <port>` or `serve -l tcp://0.0.0.0:<port>`.
# It also says: "If a port is not specified, it will default to 3000 or the value of the PORT environment variable."
# So, to make it default to 80 (matching EXPOSE) IF PORT IS NOT SET, and otherwise use PORT:
# This requires a shell:
# CMD ["sh", "-c", "serve -s dist -l ${PORT:-80}"]
# This is the most robust way to achieve the fallback for `serve`.
# Let's use this one.
# Final check on port for `serve`: it's `PORT` or `3000`. `EXPOSE 80`.
# If we want the default to be 80 when PORT is not set:
# CMD sh -c "serve -s dist -l ${PORT:-80}"
# This ensures that if PORT is set, it uses that. If not, it uses 80.
# This aligns EXPOSE 80 with the default behavior.
CMD ["sh", "-c", "serve -s dist -l ${PORT:-80}"]