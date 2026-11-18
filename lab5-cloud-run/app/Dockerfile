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

# The model version is baked into the image; the loader checks it at startup.
ARG MODEL_VERSION=1.0.0

ENV PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:${PATH}"

COPY --from=builder /opt/venv /opt/venv

WORKDIR /build/src
# Only the training code, so editing the serving code does not force a retrain.
COPY src/train.py src/data.py /build/src/
RUN python train.py --version ${MODEL_VERSION}


# Stage 3: what ships. Last stage, so it is the default build target.
FROM ${BASE_IMAGE} AS runtime

ARG MODEL_VERSION=1.0.0

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:${PATH}" \
    PORT=8080 \
    IRIS_ARTIFACT_VERSION=${MODEL_VERSION} \
    IRIS_ARTIFACT_URI=file:///app/model/${MODEL_VERSION}/model.pkl

RUN useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin app

# Everything below stays root-owned and read-only to UID 10001.
COPY --from=builder /opt/venv /opt/venv
COPY --from=train /build/model /app/model
COPY src/main.py src/model_loader.py /app/src/

WORKDIR /app/src

EXPOSE 8080

# Used by local `docker run` only: Cloud Run ignores HEALTHCHECK and uses the
# startup and liveness probes set at deploy time. slim has no curl.
HEALTHCHECK --interval=10s --timeout=3s --retries=3 --start-period=20s \
    CMD python -c "import os,sys,urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','8080')+'/health/ready', timeout=2).status==200 else 1)"

USER 10001

# exec makes uvicorn PID 1, so SIGTERM reaches it instead of being swallowed by sh.
CMD ["sh", "-c", "exec uvicorn main:app --host 0.0.0.0 --port ${PORT}"]
