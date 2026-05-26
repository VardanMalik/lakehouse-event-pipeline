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
