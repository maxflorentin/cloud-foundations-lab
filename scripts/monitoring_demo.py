"""
Lab 11 — Operations & Reliability: métrica → alarma → estado → acción SNS.

Cierra el ciclo básico de observabilidad + alarma accionable:
  1. Crea el topic SNS (destino de la alarma)
  2. Publica métricas custom (simula datos de un servicio)
  3. Crea una alarma CloudWatch: umbral + N períodos → topic
  4. Fuerza el estado con set-alarm-state (OK → ALARM → OK)
  5. Consulta el historial de la alarma

Idempotente: si los recursos ya existen, no explota.

Uso:
    python3 scripts/monitoring_demo.py
"""

import json
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

ENDPOINT = "http://localhost:4566"
REGION = "us-east-1"
ROOT = Path(__file__).parent.parent
MONITORING_DIR = ROOT / "monitoring"

BOTO_KWARGS = dict(
    endpoint_url=ENDPOINT,
    region_name=REGION,
    aws_access_key_id="test",
    aws_secret_access_key="test",
)


def client(service):
    return boto3.client(service, **BOTO_KWARGS)


# ── pasos ─────────────────────────────────────────────────────────────────────

def create_sns_topic(sns):
    cfg = json.loads((MONITORING_DIR / "sns-topic.json").read_text())
    resp = sns.create_topic(
        Name=cfg["Name"],
        Attributes=cfg.get("Attributes", {}),
    )
    arn = resp["TopicArn"]
    print(f"  ✓ SNS topic:    {arn}")
    return arn


def publish_metric_data(cw):
    """Simula 5 datapoints de CPUUtilization en el namespace 'Project'."""
    values = [42, 48, 55, 62, 45]  # último por debajo del umbral
    for v in values:
        cw.put_metric_data(
            Namespace="Project",
            MetricData=[{
                "MetricName": "CPUUtilization",
                "Value": v,
                "Unit": "Percent",
                "Timestamp": datetime.now(timezone.utc),
                "Dimensions": [{"Name": "Service", "Value": "web-tier"}],
            }],
        )
    print(f"  ✓ métricas publicadas: {values} (namespace=Project, service=web-tier)")


def create_alarm(cw, topic_arn: str):
    cfg = json.loads((MONITORING_DIR / "alarm.json").read_text())
    # Redirigir la acción al topic real creado en este run
    cfg["AlarmActions"] = [topic_arn]
    cfg["OKActions"] = [topic_arn]

    try:
        cw.put_metric_alarm(**{k: v for k, v in cfg.items() if k != "Tags"})
    except ClientError as e:
        if "AlreadyExists" in str(e):
            pass
        else:
            raise

    # Verificar
    resp = cw.describe_alarms(AlarmNames=[cfg["AlarmName"]])
    alarm = resp["MetricAlarms"][0]
    print(f"  ✓ alarma creada: {alarm['AlarmName']}")
    print(f"      métrica:      {alarm['Namespace']}/{alarm['MetricName']}")
    print(f"      umbral:       > {alarm['Threshold']}")
    print(f"      períodos:     {alarm['EvaluationPeriods']} x {alarm['Period']}s")
    print(f"      estado:       {alarm['StateValue']}")
    return alarm["AlarmName"]


def force_alarm_transitions(cw, alarm_name: str):
    """OK → ALARM → OK. Verifica que las transiciones se registran."""
    for state, reason in [
        ("ALARM", "prueba de disparo: forzado desde el lab"),
        ("OK", "prueba de recuperación: forzado desde el lab"),
    ]:
        cw.set_alarm_state(
            AlarmName=alarm_name,
            StateValue=state,
            StateReason=reason,
        )
        time.sleep(1)
        current = cw.describe_alarms(AlarmNames=[alarm_name])["MetricAlarms"][0]
        print(f"  ✓ {state}: {current['StateValue']}  reason: {current['StateReason'][:50]}")


def show_history(cw, alarm_name: str):
    resp = cw.describe_alarm_history(
        AlarmName=alarm_name,
        HistoryItemType="StateUpdate",
        MaxRecords=5,
    )
    items = resp.get("AlarmHistoryItems", [])
    print(f"  {len(items)} eventos de state update:")
    for it in items[:5]:
        ts = it["Timestamp"].strftime("%H:%M:%S")
        print(f"    {ts}  {it['HistorySummary']}")


def list_subscribers(sns, topic_arn: str):
    resp = sns.list_subscriptions_by_topic(TopicArn=topic_arn)
    subs = resp.get("Subscriptions", [])
    if not subs:
        print(f"  ⚠ sin subscribers todavía")
        print(f"    En AWS real, agregar:  aws sns subscribe --topic-arn {topic_arn} --protocol email --notification-endpoint tu@mail.com")
    else:
        for s in subs:
            print(f"    - {s['Protocol']}: {s['Endpoint']}")


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    print("=== Lab 11 — Monitoring: métrica → alarma → estado → SNS ===\n")

    sns = client("sns")
    cw = client("cloudwatch")

    print("1. SNS topic (destino de la alarma)")
    topic_arn = create_sns_topic(sns)

    print("\n2. Publicar métricas custom")
    publish_metric_data(cw)

    print("\n3. Crear alarma (CPU > 70% durante 3 períodos)")
    alarm_name = create_alarm(cw, topic_arn)

    print("\n4. Forzar transiciones de estado")
    force_alarm_transitions(cw, alarm_name)

    print("\n5. Historial de la alarma")
    show_history(cw, alarm_name)

    print("\n6. Subscribers del topic")
    list_subscribers(sns, topic_arn)

    print("\n=== Resumen ===")
    print(f"  SNS topic:      {topic_arn}")
    print(f"  Alarma:         {alarm_name}")
    print(f"  Métrica watchd: AWS/EC2 CPUUtilization (dim AutoScalingGroupName=web-tier-asg)")
    print()
    print("Inspección:")
    print(f"  awslocal cloudwatch describe-alarms --alarm-names {alarm_name}")
    print(f"  awslocal cloudwatch describe-alarm-history --alarm-name {alarm_name}")
    print(f"  awslocal sns list-subscriptions-by-topic --topic-arn {topic_arn}")


if __name__ == "__main__":
    sys.exit(main() or 0)
