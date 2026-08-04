# Lab 14 — Serverless: Lambda, cold start y costo por invocación

**Clase:** 14 · **Tiempo estimado:** 45–60 min · **Entregable:** `NombreApellido.md`

> **Objetivo:** crear, invocar y observar una función Lambda desde la CLI.
> Al terminar tenés que poder responder con evidencia:
> 1. ¿Qué cambia entre una invocación en frío y una en caliente?
> 2. ¿Con qué permisos corrió tu código y de dónde salieron?
> 3. ¿Cuánta memoria usó realmente y cuánto pagarías por 1M de invocaciones?

---

## Prerrequisitos

- LocalStack corriendo: `docker compose up -d localstack`
- `awscli-local` instalado: `pip install awscli-local`

Verificar:

```bash
awslocal lambda list-functions   # debe responder sin error
```

Variables que vas a usar en todos los comandos:

```bash
export FN=validar-pago
export ROLE=lambda-lab-role
```

---

## Paso 0 — Leer el handler antes de deployarlo

```bash
cat lambda/handler.py
```

Dos partes deliberadas:

- **Fuera del handler** (`BOOT_TS`, `COLD`): se inicializan una sola vez por entorno de ejecución. Acá irían clientes SDK, pools de conexión, config. En AWS real, esto se amortiza entre invocaciones del mismo entorno.
- **Dentro del handler**: corre en cada invocación. El log imprime si fue cold start, cuánto tiempo tiene de vida el entorno y los ms restantes del timeout.

---

## Paso 1 — Execution role

La función necesita un rol que Lambda pueda asumir. Leé la política primero:

```bash
cat lambda/trust_policy.json
```

¿Quién puede asumir este rol? ¿Qué diferencia hay con una política de permisos?

Crear el rol:

```bash
awslocal iam create-role \
  --role-name $ROLE \
  --assume-role-policy-document file://lambda/trust_policy.json

awslocal iam attach-role-policy \
  --role-name $ROLE \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
```

> **Para el entregable:** identificá las **dos** políticas en juego — la *trust policy*
> (quién puede asumir el rol) y la *permissions policy* (qué puede hacer el código).
> No son lo mismo que la *resource policy* (quién puede invocar la función).

---

## Paso 2 — Crear la función

```bash
zip function.zip lambda/handler.py

awslocal lambda create-function \
  --function-name $FN \
  --runtime python3.11 \
  --handler handler.handler \
  --role arn:aws:iam::000000000000:role/$ROLE \
  --zip-file fileb://function.zip \
  --timeout 10 \
  --memory-size 512
```

Verificar la anatomía (es la slide 7):

```bash
awslocal lambda get-function-configuration --function-name $FN \
  --query '{Runtime:Runtime,Memory:MemorySize,Timeout:Timeout,Handler:Handler,Role:Role}'
```

Pegá esa salida en el entregable.

---

## Paso 3 — Invocar: frío vs caliente

```bash
echo '{"monto": 12000}' > event.json

# 1ra invocación → cold start esperado
time awslocal lambda invoke --function-name $FN \
  --payload fileb://event.json out1.json && cat out1.json

# 2da y 3ra, inmediatas → warm esperado
time awslocal lambda invoke --function-name $FN \
  --payload fileb://event.json out2.json && cat out2.json
time awslocal lambda invoke --function-name $FN \
  --payload fileb://event.json out3.json && cat out3.json
```

Completá la tabla con los resultados (`cold_start` viene del JSON del body; `Init Duration` viene de los logs en el paso siguiente):

| invocación | `cold_start` en body | duración `time` | `Billed Duration` (logs) | `Init Duration` (logs) |
|---|---|---|---|---|
| 1 | | | | |
| 2 | | | | |
| 3 | | | | |

Probá también el camino de rechazo:

```bash
echo '{"monto": 90000}' | \
  awslocal lambda invoke --function-name $FN --payload fileb:///dev/stdin /dev/stdout
```

¿El `StatusCode` de Lambda fue 200 o 4xx? ¿Por qué? Anotalo en el entregable.

---

## Paso 4 — Logs y línea REPORT

```bash
awslocal logs tail /aws/lambda/$FN --format short
```

Buscá la línea `REPORT` de cada invocación:

```
REPORT RequestId: ...  Duration: 1.84 ms  Billed Duration: 2 ms
       Memory Size: 512 MB  Max Memory Used: 42 MB  Init Duration: 118.30 ms
```

Tres lecturas obligatorias:

- **`Init Duration`** aparece solo en la primera invocación → ese es el cold start.
- **`Billed Duration`** es lo que pagás, redondeado al ms más cercano.
- **`Max Memory Used`** vs **`Memory Size`**: si usás 42 MB de 512, estás sobre-aprovisionado.
  Pero recordá: en Lambda **la CPU escala con la memoria**, así que bajarla puede empeorar la duración.

### Mini-experimento (recomendado)

```bash
awslocal lambda update-function-configuration --function-name $FN --memory-size 128
# invocar 3 veces y registrar Duration
awslocal lambda update-function-configuration --function-name $FN --memory-size 1024
# invocar 3 veces y registrar Duration
```

¿Bajó la duración lo suficiente para compensar el GB-s extra? Esa es la pregunta
de la slide 15.

---

## Paso 5 — Cálculo de costo

Con tu `Billed Duration` y `Memory Size` reales, para **1.000.000 de invocaciones/mes**:

```
GB-s          = (memoria_MB / 1024) × (billed_ms / 1000) × 1.000.000
costo_cómputo = GB-s × 0.0000166667 USD
costo_requests = 1.000.000 / 1.000.000 × 0.20 = 0.20 USD
total         = costo_cómputo + costo_requests
```

Compará contra una instancia `t3.micro` encendida 24/7 (~$8.50/mes en us-east-1).
¿A partir de qué volumen de invocaciones te conviene la instancia?

Precios actuales: https://aws.amazon.com/lambda/pricing/

---

## Alternativa: correr todo desde Python

El script `scripts/lambda_demo.py` hace los pasos 1–5 en un solo comando:

```bash
python scripts/lambda_demo.py
```

Útil para ver el flujo completo automatizado y como referencia de cómo se hace con boto3 en lugar de la CLI.

Experimento de memoria desde el script:

```bash
python scripts/lambda_demo.py --memory 128
python scripts/lambda_demo.py --memory 1024
```

---

## Paso 6 — Limpieza

```bash
awslocal lambda delete-function --function-name $FN
awslocal iam detach-role-policy --role-name $ROLE \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
awslocal iam delete-role --role-name $ROLE
rm -f function.zip out1.json out2.json out3.json event.json
```

O con el script:

```bash
python scripts/lambda_demo.py --cleanup
```

> Serverless también deja basura si no la limpiás: funciones huérfanas, roles con
> permisos vivos y log groups que siguen acumulando datos.

---

## Entregable — `NombreApellido.md`

1. La salida de `get-function-configuration` (anatomía de la función).
2. Los outputs de las 3 invocaciones (`cold_start`, body, statusCode).
3. La **tabla frío vs caliente** completa con `Init Duration` de los logs.
4. La respuesta al caso de rechazo (`{"monto": 90000}`) y tu explicación.
5. El **cálculo de costo** para 1M de invocaciones con tus números reales y el breakeven vs instancia.
6. Tres líneas de cierre:
   - ¿Qué te sorprendió?
   - ¿Qué límite de Lambda te tocaría primero si esta función creciera?
   - ¿En qué caso **no** usarías Lambda para este caso de uso?

### Criterios de corrección

| # | Criterio | Peso |
|---|---|---|
| 1 | La función se crea y responde a ambos casos (aprobado / rechazado) | 25% |
| 2 | Evidencia clara de la diferencia frío vs caliente (`Init Duration` en logs) | 25% |
| 3 | Lectura correcta del `REPORT`: billed duration y memoria usada | 20% |
| 4 | Cálculo de costo y breakeven razonados con tus números reales | 20% |
| 5 | Limpieza de recursos + reflexión de cierre | 10% |

---

## Límites del entorno

LocalStack Community corre Lambdas reales en Docker: `create-function`, `invoke`,
`update-function-configuration` y `logs` funcionan tal cual. Lo que **no** podés
probar acá:

- **Provisioned concurrency** y **SnapStart** → requieren AWS real.
- Los tiempos absolutos no son representativos de AWS real. **La diferencia
  relativa frío/caliente sí es válida** — es lo que estamos midiendo.

---

## Referencias

- Lambda con la CLI: https://docs.aws.amazon.com/lambda/latest/dg/gettingstarted-awscli.html
- Ciclo de vida del entorno: https://docs.aws.amazon.com/lambda/latest/dg/lambda-runtime-environment.html
- Execution role: https://docs.aws.amazon.com/lambda/latest/dg/lambda-intro-execution-role.html
- Configuración de memoria: https://docs.aws.amazon.com/lambda/latest/dg/configuration-memory.html
- Cuotas de Lambda: https://docs.aws.amazon.com/lambda/latest/dg/gettingstarted-limits.html
- LocalStack Lambda: https://docs.localstack.cloud/aws/services/lambda/
