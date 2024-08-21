# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Set environment variables from build args
ARG SENDER_EMAIL
ARG SENDER_PASSWORD
ARG RECEIVER_EMAIL
ARG SMTP_SERVER
ARG SMTP_PORT
ARG ANTHROPIC_API_KEY
ARG ALPHA_VANTAGE_API_KEY
ARG OPENAI_API_KEY
ARG COINAPI_KEY

ENV SENDER_EMAIL=${SENDER_EMAIL}
ENV SENDER_PASSWORD=${SENDER_PASSWORD}
ENV RECEIVER_EMAIL=${RECEIVER_EMAIL}
ENV SMTP_SERVER=${SMTP_SERVER}
ENV SMTP_PORT=${SMTP_PORT}
ENV ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
ENV ALPHA_VANTAGE_API_KEY=${ALPHA_VANTAGE_API_KEY}
ENV OPENAI_API_KEY=${OPENAI_API_KEY}
ENV COINAPI_KEY=${COINAPI_KEY}

# Expose port 5000 for the Flask app
EXPOSE 5000

# The CMD instruction is now removed as it will be specified in docker-compose.yml