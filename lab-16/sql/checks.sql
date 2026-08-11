-- Chequeos de calidad sobre la zona curated

-- 1. Duplicados de pago_id (debe ser 0)
SELECT '1_duplicados' AS check,
  count(*) - count(DISTINCT pago_id) AS valor
FROM read_parquet('s3://curated/pagos/*/*.parquet');

-- 2. Nulos en campos críticos (debe ser 0)
SELECT '2_nulos_criticos' AS check,
  count(*) AS valor
FROM read_parquet('s3://curated/pagos/*/*.parquet')
WHERE operador IS NULL OR operador_pais IS NULL;

-- 3. Montos fuera de rango (debe ser 0)
SELECT '3_monto_invalido' AS check,
  count(*) AS valor
FROM read_parquet('s3://curated/pagos/*/*.parquet')
WHERE monto <= 0;

-- 4. Frescura del dato
SELECT '4_frescura' AS check,
  max(fecha)            AS ultima_fecha,
  min(fecha)            AS primera_fecha,
  count(DISTINCT fecha) AS dias
FROM read_parquet('s3://curated/pagos/*/*.parquet');
