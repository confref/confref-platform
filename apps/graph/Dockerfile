# The platform's application (standard library only) and its jobs.
FROM python:3.13.16-slim-trixie
RUN groupadd --gid 9090 graph && useradd --uid 9090 --gid graph --no-create-home --shell /usr/sbin/nologin graph
WORKDIR /app
COPY *.py ./
USER graph
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
EXPOSE 8090
CMD ["python3", "app.py"]
