-- Zona CONSUMER: agregados diarios por país, para el negocio
-- Sin PII, sin datos crudos — solo métricas pre-computadas

COPY (
  SELECT
    fecha,
    operador_pais                                                         AS pais,
    count(*)                                                              AS pagos,
    sum(monto)                                                            AS monto_total,
    round(
      sum(CASE WHEN estado = 'aprobado' THEN 1.0 ELSE 0.0 END) / count(*),
      4
    )                                                                     AS tasa_aprobacion
  FROM read_parquet('s3://curated/pagos/*/*.parquet')
  GROUP BY fecha, operador_pais
  ORDER BY fecha DESC, pais
) TO 's3://consumer/pagos_diarios.parquet' (FORMAT PARQUET, OVERWRITE_OR_IGNORE TRUE);

-- Preview: últimos 10 días
SELECT *
FROM read_parquet('s3://consumer/pagos_diarios.parquet')
ORDER BY fecha DESC
LIMIT 10;
