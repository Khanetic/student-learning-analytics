"""ETL logic shared by the Airflow DAGs (Phase 2).

The DAGs are thin orchestration wrappers; all read/validate/load logic lives
here so it can be unit-tested without an Airflow runtime.
"""
