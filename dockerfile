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

ENV SENDER_EMAIL=${SENDER_EMAIL}
ENV SENDER_PASSWORD=${SENDER_PASSWORD}
ENV RECEIVER_EMAIL=${RECEIVER_EMAIL}
ENV SMTP_SERVER=${SMTP_SERVER}
ENV SMTP_PORT=${SMTP_PORT}
ENV ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
ENV ALPHA_VANTAGE_API_KEY=${ALPHA_VANTAGE_API_KEY}
ENV OPENAI_API_KEY=${OPENAI_API_KEY}

# Run daily_market_email.py when the container launches
CMD ["python", "daily_market_email.py"]