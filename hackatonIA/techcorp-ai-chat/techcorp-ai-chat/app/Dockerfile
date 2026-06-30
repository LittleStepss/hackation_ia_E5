FROM python:3.11-slim
WORKDIR /srv
COPY app/requirements.txt app/requirements.txt
RUN pip install --no-cache-dir -r app/requirements.txt
COPY app app
EXPOSE 8500
CMD ["uvicorn", "app.server:app", "--host", "0.0.0.0", "--port", "8500"]
