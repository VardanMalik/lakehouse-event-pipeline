"""CLI entry point for the synthetic-event Kafka producer."""

from __future__ import annotations

import argparse
import signal
import time
from typing import Optional

from lakehouse.common.config import Settings, get_settings
from lakehouse.common.logging import configure_logging, get_logger
from lakehouse.producer.generator import EventGenerator
from lakehouse.producer.kafka_producer import EventPublisher


THROUGHPUT_LOG_INTERVAL_SECONDS = 5.0


def build_arg_parser(settings: Settings) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lakehouse.producer",
        description="Generate synthetic customer events and publish them to Kafka.",
    )
    parser.add_argument("--rate", type=int, default=100, help="Target events/sec.")
    parser.add_argument(
        "--duration",
        type=int,
        default=60,
        help="Seconds to run (0 = forever).",
    )
    parser.add_argument(
        "--topic",
        type=str,
        default=settings.kafka_topic_events,
        help="Kafka topic to publish to.",
    )
    parser.add_argument(
        "--bootstrap-servers",
        type=str,
        default=settings.kafka_bootstrap_servers_host,
        help="Kafka bootstrap servers.",
    )
    parser.add_argument("--user-pool-size", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=None)
    return parser


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    settings = get_settings()
    return build_arg_parser(settings).parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    settings = get_settings()
    configure_logging(settings)
    log = get_logger("lakehouse.producer.main")

    args = build_arg_parser(settings).parse_args(argv)

    if args.rate <= 0:
        raise SystemExit("--rate must be positive")

    generator = EventGenerator(user_pool_size=args.user_pool_size, seed=args.seed)
    publisher = EventPublisher(
        bootstrap_servers=args.bootstrap_servers,
        topic=args.topic,
    )

    stop_requested = {"value": False}

    def _request_stop(signum, _frame):  # noqa: ANN001 — signal handler signature
        log.info("producer_signal_received", signal=signum)
        stop_requested["value"] = True

    signal.signal(signal.SIGINT, _request_stop)
    signal.signal(signal.SIGTERM, _request_stop)

    log.info(
        "producer_starting",
        target_rate=args.rate,
        duration=args.duration,
        topic=args.topic,
        bootstrap_servers=args.bootstrap_servers,
        user_pool_size=args.user_pool_size,
    )

    target_interval = 1.0 / args.rate
    start = time.monotonic()
    next_log = start + THROUGHPUT_LOG_INTERVAL_SECONDS
    last_log_sent = 0
    last_log_at = start

    try:
        while not stop_requested["value"]:
            iter_start = time.monotonic()
            if args.duration > 0 and (iter_start - start) >= args.duration:
                break

            event = generator.generate_event()
            publisher.publish(event)

            if iter_start >= next_log:
                observed = (publisher.total_sent - last_log_sent) / max(
                    iter_start - last_log_at, 1e-6
                )
                log.info(
                    "producer_throughput",
                    target_rate=args.rate,
                    observed_rate=round(observed, 2),
                    total_sent=publisher.total_sent,
                    total_delivered=publisher.total_delivered,
                    total_failed=publisher.total_failed,
                )
                last_log_sent = publisher.total_sent
                last_log_at = iter_start
                next_log = iter_start + THROUGHPUT_LOG_INTERVAL_SECONDS

            elapsed = time.monotonic() - iter_start
            sleep_for = target_interval - elapsed
            if sleep_for > 0:
                time.sleep(sleep_for)
    finally:
        publisher.flush()
        log.info("producer_stopped", **publisher.metrics())

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
