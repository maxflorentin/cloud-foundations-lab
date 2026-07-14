"""
Lab 12 — Arquitecturas desacopladas: SNS fan-out + SQS + DLQ + Redis dedupe.

Flujo end-to-end:
1. Crear DLQ + 2 queues principales con RedrivePolicy → DLQ
2. Crear SNS topic
3. Subscribir ambas queues al topic (fan-out)
4. Publicar N eventos de github_events.jsonl al topic
5. Consumir de events-analytics con dedupe Redis
6. Enviar un poison message y verificar que llega a DLQ tras 3 fallos

Uso:
    python scripts/messaging_demo.py            # flujo completo, 5 mensajes
    python scripts/messaging_demo.py --messages 20 --skip-poison
"""

import argparse
import json
import sys
import time
from pathlib import Path

import boto3
import redis
from botocore.exceptions import ClientError

ENDPOINT = "http://localhost:4566"
REGION = "us-east-1"
ROOT = Path(__file__).parent.parent
MSG_DIR = ROOT / "messaging"
EVENTS_FILE = ROOT / "data" / "raw" / "events" / "github_events.jsonl"

BOTO_KWARGS = dict(
    endpoint_url=ENDPOINT,
    region_name=REGION,
    aws_access_key_id="test",
    aws_secret_access_key="test",
)


def client(service):
    return boto3.client(service, **BOTO_KWARGS)


# ── pasos ─────────────────────────────────────────────────────────────────────

def create_queues(sqs) -> tuple[str, dict]:
    cfg = json.loads((MSG_DIR / "queues.json").read_text())

    # 1) DLQ primero (necesitamos su ARN para el RedrivePolicy de las otras)
    dlq_cfg = cfg["dlq"]
    dlq_resp = sqs.create_queue(
        QueueName=dlq_cfg["Name"],
        Attributes=dlq_cfg.get("Attributes", {}),
    )
    dlq_url = dlq_resp["QueueUrl"]
    dlq_attrs = sqs.get_queue_attributes(
        QueueUrl=dlq_url, AttributeNames=["QueueArn"],
    )
    dlq_arn = dlq_attrs["Attributes"]["QueueArn"]
    print(f"  DLQ:            {dlq_url}")

    # 2) queues principales apuntando a la DLQ
    redrive_policy = json.dumps({
        "deadLetterTargetArn": dlq_arn,
        "maxReceiveCount": cfg["redrive"]["maxReceiveCount"],
    })

    queues = {}
    for q in cfg["queues"]:
        attrs = {**q.get("Attributes", {}), "RedrivePolicy": redrive_policy}
        resp = sqs.create_queue(QueueName=q["Name"], Attributes=attrs)
        queues[q["Name"]] = resp["QueueUrl"]
        print(f"  queue:          {q['Name']:<20} {resp['QueueUrl']}")

    return dlq_url, queues


def create_topic(sns) -> str:
    cfg = json.loads((MSG_DIR / "topic.json").read_text())
    resp = sns.create_topic(Name=cfg["Name"], Attributes=cfg.get("Attributes", {}))
    print(f"  topic:          {resp['TopicArn']}")
    return resp["TopicArn"]


def subscribe_queues_to_topic(sns, sqs, topic_arn: str, queues: dict) -> None:
    """Cada queue se subscribe al topic. Fan-out: 1 publish → N mensajes."""
    for qname, qurl in queues.items():
        qarn = sqs.get_queue_attributes(
            QueueUrl=qurl, AttributeNames=["QueueArn"],
        )["Attributes"]["QueueArn"]

        sub = sns.subscribe(
            TopicArn=topic_arn, Protocol="sqs", Endpoint=qarn,
            Attributes={"RawMessageDelivery": "true"},
        )
        # Permitir que SNS mande a la queue
        policy = json.dumps({
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Principal": {"Service": "sns.amazonaws.com"},
                "Action": "sqs:SendMessage",
                "Resource": qarn,
                "Condition": {"ArnEquals": {"aws:SourceArn": topic_arn}},
            }],
        })
        sqs.set_queue_attributes(QueueUrl=qurl, Attributes={"Policy": policy})
        print(f"  subscription:   {qname} ← topic ({sub['SubscriptionArn'][-16:]})")


def publish_events(sns, topic_arn: str, n: int = 5) -> int:
    """Publica N eventos del jsonl al topic (fan-out a todas las subs)."""
    if not EVENTS_FILE.exists():
        print(f"  ⚠ no encuentro {EVENTS_FILE}. Skipping publish.")
        return 0

    published = 0
    with EVENTS_FILE.open() as f:
        for line in f:
            if published >= n:
                break
            event = json.loads(line)
            sns.publish(
                TopicArn=topic_arn,
                Message=json.dumps(event),
                MessageAttributes={
                    "event_type": {
                        "DataType": "String",
                        "StringValue": event.get("type", "unknown"),
                    },
                },
            )
            published += 1
    print(f"  publicados: {published} eventos al topic")
    return published


def consume_with_dedupe(sqs, queue_url: str, rds, expected: int) -> None:
    """Consumer con dedupe por Redis: si vimos el message_id antes, no re-procesa."""
    seen = 0
    duplicates = 0
    empty_polls = 0

    while seen + duplicates < expected and empty_polls < 3:
        resp = sqs.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=10,
            WaitTimeSeconds=1,
        )
        messages = resp.get("Messages", [])
        if not messages:
            empty_polls += 1
            continue

        for msg in messages:
            body = json.loads(msg["Body"])
            key = f"lab12:dedupe:{msg['MessageId']}"

            # SET NX EX 3600: si no existe la clave, la crea (retorna True). Si existe, no toca (False).
            is_new = rds.set(key, "1", nx=True, ex=3600)

            if is_new:
                print(f"  ✓ procesado: {body.get('type', 'unknown'):<15} repo={body.get('repo', '?')[:40]}")
                seen += 1
            else:
                print(f"  ⤴ duplicado: {msg['MessageId'][:12]}... (skip)")
                duplicates += 1

            sqs.delete_message(QueueUrl=queue_url, ReceiptHandle=msg["ReceiptHandle"])

    print(f"  Total: {seen} procesados, {duplicates} deduplicados")


def poison_message_demo(sqs, queue_url: str, dlq_url: str) -> None:
    """Enviar un mensaje que 'falla' siempre → después de 3 receives va a DLQ."""
    # Poner VisibilityTimeout a 1s para que la DLQ demo sea rápida
    sqs.set_queue_attributes(
        QueueUrl=queue_url,
        Attributes={"VisibilityTimeout": "1"},
    )

    # Enviar el poison message
    sqs.send_message(
        QueueUrl=queue_url,
        MessageBody=json.dumps({"type": "POISON", "reason": "consumer falla siempre"}),
    )
    print(f"  enviado poison message a events-analytics")

    # Simular 3 intentos de procesamiento que "fallan" (no delete)
    for attempt in range(1, 5):
        resp = sqs.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=2,
        )
        messages = resp.get("Messages", [])
        if not messages:
            print(f"  intento {attempt}: cola vacía (¿ya se movió a DLQ?)")
            continue
        msg = messages[0]
        print(f"  intento {attempt}: recibido MessageId={msg['MessageId'][:12]}... — NO delete (simula fallo)")
        # NO delete → después del VisibilityTimeout vuelve a la cola
        time.sleep(2)

    # Verificar que la DLQ tenga el mensaje
    time.sleep(1)
    dlq_attrs = sqs.get_queue_attributes(
        QueueUrl=dlq_url, AttributeNames=["ApproximateNumberOfMessages"],
    )
    dlq_count = int(dlq_attrs["Attributes"]["ApproximateNumberOfMessages"])
    print(f"  DLQ ahora contiene: {dlq_count} poison messages")

    # Restaurar VisibilityTimeout
    sqs.set_queue_attributes(
        QueueUrl=queue_url, Attributes={"VisibilityTimeout": "30"},
    )


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="Lab 12 — SNS + SQS + DLQ demo")
    parser.add_argument("--messages", type=int, default=5, help="cuántos eventos publicar (default 5)")
    parser.add_argument("--skip-poison", action="store_true", help="saltear la demo de DLQ")
    args = parser.parse_args()

    print("=== Lab 12 — SNS fan-out → 2 SQS + DLQ + Redis dedupe ===\n")

    sqs = client("sqs")
    sns = client("sns")
    rds = redis.Redis(host="localhost", port=6379, decode_responses=True)
    rds.ping()

    print("1. Crear DLQ + 2 queues (con RedrivePolicy → DLQ)")
    dlq_url, queues = create_queues(sqs)

    print("\n2. Crear SNS topic")
    topic_arn = create_topic(sns)

    print("\n3. Subscribir ambas queues al topic (fan-out)")
    subscribe_queues_to_topic(sns, sqs, topic_arn, queues)

    print(f"\n4. Publicar {args.messages} eventos al topic")
    published = publish_events(sns, topic_arn, args.messages)

    print(f"\n5. Consumir de events-analytics con dedupe Redis")
    # Cada evento publicado genera 1 mensaje en cada queue (fan-out)
    consume_with_dedupe(sqs, queues["events-analytics"], rds, expected=published)

    if not args.skip_poison:
        print("\n6. Poison message → DLQ demo")
        poison_message_demo(sqs, queues["events-analytics"], dlq_url)

    print("\n=== Resumen ===")
    print(f"  DLQ:            {dlq_url}")
    for name, url in queues.items():
        print(f"  Queue:          {url}")
    print(f"  Topic:          {topic_arn}")
    print()
    print("Inspección:")
    print(f"  awslocal sqs get-queue-attributes --queue-url {queues['events-analytics']} --attribute-names All")
    print(f"  awslocal sns list-subscriptions-by-topic --topic-arn {topic_arn}")
    print(f"  awslocal sqs receive-message --queue-url {dlq_url}   # ver poison messages")
    return 0


if __name__ == "__main__":
    sys.exit(main())
