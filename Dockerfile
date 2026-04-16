FROM python:3.10-slim

# System tools install karne ke liye (Binary chalane ke liye zaroori hai)
RUN apt-get update && apt-get install -y \
    curl \
    procps \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Sabhi files copy karein
COPY . .

# Requirements install karein
RUN pip install --no-cache-dir -r requirements.txt

# Binary ko executable banayein (Ye step Railway ke liye main hai)
RUN chmod +x bgmi

# Bot start karein
CMD ["python", "danger.py"]
