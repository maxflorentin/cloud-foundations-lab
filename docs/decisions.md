# Decision log

## Formato

```text
Decision:
Contexto:
Alternativas:
Tradeoff:
Resultado:
```

## Decisiones

### 001 - Laboratorios locales

Decision: usar Docker Compose, MinIO y LocalStack en lugar de cuentas AWS personales.

Contexto: evitar costos accidentales y reducir friccion de setup.

Tradeoff: no se practica consola AWS real en profundidad.

Resultado: los labs son reproducibles y reutilizables.

### 003 - Formato de eventos crudos

Decision: JSONL (JSON Lines) para data/raw/events.jsonl.

Contexto: los eventos se generan uno por vez. JSONL permite procesar con streaming
sin cargar todo el archivo en memoria, y es fácil de appender.

Alternativas: JSON array, CSV, Parquet.

Tradeoff: JSONL no es legible de un vistazo como un JSON array formateado.
Parquet sería más eficiente a escala, pero requiere dependencias externas.

Resultado: JSONL para raw. CSV para processed (compatibilidad analítica máxima).

### 004 - Pipeline de procesamiento

Decision: script Python (process_events.py) lee JSONL y escribe JSON filtrado.

Contexto: necesitamos filtrar un subconjunto de eventos GitHub Archive para análisis.
El script es reproducible: misma entrada, misma salida, sin efectos secundarios.

Tradeoff: un script por transformación vs una sola función general.
Elegimos un script por transformación: más legible, más fácil de testear.

Resultado: process_events.py → data/processed/push_events.json (filtra PushEvent)

### 002 - Entorno de desarrollo

Decision: GitHub Codespaces.

Contexto: el grupo no tiene instalaciones homogéneas (mix de macOS, Windows y Linux).
Codespaces ofrece el mismo entorno para todos sin configuración local.

Alternativas: Docker Desktop local, WSL2, máquina virtual.

Tradeoff: depende de conectividad y de los free-tier hours disponibles (60 hs/mes por cuenta).
Con Docker local se trabaja offline y sin límite de tiempo.

Resultado: Codespaces para las clases, Docker local como fallback documentado en el README.
### 005 - Identidad y credenciales en el lab

Decision: Usar roles con STS en lugar de access keys de larga duracion para acceso entre servicios.

Contexto: Las access keys no expiran y si se filtran dan acceso indefinido. Los roles con STS generan credenciales temporales (15 minutos a 12 horas) con trazabilidad.

Alternativas:
- Access keys rotadas manualmente
- Usar un vault o secret manager

Tradeoff: Asumir un rol requiere que el servicio tenga permiso de sts:AssumeRole y que el rol tenga un trust policy correcto. Implica mas configuracion inicial, pero reduce el riesgo de forma significativa.

Resultado: Se creo app-role con una politica de privilegio minimo (solo lectura) sobre el bucket course-data-raw. Comprobamos que las credenciales generadas por STS expiran automaticamente, a diferencia de la access key fija creada para lab-user.

Nota adicional: en LocalStack Community, un Deny explicito no bloquea las llamadas (lo verificamos en la practica). En AWS real, el Deny explicito siempre tiene prioridad sobre cualquier Allow.