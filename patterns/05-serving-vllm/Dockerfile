FROM python:3.12-slim

# Pinned minors, not "latest": the whole point of a reproducible contour is that
# `docker compose up` a month from now builds the same thing.
RUN pip install --no-cache-dir \
      "redis==5.2.*" \
      "openai==1.*" \
      "neo4j==5.*"

WORKDIR /srv
COPY app.py /srv/app.py

EXPOSE 8080
CMD ["python", "-u", "app.py"]
