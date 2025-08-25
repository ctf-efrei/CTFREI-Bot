FROM python3.11-slim

LABEL authors="Lawcky"

# Install necessary packages
RUN apt-get update && apt-get install -y \
    procps \
    && rm -rf /var/lib/apt/lists/* \
    && pip3 install --no-cache-dir -r requirements.txt \
    && mkdir -p "/home/discordbot/log"

WORKDIR /home/discordbot

COPY --chown=discordbot:discordbot . .

USER discordbot

ENTRYPOINT ["python3", "main.py"]