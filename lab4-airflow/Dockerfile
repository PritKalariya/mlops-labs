FROM apache/airflow:3.3.2-python3.12

COPY requirements.txt /tmp/requirements.txt

# Runs as the airflow user. The constraints file is never overridden.
RUN pip install --no-cache-dir -r /tmp/requirements.txt \
    -c https://raw.githubusercontent.com/apache/airflow/constraints-3.3.2/constraints-3.12.txt

# Last build step: fail the build on any broken dependency.
RUN pip check
