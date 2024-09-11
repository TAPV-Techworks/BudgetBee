# backend.Dockerfile
# Use the official lightweight Python image.
# https://hub.docker.com/_/python
FROM python:3.10-slim

# Set environment variable to prevent the creation of __pycache__ folders
ENV PYTHONDONTWRITEBYTECODE=1

# Set the working directory in the container.
WORKDIR /app

RUN pip install --upgrade pip

# Install necessary packages and Zsh
RUN apt-get update && apt-get install -y sudo zsh

# Copy the requirements file into the container.
COPY backend/requirements.txt .

# Install any dependencies.
RUN pip install --no-cache-dir -r requirements.txt

# Copy the content of the backend folder into the container.
COPY . .

# # Copy the startup script into the container.
# COPY backend/startup.sh /app/startup.sh

# # Make the startup script executable
# RUN sudo chmod +x /app/startup.sh

# RUN sudo sh backend/startup.sh

# Set environment variables
ENV OAUTHLIB_INSECURE_TRANSPORT=1
ENV FLASK_APP=backend/wsgi.py
ENV FLASK_ENV=development

# Expose the port the app runs on
EXPOSE 5000

# Run the application
CMD ["flask", "run", "--host=0.0.0.0", "--port=5000"]
