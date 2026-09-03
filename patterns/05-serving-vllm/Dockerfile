FROM python:3.12.11-slim-bookworm@sha256:519591d6871b7bc437060736b9f7456b8731f1499a57e22e6c285135ae657bf7

# Direct and transitive Python dependencies are version- and hash-locked. Compose service-image
# digests still need pinning before a production supply-chain claim.
COPY requirements.lock /tmp/requirements.lock
RUN pip install --no-cache-dir --require-hashes -r /tmp/requirements.lock

WORKDIR /srv
COPY app.py /srv/app.py

EXPOSE 8080
CMD ["python", "-u", "app.py"]
