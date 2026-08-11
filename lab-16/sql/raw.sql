-- Zona RAW: CSV → Parquet tipado, particionado por fecha
-- Lee todos los archivos de landing (cualquier fecha_ingesta)

-- pagos: tipos correctos + partición por fecha
COPY (
  SELECT
    CAST(pago_id   AS BIGINT)        AS pago_id,
    CAST(user_id   AS INTEGER)       AS user_id,
    CAST(monto     AS DECIMAL(12,2)) AS monto,
    moneda,
    operador_id,
    estado,
    CAST(creado_en AS TIMESTAMP)     AS creado_en,
    CAST(creado_en AS DATE)          AS fecha
  FROM read_csv_auto('s3://landing/postgres/pagos/**/*.csv', header=true)
) TO 's3://raw/pagos/' (FORMAT PARQUET, PARTITION_BY (fecha), OVERWRITE_OR_IGNORE TRUE);

-- usuarios: tipos correctos (PII aún visible en raw)
COPY (
  SELECT
    CAST(user_id   AS INTEGER)   AS user_id,
    nombre,
    CAST(documento AS VARCHAR) AS documento,
    email,
    pais,
    CAST(creado_en AS TIMESTAMP) AS creado_en
  FROM read_csv_auto('s3://landing/postgres/usuarios/**/*.csv', header=true)
) TO 's3://raw/usuarios/usuarios.parquet' (FORMAT PARQUET, OVERWRITE_OR_IGNORE TRUE);

SELECT 'raw/pagos ok' AS status UNION ALL SELECT 'raw/usuarios ok';
