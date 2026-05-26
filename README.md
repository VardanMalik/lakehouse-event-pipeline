# lakehouse-event-pipeline

An end-to-end event-driven lakehouse pipeline that streams synthetic events through Kafka, processes them with Spark Structured Streaming and Spark batch jobs, and lands them as Iceberg tables on S3-compatible object storage. The project is organized as a single Python package with separate producer, streaming, batch, and shared-utility subpackages, plus local infrastructure tooling for running the full stack against MinIO and Kafka.
