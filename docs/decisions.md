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

### 009 — Postgres en docker para dev, RDS en prod

Decision: usar docker postgres del compose para desarrollo local y RDS managed para producción.

Contexto: postgres-on-EC2 nos da el peor de los dos mundos para una app nueva: toda la carga operativa de self-managed, sin las garantías de RDS y sin la simplicidad de docker para dev.

Alternativas: postgres-on-EC2, docker postgres, RDS.

Tradeoff: docker postgres no es producción (sin HA, backups automáticos, ni Multi-AZ). RDS cuesta más, pero reduce la carga operativa y ofrece resiliencia.

Resultado: dev=docker postgres, prod=RDS. Postgres-on-EC2 se descarta salvo que haya requerimientos específicos que justifiquen controlar el SO y el motor.

### 010 — Credencial en Secrets Manager, nunca en el código

Decision: guardar la contraseña de la base en Secrets Manager y leerla en runtime con el rol de la app.

Contexto: credenciales en el código son el vector de incidente más común.

Alternativas: variables de entorno, archivo de configuración, Secrets Manager.

Tradeoff: Secrets Manager añade una dependencia, pero aporta rotación, auditoría y acceso controlado por IAM.

Resultado: secret `app/db` para la credencial de la app. El código no contiene passwords; solo usa el rol y el secret para obtener las credenciales en tiempo de ejecución.
