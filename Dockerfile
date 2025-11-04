FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1
RUN pip install --no-cache-dir python-telegram-bot[ext] aiosqlite
COPY bot.py /app/bot.py
RUN useradd -r -u 1001 adalikm && mkdir -p /data && chown -R adalikm:adalikm /data
USER adalikm
VOLUME ["/data"]
ENV DB_PATH=/data/AdalikM.db TORAGE_DIR=/data/storage
CMD ["python", "/app/bot.py"]
