FROM mcr.microsoft.com/playwright/python:v1.39.0-jammy

WORKDIR /app

COPY requirements.txt /app/
RUN python -m pip install --upgrade pip \
    && pip install -r requirements.txt \
    && pip install allure-commandline

COPY . /app

# Установка браузеров Playwright (образ уже содержит, но на всякий случай)
RUN playwright install --with-deps

ENV PYTHONUNBUFFERED=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

# Директория для результатов
RUN mkdir -p /app/test_results/allure-results

CMD ["bash", "-lc", "pytest -v --alluredir=./test_results/allure-results"]
