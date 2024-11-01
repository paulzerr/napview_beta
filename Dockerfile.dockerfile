# Use a specific Python version as a base image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Copy project files into the container
COPY . /app

# Install Python dependencies, ensuring pylsl is at version 1.16.2
RUN pip install -r requirements.txt

# Copy the liblsl.so file into the appropriate directory
COPY libs/liblsl.so /usr/local/lib/

# Specify the PYLSL_LIB environment variable
ENV PYLSL_LIB="/usr/local/lib/liblsl.so"

# Set environment variables
ENV PYTHONPATH="/app"

# # Expose necessary ports
EXPOSE 8145 8146 8147 8148 8149 8150 8245 8246 8247 8248 8249 8250

# Run the application
CMD ["python3", "src/napview/main.py"]
