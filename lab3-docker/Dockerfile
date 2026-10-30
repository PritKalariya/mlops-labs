# One base for every stage. The venv's interpreter symlinks into the base, so
# builder and runtime must be byte-identical: pin by digest, not just by tag.
ARG BASE_IMAGE=python:3.12-slim@sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159


# Stage 1: install the pinned app dependencies into /opt/venv.
FROM ${BASE_IMAGE} AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"

# Requirements before code, so a code edit does not reinstall dependencies.
COPY requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt && pip check


# Stage 2: train with that same venv, so the model's scikit-learn is the runtime's.
FROM ${BASE_IMAGE} AS train

ENV PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:${PATH}"

COPY --from=builder /opt/venv /opt/venv

WORKDIR /build/src
# Only the training code, so editing the serving code does not force a retrain.
COPY src/train.py src/data.py /build/src/
RUN python train.py --version 1.0.0


# Stage 3: the load test. Its own base, its own deps; never reaches the runtime.
FROM ${BASE_IMAGE} AS smoke

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"

COPY requirements-smoke.txt /tmp/requirements-smoke.txt
RUN pip install -r /tmp/requirements-smoke.txt && pip check

RUN useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin app

WORKDIR /smoke
COPY loadtest.py /smoke/loadtest.py

USER 10001
CMD ["python", "loadtest.py"]


# Stage 4: what ships. Last stage, so it is the default build target.
FROM ${BASE_IMAGE} AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:${PATH}" \
    PORT=8080 \
    IRIS_ARTIFACT_VERSION=1.0.0 \
    IRIS_ARTIFACT_URI=file:///app/model/1.0.0/model.pkl

RUN useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin app

# Everything below stays root-owned and read-only to UID 10001.
COPY --from=builder /opt/venv /opt/venv
COPY --from=train /build/model /app/model
COPY src/main.py src/model_loader.py /app/src/

WORKDIR /app/src

EXPOSE 8080

# slim has no curl. Readiness, not liveness: healthy means the model loaded
# and the loader's version and sha256 checks passed.
HEALTHCHECK --interval=10s --timeout=3s --retries=3 --start-period=20s \
    CMD python -c "import os,sys,urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','8080')+'/health/ready', timeout=2).status==200 else 1)"

USER 10001

# exec makes uvicorn PID 1, so SIGTERM reaches it instead of being swallowed by sh.
CMD ["sh", "-c", "exec uvicorn main:app --host 0.0.0.0 --port ${PORT}"]
