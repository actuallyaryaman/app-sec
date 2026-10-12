ARG PYTHON_IMAGE=python:3.13.16-slim-bookworm
FROM ${PYTHON_IMAGE}
ARG LAB_UID=1000
ARG LAB_GID=1000
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1 \
    HOME=/tmp PYTHONPATH=/opt/lab
# Required by os.popen("diff ...") in the provided updated script.
RUN apt-get update \
    && apt-get install -y --no-install-recommends diffutils=1:3.8-4 \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt /opt/lab/requirements.txt
RUN python -m pip install --no-cache-dir --only-binary=:all: --no-deps -r /opt/lab/requirements.txt \
    && python -m pip check
COPY docker/ /opt/lab/
RUN mkdir -p /originals /work /export \
    && chown ${LAB_UID}:${LAB_GID} /work \
    && chmod 700 /work
USER ${LAB_UID}:${LAB_GID}
WORKDIR /work
ENTRYPOINT ["python", "-u", "/opt/lab/entrypoint.py"]
CMD ["help"]
