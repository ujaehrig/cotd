FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

WORKDIR /app

COPY takeover_app.py db.py ./

ENV DB_PATH=/data/user.db

EXPOSE 8090

CMD ["uv", "run", "--script", "takeover_app.py"]
