FROM registry.access.redhat.com/ubi9/python-311:latest
WORKDIR /opt/app-root/src
COPY python/ ./
RUN pip install --no-cache-dir .
USER 1001
ENTRYPOINT []
CMD ["platform-audit", "--help"]
