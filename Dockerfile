FROM python:3.12-slim

WORKDIR /usr/src/app

COPY requirements.txt ./

RUN pip install --no-cache-dir -r requirements.txt

COPY *.py ./

RUN apt-get update && apt-get install -y locales && locale-gen zh_CN.UTF-8

CMD ["python","main.py"]
