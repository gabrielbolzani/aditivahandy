FROM python:3.12-slim-bookworm

WORKDIR /opt/aditivahandy

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY aditivahandy ./aditivahandy
COPY vendor ./vendor
COPY run.py .

EXPOSE 8787

CMD ["python", "-m", "aditivahandy"]
