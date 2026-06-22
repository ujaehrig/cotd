FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

LABEL org.opencontainers.image.title="cotd-takeover"
LABEL org.opencontainers.image.description="Catcher of the Day - Takeover web app"
LABEL org.opencontainers.image.source="https://github.com/ujaehrig/cotd"

WORKDIR /app

COPY takeover_app.py db.py ./

ENV DB_PATH=/data/user.db

EXPOSE 8090

CMD ["uv", "run", "--script", "takeover_app.py"]
