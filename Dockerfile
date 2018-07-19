FROM python:3.7
ENV PYTHONPATH /app
COPY . /app
WORKDIR /app
RUN python3 setup.py install

