# Lab 16 — Data lake por zonas

**Clase:** 16 · **Tiempo estimado:** 60–75 min · **Entregable:** `NombreApellido.md`

> **Objetivo:** armar un data lake con cuatro zonas sobre almacenamiento de objetos local,
> alimentado por dos fuentes reales, y administrarlo con permisos por zona.
>
> El objetivo **no es mover datos**. Al terminar tenés que poder defender tres decisiones:
> 1. Qué vive en cada zona y **por qué no se borra raw**.
> 2. Cómo particionaste y **qué query se vuelve cara** si elegís otra partición.
> 3. Quién puede leer cada zona y **cómo lo hiciste cumplir**.

---

## Stack y equivalencias AWS

| En el lab | En AWS | Nota |
|---|---|---|
| MinIO | S3 | habla la API de S3: mismas rutas, buckets y políticas |
| Hive Metastore | Glue Data Catalog | el catálogo que consultan todos los motores |
| Trino | Athena | Athena está construido sobre Presto/Trino: es el mismo motor |
| Postgres | RDS (fuente OLTP) | la base transaccional de la que se extrae |

---

## Prerrequisitos

- Docker y Docker Compose instalados
- Estar parado en el directorio `lab-16/`

```bash
cd lab-16
```

---

## Paso 0 — Levantar el entorno

```bash
make up
```

Esto levanta Postgres (con ~200k pagos ya cargados), MinIO, Hive Metastore y Trino.
El metastore descarga el driver JDBC de Postgres en el primer arranque (~30 segundos extra).

Verificá que Trino ve el catálogo antes de continuar:

```bash
make check-metastore
```

Tenés que ver `lake` en la lista de catálogos y los schemas `information_schema`.
**Si eso no aparece, no sigas** — algo no levantó bien. Revisá:

```bash
make logs   # logs de metastore y trino
```

---

## Paso 1 — Crear las zonas

```bash
make zones
```

Cuatro buckets en MinIO: `landing`, `raw`, `curated`, `consumer`.

**¿Por qué cuatro buckets y no cuatro carpetas?**
La separación física es lo que permite dar permisos distintos por zona sin escribir
políticas con prefijos frágiles. En AWS esto son cuatro buckets S3 distintos.

Mirá la consola de MinIO en `http://localhost:9001` (minioadmin / minioadmin) y
verificá que los cuatro buckets existen.

---

## Paso 2 — Landing: tal como llegó

```bash
make landing
```

Extrae de Postgres y copia el CSV de operadores **sin transformar nada**.
El layout en MinIO es:

```
landing/
├── postgres/pagos/fecha_ingesta=2024-01-15/pagos.csv
├── postgres/usuarios/fecha_ingesta=2024-01-15/usuarios.csv
└── externo/operadores/fecha_ingesta=2024-01-15/operadores.csv
```

Regla de la zona: **nadie consulta landing directamente**. Es evidencia de lo que
llegó, con su fecha de ingesta. Si raw o curated se corrompen, landing es el backup.

Antes de seguir: abrí `seed/csv/operadores.csv` y encontrá los cuatro problemas de
calidad que están a propósito. Anotá cuáles son — los vas a resolver en curated.

---

## Paso 3 — Raw: formato estándar, misma semántica

```bash
make raw
```

Convierte los CSV a Parquet **sin limpiar ni deduplicar**, particionado por `fecha`.

Medí la diferencia de tamaño que imprimió el comando:

- ¿Cuánto pesa landing en CSV?
- ¿Cuánto pesa raw en Parquet?
- ¿Qué explica la diferencia?

La partición por `fecha` permite que una query sobre los últimos 7 días no lea los
60 días de historia. Probalo desde Trino:

```bash
# conectarse a Trino
docker compose exec trino trino --catalog lake
```

```sql
-- con partition pruning: lee solo 7 particiones
SELECT count(*), sum(monto)
FROM lake.raw.pagos
WHERE fecha >= current_date - INTERVAL '7' DAY;

-- sin filtro de fecha: escanea las 60 particiones
SELECT count(*), sum(monto)
FROM lake.raw.pagos;
```

Mirá en la UI de Trino (`http://localhost:8080`) cuántos bytes escaneó cada query.
Esa diferencia en bytes es la diferencia en costo en Athena ($5 por TB escaneado).

> **Para el entregable:** anotá el ratio de bytes escaneados entre la query con filtro y
> sin filtro. ¿Qué query se volvería cara si hubieras particionado por `operador_id`?

---

## Paso 4 — Curated: tipada, deduplicada, unida, PII tratada

```bash
make curated
```

Aplica las transformaciones de calidad:
- **Deduplicación** por `pago_id` (window function `row_number`)
- **Join** con operadores (el CSV sucio)
- **Normalización** de país a mayúsculas (`upper()`)
- **Enmascaramiento de PII**: documento → `203***`, email → `***@dominio.com`
- **Descarte** de comisiones nulas con `COALESCE(..., 0.0)`

Ejecutá los chequeos de calidad:

```bash
make checks
```

Cuatro chequeos obligatorios antes de publicar una tabla curated:

| Chequeo | Qué verifica |
|---|---|
| Duplicados | `count(*) - count(DISTINCT pago_id) = 0` |
| Nulos críticos | No hay operador ni país nulo |
| Rangos | Montos > 0 y fechas ≤ hoy |
| Frescura | La fecha máxima es reciente |

**Si alguno falla, el pipeline no publica.** Anotá los resultados en el entregable.

> **Para el entregable:** ¿cuántos operadores del CSV no pudieron unirse porque tenían
> el `operador_id` sucio? (Pista: buscá nulos en `operador` después del join.)

---

## Paso 5 — Consumer: el número de negocio

```bash
make consumer
```

Una tabla con nombres de negocio, sin PII, lista para el dashboard:
`fecha`, `pais`, `pagos`, `monto_total`, `tasa_aprobacion`.

Mirá el preview que imprimió el comando. ¿La tasa de aprobación parece razonable
para una billetera digital?

---

## Paso 6 — Permisos por zona

```bash
make permisos
```

Crea un usuario `analista` con una política que solo permite leer `consumer`.

El output tiene que mostrar:
- `mc ls analista/consumer` → lista los archivos ✅
- `mc ls analista/curated` → `Access Denied` ❌
- `mc ls analista/landing` → `Access Denied` ❌

**Si el segundo comando funciona, la política no está aplicada. No pases al entregable hasta que falle.**

Esto es la diferencia entre "tenemos zonas" y "tenemos zonas con control de acceso".

---

## Entregable — `NombreApellido.md`

1. **Tabla de administración** (una fila por zona):

   | Zona | Dueño | Quién escribe | Quién lee | Retención |
   |---|---|---|---|---|

2. **Los cuatro problemas de calidad** del CSV de operadores (los que encontraste en Paso 2).

3. **Tamaños por zona** (salida de `mc du`) y explicación de la diferencia landing → raw.

4. **Ratio de bytes escaneados** con/sin filtro de fecha, y la query que se volvería cara
   si la partición fuera por `operador_id`.

5. **Resultados de los cuatro chequeos de calidad** (salida de `make checks`).

6. **La política de acceso** aplicada y la salida de los tres `mc ls` del paso 6,
   incluyendo el `Access Denied`.

7. **Tres líneas de cierre:**
   - ¿Qué zona borrarías sin perder nada, y cuál no podrías borrar jamás?
   - ¿Dónde vive el PII en tu lake y quién puede leerlo?
   - ¿Qué pasaría si re-procesás curated desde raw con un bug corregido?

### Criterios de corrección

| # | Criterio | Peso |
|---|---|---|
| 1 | Las cuatro zonas existen y el dato fluye de landing a consumer | 20% |
| 2 | Raw en Parquet particionado, con ratio de bytes escaneados medido | 20% |
| 3 | Curated deduplicada, unida con CSV, PII enmascarada, chequeos pasados | 20% |
| 4 | Permisos por zona con `Access Denied` demostrado | 25% |
| 5 | Tabla de administración y decisión de particionado justificada | 15% |

---

## Límites del entorno

- **No hay Lake Formation ni DataZone.** Los permisos son de bucket, no por columna
  ni por fila. Ese salto solo existe en AWS real.
- **El Metastore no es Glue.** No tiene crawlers ni versionado de esquema; las tablas
  se declaran a mano.
- **No hay costo por byte escaneado**, así que el incentivo económico hay que calcularlo
  con los tamaños medidos (Athena cobra $5/TB escaneado).
- Trino corre en un solo nodo. Los tiempos absolutos no son representativos;
  **las diferencias relativas sí**.

### Extensión opcional — Iceberg

Convertí `curated` a formato **Iceberg** y probá operaciones que no existen en Parquet plano:

```sql
-- Agregar columna sin reescribir datos
ALTER TABLE lake.curated.pagos ADD COLUMN canal varchar;

-- Borrar filas (time travel para recuperarlas)
DELETE FROM lake.curated.pagos WHERE pago_id = 1;
SELECT * FROM lake.curated.pagos FOR VERSION AS OF 1;
```

Para esto necesitás un segundo catálogo `iceberg.properties` con `connector.name=iceberg`.
Es la diferencia entre un lake de archivos y un **lakehouse**.

---

## Limpieza

```bash
make down
```

Baja todos los contenedores y borra los volúmenes (incluyendo los datos de MinIO).

---

## Referencias

- Athena pricing (¿cuánto cuesta escanear?): https://aws.amazon.com/athena/pricing/
- Glue Data Catalog vs Hive Metastore: https://docs.aws.amazon.com/glue/latest/dg/aws-glue-api-catalog.html
- Apache Iceberg en Trino: https://trino.io/docs/current/connector/iceberg.html
- Lake Formation column-level security: https://docs.aws.amazon.com/lake-formation/latest/dg/column-level-permissions.html
