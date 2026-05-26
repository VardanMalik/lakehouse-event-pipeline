# Custom Spark image for the lakehouse-event-pipeline.
# Base: apache/spark:3.5.1-python3 (Spark 3.5.1 on Python 3, Scala 2.12).
# Pre-bakes every JAR the Iceberg + Kafka + S3A stack needs so that
# spark-submit does not have to resolve --packages at runtime.

FROM apache/spark:3.5.1-python3

LABEL org.opencontainers.image.title="lakehouse-spark" \
      org.opencontainers.image.description="Spark 3.5.1 with Iceberg 1.6.1, Hadoop AWS 3.3.4, and Kafka 3.5.1 connectors pre-installed." \
      org.opencontainers.image.source="lakehouse-event-pipeline"

ARG MAVEN=https://repo1.maven.org/maven2

# Pinned dependency versions. Updating any of these requires re-verifying
# the cross-component compatibility matrix (Iceberg <-> Spark <-> Hadoop <-> AWS SDK).
ARG ICEBERG_VERSION=1.6.1
ARG HADOOP_AWS_VERSION=3.3.4
ARG AWS_SDK_VERSION=1.12.262
ARG SPARK_VERSION=3.5.1
ARG KAFKA_CLIENTS_VERSION=3.7.0
ARG COMMONS_POOL2_VERSION=2.11.1
ARG SCALA_BINARY_VERSION=2.12

USER root

# Download all required JARs in a single layer so the image stays small.
# --fail makes curl exit non-zero on HTTP errors (otherwise a 404 would
# happily write a 200-byte HTML body into $SPARK_HOME/jars).
RUN set -eux; \
    cd "${SPARK_HOME}/jars"; \
    curl -fSL -o "iceberg-spark-runtime-3.5_${SCALA_BINARY_VERSION}-${ICEBERG_VERSION}.jar" \
        "${MAVEN}/org/apache/iceberg/iceberg-spark-runtime-3.5_${SCALA_BINARY_VERSION}/${ICEBERG_VERSION}/iceberg-spark-runtime-3.5_${SCALA_BINARY_VERSION}-${ICEBERG_VERSION}.jar" \
    && curl -fSL -o "iceberg-aws-bundle-${ICEBERG_VERSION}.jar" \
        "${MAVEN}/org/apache/iceberg/iceberg-aws-bundle/${ICEBERG_VERSION}/iceberg-aws-bundle-${ICEBERG_VERSION}.jar" \
    && curl -fSL -o "hadoop-aws-${HADOOP_AWS_VERSION}.jar" \
        "${MAVEN}/org/apache/hadoop/hadoop-aws/${HADOOP_AWS_VERSION}/hadoop-aws-${HADOOP_AWS_VERSION}.jar" \
    && curl -fSL -o "aws-java-sdk-bundle-${AWS_SDK_VERSION}.jar" \
        "${MAVEN}/com/amazonaws/aws-java-sdk-bundle/${AWS_SDK_VERSION}/aws-java-sdk-bundle-${AWS_SDK_VERSION}.jar" \
    && curl -fSL -o "spark-sql-kafka-0-10_${SCALA_BINARY_VERSION}-${SPARK_VERSION}.jar" \
        "${MAVEN}/org/apache/spark/spark-sql-kafka-0-10_${SCALA_BINARY_VERSION}/${SPARK_VERSION}/spark-sql-kafka-0-10_${SCALA_BINARY_VERSION}-${SPARK_VERSION}.jar" \
    && curl -fSL -o "kafka-clients-${KAFKA_CLIENTS_VERSION}.jar" \
        "${MAVEN}/org/apache/kafka/kafka-clients/${KAFKA_CLIENTS_VERSION}/kafka-clients-${KAFKA_CLIENTS_VERSION}.jar" \
    && curl -fSL -o "spark-token-provider-kafka-0-10_${SCALA_BINARY_VERSION}-${SPARK_VERSION}.jar" \
        "${MAVEN}/org/apache/spark/spark-token-provider-kafka-0-10_${SCALA_BINARY_VERSION}/${SPARK_VERSION}/spark-token-provider-kafka-0-10_${SCALA_BINARY_VERSION}-${SPARK_VERSION}.jar" \
    && curl -fSL -o "commons-pool2-${COMMONS_POOL2_VERSION}.jar" \
        "${MAVEN}/org/apache/commons/commons-pool2/${COMMONS_POOL2_VERSION}/commons-pool2-${COMMONS_POOL2_VERSION}.jar"

# Spark defaults wire the Iceberg catalog and S3A filesystem to MinIO.
COPY spark-defaults.conf ${SPARK_HOME}/conf/spark-defaults.conf

# Make sure the spark user can read everything we just dropped in.
RUN chmod -R a+r "${SPARK_HOME}/jars" "${SPARK_HOME}/conf"

# Switch back to the unprivileged user shipped by the base image.
USER spark
