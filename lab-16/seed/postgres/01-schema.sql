-- ── Schema ────────────────────────────────────────────────────────────────────

CREATE TABLE usuarios (
  user_id   int PRIMARY KEY,
  nombre    text NOT NULL,
  documento text NOT NULL,   -- PII: CUIL/DNI, se enmascara en curated
  email     text NOT NULL,   -- PII, se enmascara en curated
  pais      text NOT NULL,
  creado_en timestamptz NOT NULL
);

CREATE TABLE pagos (
  pago_id     bigint PRIMARY KEY,
  user_id     int NOT NULL REFERENCES usuarios(user_id),
  monto       numeric(12,2) NOT NULL,
  moneda      text NOT NULL,
  operador_id text NOT NULL,
  estado      text NOT NULL CHECK (estado IN ('aprobado','rechazado','pendiente')),
  creado_en   timestamptz NOT NULL
);

-- ── Datos de ejemplo ─────────────────────────────────────────────────────────

INSERT INTO usuarios (user_id, nombre, documento, email, pais, creado_en)
SELECT
  i,
  'Usuario ' || i,
  '20' || lpad(i::text, 7, '0') || '3',
  'user' || i || '@example.com',
  CASE (i % 3)
    WHEN 0 THEN 'AR'
    WHEN 1 THEN 'MX'
    ELSE        'CO'
  END,
  NOW() - ((random() * 365)::int || ' days')::interval
FROM generate_series(1, 200) i;

-- ~200k pagos distribuidos en los últimos 60 días
-- operador_id referencia OP001..OP010 (los que están en el CSV sin suciedad)
INSERT INTO pagos (pago_id, user_id, monto, moneda, operador_id, estado, creado_en)
SELECT
  i                                                   AS pago_id,
  ((i % 200) + 1)                                    AS user_id,
  round((random() * 9900 + 100)::numeric, 2)         AS monto,
  CASE (i % 3)
    WHEN 0 THEN 'ARS'
    WHEN 1 THEN 'MXN'
    ELSE        'COP'
  END                                                  AS moneda,
  'OP' || lpad(((i % 10) + 1)::text, 3, '0')         AS operador_id,
  CASE
    WHEN random() < 0.72 THEN 'aprobado'
    WHEN random() < 0.55 THEN 'rechazado'
    ELSE                      'pendiente'
  END                                                  AS estado,
  -- distribuidos en 60 días para que el partition pruning sea visible
  NOW() - ((random() * 60)::int || ' days')::interval
       - ((random() * 23)::int || ' hours')::interval AS creado_en
FROM generate_series(1, 200000) i;

-- índice mínimo para que el COPY no sea dolorosamente lento
CREATE INDEX pagos_creado_en_idx ON pagos (creado_en);
