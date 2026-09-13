FROM python:3.12-slim

WORKDIR /app/BogoBots

ENV TZ=Asia/Shanghai

RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    vim \
    ffmpeg \
    default-libmysqlclient-dev \
    pkg-config \
    tzdata \
    cron \
    util-linux \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime \
    && echo $TZ > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

COPY . /app/BogoBots

RUN pip3 install -r requirements.txt \
    && chmod +x /app/BogoBots/scripts/ai_news_cron.sh \
        /app/BogoBots/scripts/register_ai_news_cron.sh \
        /app/BogoBots/scripts/docker-entrypoint.sh \
    && cp /app/BogoBots/scripts/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh \
    && cp /app/BogoBots/scripts/register_ai_news_cron.sh /usr/local/bin/register-ai-news-cron \
    && chmod +x /usr/local/bin/docker-entrypoint.sh /usr/local/bin/register-ai-news-cron

RUN mkdir /app/BogoBots/static

COPY backup_openai_chat_models_base.py /usr/local/lib/python3.12/site-packages/langchain_openai/chat_models/base.py

EXPOSE 8601

HEALTHCHECK CMD curl --fail http://localhost:8601/_stcore/health

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["streamlit", "run", "BogoBots.py", "--server.port=8601", "--server.address=0.0.0.0"]