-- Zona CURATED: dedup, join, tipado final, PII enmascarada
-- Problemas que resuelve:
--   - pagos duplicados: queda la fila más reciente por pago_id
--   - operadores: dedup por operador_id + COALESCE en comisión vacía (OP003)
--   - PII: documento y email enmascarados

COPY (
  SELECT
    p.pago_id,
    p.user_id,
    p.monto,
    p.moneda,
    p.estado,
    o.nombre       AS operador,
    o.tipo         AS operador_tipo,
    o.pais         AS operador_pais,
    o.comision_pct,
    u.documento_masked,
    u.email_masked,
    p.creado_en,
    p.fecha
  FROM (
    -- pagos: dedup por pago_id, queda la fila más reciente
    SELECT * EXCLUDE (rn)
    FROM (
      SELECT *,
        row_number() OVER (PARTITION BY pago_id ORDER BY creado_en DESC) AS rn
      FROM read_parquet('s3://raw/pagos/*/*.parquet', hive_partitioning=true)
    )
    WHERE rn = 1
      AND monto > 0
  ) p
  JOIN (
    -- operadores: dedup por operador_id + normaliza pais + COALESCE comision
    SELECT
      operador_id,
      ANY_VALUE(nombre)                                           AS nombre,
      ANY_VALUE(tipo)                                             AS tipo,
      upper(ANY_VALUE(pais))                                      AS pais,
      COALESCE(TRY_CAST(ANY_VALUE(comision_pct) AS DOUBLE), 0.0) AS comision_pct
    FROM read_csv(
      's3://landing/externo/operadores/*/operadores.csv',
      header      = true,
      columns     = {'operador_id':'VARCHAR','nombre':'VARCHAR','tipo':'VARCHAR','pais':'VARCHAR','comision_pct':'VARCHAR'},
      ignore_errors = true
    )
    GROUP BY operador_id
  ) o ON o.operador_id = p.operador_id
  JOIN (
    -- usuarios: máscara de PII
    SELECT
      user_id,
      substr(CAST(documento AS VARCHAR), 1, 3) || '***' AS documento_masked,
      regexp_replace(email, '^[^@]+', '***')          AS email_masked
    FROM read_parquet('s3://raw/usuarios/usuarios.parquet')
  ) u ON u.user_id = p.user_id
) TO 's3://curated/pagos/' (FORMAT PARQUET, PARTITION_BY (fecha), OVERWRITE_OR_IGNORE TRUE);

SELECT count(*) AS filas_curated
FROM read_parquet('s3://curated/pagos/*/*.parquet');
