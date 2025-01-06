# Use the official Python image as a base image
FROM python:3.9-slim

# Set the working directory in the container to /app
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app/

# Install the necessary dependencies
RUN apt-get update && apt-get install -y ffmpeg && apt-get clean

# Create a virtual environment (optional but recommended)
RUN python -m venv /venv
ENV PATH="/venv/bin:$PATH"

# Install the required Python packages
RUN pip install --no-cache-dir -r requirements.txt

# Expose the port the app runs on
EXPOSE 8081

# Set the environment variable for Flask
ENV FLASK_APP=flaskinferencecleaning.py

# Command to run the Flask app
CMD ["flask", "run", "--host=0.0.0.0", "--port=8081"]


