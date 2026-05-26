# Local Infrastructure

This directory defines the local development stack for `lakehouse-event-pipeline`. Everything is wired together by `docker-compose.yml` and runs on a shared Docker network named `lakehouse-net`.

## Services

| Service       | Image                              | Host Port(s)  | Purpose                                              |
| ------------- | ---------------------------------- | ------------- | ---------------------------------------------------- |
| `zookeeper`   | `confluentinc/cp-zookeeper:7.6.0`  | `2181`        | Coordination layer required by Kafka 7.6 brokers.    |
| `kafka`       | `confluentinc/cp-kafka:7.6.0`      | `9092`, `29092` | Single-broker Kafka. `9092` is for host clients, `29092` is the in-network advertised listener. |
| `kafka-ui`    | `provectuslabs/kafka-ui:latest`    | `8080`        | Web UI for inspecting topics, consumer groups, and messages. |
| `minio`       | `minio/minio:latest`               | `9000`, `9001` | S3-compatible object store. `9000` is the S3 API; `9001` is the web console. |
| `minio-init`  | `minio/mc:latest`                  | —             | One-shot job that creates the `lakehouse-warehouse` bucket and exits. |
| `spark`       | `lakehouse-spark:3.5.1` (built locally) | —        | Spark 3.5.1 with Iceberg, Hadoop-AWS, and Kafka JARs pre-installed. Idles on `tail -f /dev/null` and is driven via `docker compose exec`. |

## Default credentials

| What         | Value                          |
| ------------ | ------------------------------ |
| MinIO user   | `minioadmin`                   |
| MinIO secret | `minioadmin`                   |
| MinIO bucket | `lakehouse-warehouse`          |
| Kafka host bootstrap | `localhost:9092`       |
| Kafka in-network bootstrap | `kafka:29092`    |

## Bringing the stack up and down

The repo ships two helper scripts under `scripts/`:

```sh
# From the repo root
./scripts/infra-up.sh       # bring everything up and wait until healthy
./scripts/infra-down.sh     # stop the stack, keeping volumes
./scripts/infra-down.sh --clean   # stop and also remove the minio-data volume
```

If the scripts are not yet executable, make them so once:

```sh
chmod +x scripts/infra-up.sh scripts/infra-down.sh
```

The Makefile targets `make infra-up` and `make infra-down` simply delegate to these scripts.

You can also drive Docker Compose directly:

```sh
docker compose -f infrastructure/docker-compose.yml up -d
docker compose -f infrastructure/docker-compose.yml ps
docker compose -f infrastructure/docker-compose.yml down
```

## Verifying healthchecks

`kafka` and `minio` both declare healthchecks. After `infra-up.sh` returns, confirm health with:

```sh
docker compose -f infrastructure/docker-compose.yml ps
```

The `STATUS` column should report `healthy` for both. The init job `lakehouse-minio-init` exits with code 0 after creating the bucket — its terminal state is `Exited (0)`.

Run a healthcheck manually:

```sh
# Kafka — list broker API versions through the in-container CLI
docker exec lakehouse-kafka kafka-broker-api-versions --bootstrap-server localhost:9092

# MinIO — live-probe the HTTP endpoint
curl -f http://localhost:9000/minio/health/live
```

Confirm the bucket exists:

```sh
docker exec lakehouse-minio-init mc ls local/ || true
# Or open the console at http://localhost:9001 and sign in as minioadmin/minioadmin.
```

## Troubleshooting

**Kafka won't become healthy.** Tail the broker logs:

```sh
docker compose -f infrastructure/docker-compose.yml logs -f kafka
```

The most common causes are (a) a stale ZooKeeper data dir from a previous run — clear with `./scripts/infra-down.sh --clean` and bring the stack up again, and (b) a port collision on `9092`/`29092` — check `lsof -i :9092` on the host.

**MinIO bucket missing or corrupted.** Recreate it by re-running the init job:

```sh
docker compose -f infrastructure/docker-compose.yml run --rm minio-init
```

If the volume itself is suspect, take the whole stack down with `--clean` and restart — that drops the `lakehouse-minio-data` named volume.

**Kafka UI shows "no clusters".** It only resolves `kafka:29092` over `lakehouse-net`. Make sure the `kafka` service has reached the `healthy` state before refreshing the UI at <http://localhost:8080>.

**Host can't reach Kafka on `localhost:9092`.** That listener is `PLAINTEXT_HOST`. Confirm the container exposes it with `docker compose -f infrastructure/docker-compose.yml port kafka 9092`. From inside another compose service, use `kafka:29092` instead.

**MinIO console login fails.** The console uses `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` (default `minioadmin` / `minioadmin`). If you changed the env vars after the volume was created, the new credentials apply on next start; the old data remains accessible with the new root credentials.

## Spark service

The `spark` service is built from `infrastructure/spark/Dockerfile` and published locally as `lakehouse-spark:3.5.1`. The image is based on `apache/spark:3.5.1-python3` and pre-bakes every JAR the Iceberg + Kafka + S3A stack needs. PySpark scripts under the repo root are reachable inside the container at `/opt/spark-apps` via a read-only bind mount.

### Why a custom image instead of `--packages` at runtime?

Spark's `--packages` flag (and `spark.jars.packages`) resolves JARs via Ivy on every submit. That has three downsides for this project:

1. **Reproducibility.** Ivy walks transitive dependencies on the fly, so two `spark-submit` calls minutes apart can pick up different patch versions when an upstream POM changes.
2. **Cold-start cost.** Every first submission in a fresh container has to download tens of MB of JARs before the driver starts.
3. **Offline / restricted networks.** Ivy needs HTTP egress to Maven Central; pre-baking lets the image run with no outbound network at submit time.

Pre-baking pins exact versions, keeps submit time fast, and removes Maven Central from the runtime critical path. The trade-off is that bumping any JAR requires rebuilding the image — that is a deliberate gate, not an accident.

### JARs included

| JAR                                                 | Version  | Purpose                                                                 |
| --------------------------------------------------- | -------- | ----------------------------------------------------------------------- |
| `iceberg-spark-runtime-3.5_2.12`                    | `1.6.1`  | Apache Iceberg runtime for Spark 3.5 / Scala 2.12. Provides the catalog, table format, and SQL extensions. |
| `iceberg-aws-bundle`                                | `1.6.1`  | Iceberg's bundled AWS dependencies, including `S3FileIO` (the catalog `io-impl`). |
| `hadoop-aws`                                        | `3.3.4`  | Hadoop S3A connector. Implements the `s3a://` filesystem used by Iceberg's warehouse path. |
| `aws-java-sdk-bundle`                               | `1.12.262` | AWS SDK v1 bundle required by `hadoop-aws` 3.3.x. Pinned to the version `hadoop-aws:3.3.4` was built against. |
| `spark-sql-kafka-0-10_2.12`                         | `3.5.1`  | Spark Structured Streaming Kafka source/sink.                           |
| `kafka-clients`                                     | `3.7.0`  | Kafka client library used by the connector.                             |
| `spark-token-provider-kafka-0-10_2.12`              | `3.5.1`  | Kafka delegation-token provider, required by the Spark Kafka connector at runtime. |
| `commons-pool2`                                     | `2.11.1` | Object pool used by the Spark Kafka connector for consumer reuse.        |

### Driving the Spark container

The `spark` service idles on `tail -f /dev/null` so the long-running container is always available; you drive it with `docker compose exec`. Two helper scripts wrap the common flows:

```sh
# Interactive PySpark REPL inside the container
./scripts/spark-shell.sh

# Submit a Python job. The path is relative to the repo root and is
# resolved inside the container under /opt/spark-apps/.
./scripts/spark-submit.sh src/lakehouse/streaming/my_job.py
./scripts/spark-submit.sh src/lakehouse/batch/my_job.py --conf spark.sql.shuffle.partitions=8
```

Make the helpers executable on a fresh clone:

```sh
chmod +x scripts/spark-shell.sh scripts/spark-submit.sh
```

### Verifying Iceberg + S3A from the shell

```python
# inside ./scripts/spark-shell.sh
spark.sql("CREATE NAMESPACE IF NOT EXISTS lakehouse.smoke").show()
spark.sql(
    "CREATE TABLE IF NOT EXISTS lakehouse.smoke.t (id BIGINT, ts TIMESTAMP) "
    "USING iceberg"
).show()
spark.sql("INSERT INTO lakehouse.smoke.t VALUES (1, current_timestamp())").show()
spark.sql("SELECT * FROM lakehouse.smoke.t").show()
```

If all four statements succeed and the `SELECT` returns one row, the catalog, the S3A connection to MinIO, and write path are all healthy.

### Spark-specific troubleshooting

**`NoSuchMethodError` / `NoClassDefFoundError` at job start.** This is almost always a version mismatch — typically Iceberg/Hadoop/AWS-SDK versions that were not built against each other, or a duplicate of one of the pre-baked JARs being pulled in by `--packages` at submit time. Do **not** combine the pre-baked image with `--packages`; pick one or the other. If you bumped a single dependency, restore the matrix in `infrastructure/spark/Dockerfile` and rebuild.

**`S3Exception: PathStyle ... must be virtual hosted-style` or `UnknownHostException: lakehouse-warehouse.minio`.** MinIO requires path-style addressing. `spark.hadoop.fs.s3a.path.style.access=true` is set in `spark-defaults.conf`; if you override it elsewhere (e.g., in `SparkConf`), put it back. The endpoint must also be `http://minio:9000` (the in-network hostname), not `localhost`.

**`AccessDenied` against MinIO.** Confirm the credentials in `spark-defaults.conf` match `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` in `docker-compose.yml`. If you rotated them, rebuild the Spark image or override via `--conf spark.hadoop.fs.s3a.access.key=...`.

**`org.apache.kafka.common.errors.TimeoutException` or `Connection refused` against Kafka.** From inside the `spark` container you must address Kafka as `kafka:29092` — the `9092` host listener is only reachable from outside Docker. Also confirm `lakehouse-kafka` is `healthy` with `docker compose ps`; the connector will not retry past its own timeout if the broker never comes up.

**`The bucket lakehouse-warehouse does not exist`.** The `minio-init` job creates the bucket. If it failed (check `docker compose logs minio-init`), recreate it with `docker compose -f infrastructure/docker-compose.yml run --rm minio-init`.

**Image build fails on a 404 from Maven Central.** The Dockerfile uses `curl --fail`, so a single missing JAR will break the build instead of silently writing an HTML page into `$SPARK_HOME/jars`. Confirm the version pin matches an actual artifact on `repo1.maven.org` — versions occasionally get yanked, especially for release candidates.
