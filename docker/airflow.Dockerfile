# syntax=docker/dockerfile:1
# ---------------------------------------------------------------------------
# Airflow image for the Student Learning Analytics pipeline.
# Built on the official Airflow 2.9 / Python 3.11 image; layers in the few
# extra runtime dependencies the project's `sla` package needs. The package
# itself is made importable at runtime via PYTHONPATH (repo mounted by compose),
# so DAG and src edits are picked up without a rebuild.
# ---------------------------------------------------------------------------
FROM apache/airflow:2.9.3-python3.11

COPY docker/airflow-requirements.txt /tmp/airflow-requirements.txt
RUN pip install --no-cache-dir -r /tmp/airflow-requirements.txt
