FROM python:3.9-slim

WORKDIR /app/BogoBots

RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    software-properties-common \
    git \
    vim \
    && rm -rf /var/lib/apt/lists/*

COPY . /app/BogoBots

RUN pip3 install -r requirements.txt

EXPOSE 8501

HEALTHCHECK CMD curl --fail http://localhost:8601/_stcore/health

ENTRYPOINT ["streamlit", "run", "BogoBots.py", "--server.port=8601", "--server.address=0.0.0.0"]