"""
Lab 14 — Lambda demo: cold start, warm start y costo por invocación.

Crea la función `validar-pago` en LocalStack, la invoca tres veces para
observar frío vs caliente, parsea los REPORT de CloudWatch Logs y calcula
el costo estimado para 1M de invocaciones.

LocalStack Community corre Lambdas reales en Docker: create-function, invoke,
update-function-configuration y logs funcionan tal cual. Los tiempos absolutos
no son representativos de AWS real, pero la diferencia relativa frío/caliente
sí es válida.

Uso:
    python scripts/lambda_demo.py
    python scripts/lambda_demo.py --memory 128   # experimento de memoria
    python scripts/lambda_demo.py --cleanup      # solo limpieza
"""

import argparse
import base64
import io
import json
import time
import zipfile
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

ENDPOINT = "http://localhost:4566"
REGION = "us-east-1"
ROOT = Path(__file__).parent.parent
LAMBDA_DIR = ROOT / "lambda"

FN_NAME = "validar-pago"
ROLE_NAME = "lambda-lab-role"
POLICY_ARN = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
# En LocalStack el account id es siempre 000000000000
ROLE_ARN = f"arn:aws:iam::000000000000:role/{ROLE_NAME}"

BOTO_KWARGS = dict(endpoint_url=ENDPOINT, region_name=REGION)


def client(service):
    return boto3.client(service, **BOTO_KWARGS)


# ---------------------------------------------------------------------------
# IAM
# ---------------------------------------------------------------------------

def create_execution_role(iam):
    trust = (LAMBDA_DIR / "trust_policy.json").read_text()
    try:
        iam.create_role(
            RoleName=ROLE_NAME,
            AssumeRolePolicyDocument=trust,
        )
        print(f"[IAM] Rol '{ROLE_NAME}' creado.")
    except ClientError as e:
        if e.response["Error"]["Code"] == "EntityAlreadyExists":
            print(f"[IAM] Rol '{ROLE_NAME}' ya existe, continúo.")
        else:
            raise

    iam.attach_role_policy(RoleName=ROLE_NAME, PolicyArn=POLICY_ARN)
    print(f"[IAM] Política adjuntada: AWSLambdaBasicExecutionRole")
    print()
    print("  Trust policy  → quién puede ASUMIR el rol: lambda.amazonaws.com")
    print("  Permissions   → qué puede HACER el código: escribir logs en CloudWatch")
    print("  (Resource policy de la función: quién puede invocarla — no usada acá)")
    print()


def delete_execution_role(iam):
    try:
        iam.detach_role_policy(RoleName=ROLE_NAME, PolicyArn=POLICY_ARN)
    except ClientError:
        pass
    try:
        iam.delete_role(RoleName=ROLE_NAME)
        print(f"[IAM] Rol '{ROLE_NAME}' eliminado.")
    except ClientError:
        pass


# ---------------------------------------------------------------------------
# Lambda
# ---------------------------------------------------------------------------

def zip_handler() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(LAMBDA_DIR / "handler.py", "handler.py")
    return buf.getvalue()


def create_function(lam, memory_mb: int = 512):
    code = zip_handler()
    try:
        lam.create_function(
            FunctionName=FN_NAME,
            Runtime="python3.11",
            Handler="handler.handler",
            Role=ROLE_ARN,
            Code={"ZipFile": code},
            Timeout=10,
            MemorySize=memory_mb,
        )
        print(f"[Lambda] Función '{FN_NAME}' creada (memory={memory_mb} MB).")
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceConflictException":
            print(f"[Lambda] Función ya existe, actualizando código y config…")
            lam.update_function_code(FunctionName=FN_NAME, ZipFile=code)
            lam.update_function_configuration(
                FunctionName=FN_NAME, MemorySize=memory_mb
            )
        else:
            raise

    _wait_active(lam)


def _wait_active(lam, max_wait: int = 30):
    for _ in range(max_wait):
        state = lam.get_function_configuration(FunctionName=FN_NAME)["State"]
        if state == "Active":
            return
        time.sleep(1)
    raise TimeoutError("Lambda no llegó a Active en el tiempo esperado.")


def print_configuration(lam):
    cfg = lam.get_function_configuration(FunctionName=FN_NAME)
    print("\n=== Anatomía de la función (slide 7) ===")
    for key in ("Runtime", "MemorySize", "Timeout", "Handler", "Role", "State"):
        print(f"  {key}: {cfg.get(key)}")
    print()


def invoke(lam, payload: dict, label: str) -> dict:
    start = time.monotonic()
    resp = lam.invoke(
        FunctionName=FN_NAME,
        Payload=json.dumps(payload).encode(),
    )
    elapsed_ms = round((time.monotonic() - start) * 1000)
    body = json.loads(resp["Payload"].read())
    status = resp["StatusCode"]
    fn_error = resp.get("FunctionError", "")

    print(f"[{label}] status={status} elapsed={elapsed_ms}ms fn_error={fn_error!r}")
    print(f"  body: {body}")
    return {"label": label, "status": status, "elapsed_ms": elapsed_ms, "body": body}


def delete_function(lam):
    try:
        lam.delete_function(FunctionName=FN_NAME)
        print(f"[Lambda] Función '{FN_NAME}' eliminada.")
    except ClientError:
        pass


# ---------------------------------------------------------------------------
# CloudWatch Logs
# ---------------------------------------------------------------------------

LOG_GROUP = f"/aws/lambda/{FN_NAME}"


def delete_log_group(logs_client):
    try:
        logs_client.delete_log_group(logGroupName=LOG_GROUP)
        print(f"[Logs] Log group '{LOG_GROUP}' eliminado.")
    except ClientError:
        pass


def tail_logs(logs_client, max_streams: int = 10) -> list[dict]:
    """Lee todos los streams recientes y combina REPORT + JSON del handler por invocación.

    Ministack crea un stream por invocación (AWS real reutiliza el stream en warm starts).
    Ministack no emite Init Duration en REPORT — lo detectamos desde el campo cold_start
    que el handler imprime como JSON.
    """
    try:
        # Ordenar ascendente (más antiguo primero) para que inv-1 quede primero
        streams = logs_client.describe_log_streams(
            logGroupName=LOG_GROUP,
            orderBy="LastEventTime",
            descending=False,
            limit=max_streams,
        )["logStreams"]
    except ClientError:
        print("[Logs] Log group todavía no existe — probá de nuevo en unos segundos.")
        return []

    invocations = []
    for stream in streams:
        events = logs_client.get_log_events(
            logGroupName=LOG_GROUP,
            logStreamName=stream["logStreamName"],
            startFromHead=True,
        )["events"]

        inv: dict = {}
        for ev in events:
            msg = ev["message"].strip()
            if msg.startswith("REPORT"):
                for token in msg.split("\t"):
                    token = token.strip()
                    for field, key in [
                        ("Duration:", "duration_ms"),
                        ("Billed Duration:", "billed_ms"),
                        ("Memory Size:", "memory_mb"),
                        ("Max Memory Used:", "used_mb"),
                        ("Init Duration:", "init_ms"),
                    ]:
                        if token.startswith(field):
                            inv[key] = float(token[len(field):].strip().split()[0])
            elif msg.startswith("{") and "cold_start" in msg:
                try:
                    data = json.loads(msg)
                    inv["cold_start"] = data.get("cold_start")
                    inv["init_age_ms"] = data.get("init_age_ms")
                except json.JSONDecodeError:
                    pass

        if inv:
            invocations.append(inv)

    return invocations


def print_reports(invocations: list[dict]):
    print("\n=== CloudWatch Logs — REPORT por invocación ===")
    print("(ministack no emite Init Duration; cold_start lo detecta el handler)\n")
    for i, inv in enumerate(invocations, 1):
        cold = inv.get("cold_start")
        if cold is True:
            label = "FRÍO  ❄️ "
        elif cold is False:
            label = "CALIENTE 🔥"
        else:
            label = "desconocido"
        print(f"  Invocación {i} [{label}]")
        print(f"    Duration:      {inv.get('duration_ms', '?')} ms")
        print(f"    Billed:        {inv.get('billed_ms', '?')} ms")
        print(f"    Memory Size:   {inv.get('memory_mb', '?')} MB")
        print(f"    Max Used:      {inv.get('used_mb', '?')} MB")
        if cold is True and inv.get("init_age_ms") is not None:
            print(f"    init_age_ms:   {inv['init_age_ms']} ms  ← overhead de cold start")
        if "init_ms" in inv:
            print(f"    Init Duration: {inv['init_ms']} ms  ← (AWS real)")
        print()


# ---------------------------------------------------------------------------
# Cálculo de costo
# ---------------------------------------------------------------------------

def calculate_cost(billed_ms: float, memory_mb: float, invocations: int = 1_000_000):
    gb_s = (memory_mb / 1024) * (billed_ms / 1000) * invocations
    compute_cost = gb_s * 0.0000166667
    request_cost = invocations / 1_000_000 * 0.20
    total = compute_cost + request_cost
    return gb_s, compute_cost, request_cost, total


def print_cost(billed_ms: float, memory_mb: float):
    gb_s, compute, requests, total = calculate_cost(billed_ms, memory_mb)
    ec2_monthly = 8.50  # t3.micro 24/7 us-east-1 (~$0.0116/hr × 730h)

    print("=== Estimación de costo para 1M invocaciones/mes ===")
    print(f"  Billed Duration:  {billed_ms} ms")
    print(f"  Memory:           {memory_mb} MB")
    print(f"  GB-s:             {gb_s:.4f}")
    print(f"  Cómputo:          ${compute:.4f}")
    print(f"  Requests (1M):    ${requests:.4f}")
    print(f"  TOTAL Lambda:     ${total:.4f}")
    print()
    print(f"  Referencia: EC2 t3.micro 24/7 ≈ ${ec2_monthly:.2f}/mes")

    # breakeven: cuántas invocaciones/mes cuesta lo mismo que la instancia
    _, c_per_inv, r_per_inv, _ = calculate_cost(billed_ms, memory_mb, invocations=1)
    cost_per_inv = c_per_inv + r_per_inv
    if cost_per_inv > 0:
        breakeven = int(ec2_monthly / cost_per_inv)
        print(f"  Breakeven:        a partir de ~{breakeven:,} inv/mes Lambda es más caro")
        print(f"  → Por debajo de ese volumen, Lambda gana en costo.")
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run(memory_mb: int):
    iam = client("iam")
    lam = client("lambda")
    logs = client("logs")

    print("=== Lab 14 — Lambda: cold start, warm start y costo ===\n")

    # Limpiar logs de runs anteriores para no mezclar invocaciones
    delete_log_group(logs)

    # Rol de ejecución
    create_execution_role(iam)

    # Función
    create_function(lam, memory_mb)
    print_configuration(lam)

    # Invocaciones: frío + 2 calientes
    print("=== Invocaciones ===")
    invoke(lam, {"monto": 12000}, "inv-1 (esperado cold)")
    invoke(lam, {"monto": 12000}, "inv-2 (esperado warm)")
    invoke(lam, {"monto": 12000}, "inv-3 (esperado warm)")

    # Caso de rechazo — 402 no es error de Lambda
    print()
    result = invoke(lam, {"monto": 90000}, "inv-4 (rechazo negocio)")
    assert result["status"] == 200, "Lambda reportó error de plataforma — no debería"
    body = result["body"]
    assert body.get("statusCode") == 402, "La función debería devolver 402 para monto > 50000"
    print("  ✓ HTTP 402 es un rechazo de negocio — Lambda lo trata como éxito de plataforma\n")

    # Logs
    time.sleep(2)  # ministack necesita un momento para flushear logs
    invocations = tail_logs(logs)
    if invocations:
        print_reports(invocations)
        # usar la primera invocación del cold start para el cálculo de costo
        first = next((inv for inv in invocations if inv.get("cold_start") is True and "billed_ms" in inv),
                     next((inv for inv in invocations if "billed_ms" in inv), {}))
        billed = first.get("billed_ms", 1.0)
        mem = first.get("memory_mb", memory_mb)
        print_cost(billed, mem)
    else:
        print("[Logs] Sin datos todavía. Corré: aws --endpoint-url=http://localhost:4566 logs tail /aws/lambda/validar-pago")
        print_cost(1.0, memory_mb)


def cleanup():
    iam = client("iam")
    lam = client("lambda")
    logs = client("logs")
    print("=== Limpieza ===")
    delete_function(lam)
    delete_log_group(logs)
    delete_execution_role(iam)
    print("Listo. Recordá hacer `localstack stop` si terminaste con el entorno.")


def main():
    parser = argparse.ArgumentParser(description="Lab 14 — Lambda demo")
    parser.add_argument("--memory", type=int, default=512,
                        help="Memoria de la función en MB (default: 512)")
    parser.add_argument("--cleanup", action="store_true",
                        help="Solo eliminar la función y el rol, sin crear nada")
    args = parser.parse_args()

    if args.cleanup:
        cleanup()
    else:
        run(args.memory)


if __name__ == "__main__":
    main()
