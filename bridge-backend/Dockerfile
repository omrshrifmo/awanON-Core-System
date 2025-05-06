# bridge-backend/Dockerfile
FROM node:18-alpine
# Use a specific LTS Node.js version (alpine is smaller)

WORKDIR /usr/src/app

# Copy package.json and package-lock.json (if available)
COPY package*.json ./

# Install dependencies
RUN npm install --production
# Install only production dependencies

# Copy application code
COPY . .

# Expose the port the app runs on
EXPOSE 3000

# Command to run the application
CMD [ "node", "server.js" ]