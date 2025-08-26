FROM python:3.11-slim

LABEL authors="Lawcky"

WORKDIR /home/discordbot

COPY . .

# Install necessary packages
RUN apt-get update && apt-get install -y \
    procps \
    && rm -rf /var/lib/apt/lists/* \
    && pip3 install --no-cache-dir -r requirements.txt \
    && mkdir -p "/home/discordbot/log"

ENTRYPOINT ["python3", "main.py"]