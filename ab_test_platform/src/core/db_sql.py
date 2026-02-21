"""
SQL-строки для создания материализованного представления и хранимых функций.
Выполняются один раз при старте сервиса через init_data.create_tables_and_mv().

Примечание: SQLAlchemy/SQLModel маппит Python str -> VARCHAR в PostgreSQL,
поэтому все строковые колонки из MV кастуются ::text чтобы соответствовать
объявлению RETURNS TABLE(... TEXT).
"""

# ---------------------------------------------------------------------------
# Materialized view: денормализованные события для построения метрик
# ---------------------------------------------------------------------------

SQL_CREATE_MV = """
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_events_enriched AS
SELECT
    e.id,
    e.occurred_at,
    e.subject_id,
    e.payload,
    e.decision_id,
    et.type          AS event_type_key,
    d.experiment_id,
    d.variant_id,
    v.name           AS variant_name,
    v.value          AS variant_value,
    v.is_control
FROM events e
JOIN event_types et ON e.event_type_id = et.id
JOIN decisions   d  ON e.decision_id   = d.id
JOIN variants    v  ON d.variant_id    = v.id
WITH NO DATA;
"""

SQL_CREATE_IDX_EXPERIMENT_TYPE_TIME = """
CREATE INDEX IF NOT EXISTS idx_mv_events_exp_type_time
    ON mv_events_enriched(experiment_id, event_type_key, occurred_at);
"""

SQL_CREATE_IDX_EXPERIMENT_VARIANT = """
CREATE INDEX IF NOT EXISTS idx_mv_events_exp_variant
    ON mv_events_enriched(experiment_id, variant_id);
"""

SQL_REFRESH_MV = "REFRESH MATERIALIZED VIEW mv_events_enriched;"

# ---------------------------------------------------------------------------
# fn_metric_summary
# Возвращает агрегированное значение метрики по вариантам эксперимента.
# Колонки: variant_id, variant_name, is_control, value, value_num, value_denom
#   value      — финальное значение (ratio если есть знаменатель, иначе числитель)
#   value_num  — сырой числитель (для подсчёта корректных итогов в Python)
#   value_denom — знаменатель (NULL если метрика не дробная)
# ---------------------------------------------------------------------------

SQL_CREATE_FN_METRIC_SUMMARY = """
CREATE OR REPLACE FUNCTION fn_metric_summary(
    p_experiment_id TEXT,
    p_metric_key    TEXT,
    p_date_from     TIMESTAMPTZ,
    p_date_to       TIMESTAMPTZ
)
RETURNS TABLE(
    variant_id   TEXT,
    variant_name TEXT,
    is_control   BOOLEAN,
    value        NUMERIC,
    value_num    NUMERIC,
    value_denom  NUMERIC
)
LANGUAGE plpgsql AS $$
DECLARE
    v_event_type       TEXT;
    v_aggregation      TEXT;
    v_payload_field    TEXT;
    v_denom_event_type TEXT;
    v_denom_agg        TEXT;
    v_num_expr         TEXT;
    v_denom_expr       TEXT;
    v_sql              TEXT;
BEGIN
    SELECT m.event_type, m.aggregation, m.payload_field,
           m.denominator_event_type, m.denominator_aggregation
    INTO   v_event_type, v_aggregation, v_payload_field,
           v_denom_event_type, v_denom_agg
    FROM metrics m
    JOIN experiment_metrics em ON em.metric_id = m.id
    WHERE em.experiment_id = p_experiment_id
      AND m.key = p_metric_key
    LIMIT 1;

    IF NOT FOUND THEN
        RETURN;
    END IF;

    v_num_expr := CASE v_aggregation
        WHEN 'COUNT'        THEN 'count(e.id)::numeric'
        WHEN 'COUNT_UNIQUE' THEN 'count(distinct e.subject_id)::numeric'
        WHEN 'SUM'          THEN format('sum((e.payload->>%L)::numeric)', v_payload_field)
        WHEN 'AVG'          THEN format('avg((e.payload->>%L)::numeric)', v_payload_field)
        ELSE                     'count(e.id)::numeric'
    END;

    IF v_denom_event_type IS NOT NULL THEN
        v_denom_expr := CASE v_denom_agg
            WHEN 'COUNT'        THEN 'count(d.id)::numeric'
            WHEN 'COUNT_UNIQUE' THEN 'count(distinct d.subject_id)::numeric'
            ELSE                     'count(d.id)::numeric'
        END;

        v_sql := format(
            'SELECT
                n.variant_id::text,
                n.variant_name::text,
                n.is_control,
                CASE WHEN d.denom_val > 0
                     THEN n.num_val / d.denom_val
                     ELSE NULL
                END                       AS value,
                n.num_val                 AS value_num,
                d.denom_val               AS value_denom
             FROM (
                 SELECT e.variant_id::text, e.variant_name::text, e.is_control,
                        %s AS num_val
                 FROM mv_events_enriched e
                 WHERE e.experiment_id = %L
                   AND e.event_type_key = %L
                   AND e.occurred_at BETWEEN %L AND %L
                 GROUP BY e.variant_id, e.variant_name, e.is_control
             ) n
             LEFT JOIN (
                 SELECT d.variant_id::text,
                        %s AS denom_val
                 FROM mv_events_enriched d
                 WHERE d.experiment_id = %L
                   AND d.event_type_key = %L
                   AND d.occurred_at BETWEEN %L AND %L
                 GROUP BY d.variant_id
             ) d ON n.variant_id = d.variant_id',
            v_num_expr,
            p_experiment_id, v_event_type, p_date_from, p_date_to,
            v_denom_expr,
            p_experiment_id, v_denom_event_type, p_date_from, p_date_to
        );
    ELSE
        v_sql := format(
            'SELECT
                e.variant_id::text,
                e.variant_name::text,
                e.is_control,
                %s            AS value,
                %s            AS value_num,
                NULL::numeric AS value_denom
             FROM mv_events_enriched e
             WHERE e.experiment_id = %L
               AND e.event_type_key = %L
               AND e.occurred_at BETWEEN %L AND %L
             GROUP BY e.variant_id, e.variant_name, e.is_control',
            v_num_expr, v_num_expr,
            p_experiment_id, v_event_type, p_date_from, p_date_to
        );
    END IF;

    RETURN QUERY EXECUTE v_sql;
END;
$$;
"""

# ---------------------------------------------------------------------------
# fn_metric_timeseries
# Возвращает метрику по временны́м бакетам для каждого варианта.
# Колонки: variant_id, variant_name, is_control, bucket_start, bucket_end, value
# ---------------------------------------------------------------------------

SQL_CREATE_FN_METRIC_TIMESERIES = """
CREATE OR REPLACE FUNCTION fn_metric_timeseries(
    p_experiment_id TEXT,
    p_metric_key    TEXT,
    p_date_from     TIMESTAMPTZ,
    p_date_to       TIMESTAMPTZ,
    p_granularity   TEXT
)
RETURNS TABLE(
    variant_id   TEXT,
    variant_name TEXT,
    is_control   BOOLEAN,
    bucket_start TIMESTAMPTZ,
    bucket_end   TIMESTAMPTZ,
    value        NUMERIC
)
LANGUAGE plpgsql AS $$
DECLARE
    v_event_type       TEXT;
    v_aggregation      TEXT;
    v_payload_field    TEXT;
    v_denom_event_type TEXT;
    v_denom_agg        TEXT;
    v_num_expr         TEXT;
    v_denom_expr       TEXT;
    v_interval         TEXT;
    v_sql              TEXT;
BEGIN
    SELECT m.event_type, m.aggregation, m.payload_field,
           m.denominator_event_type, m.denominator_aggregation
    INTO   v_event_type, v_aggregation, v_payload_field,
           v_denom_event_type, v_denom_agg
    FROM metrics m
    JOIN experiment_metrics em ON em.metric_id = m.id
    WHERE em.experiment_id = p_experiment_id
      AND m.key = p_metric_key
    LIMIT 1;

    IF NOT FOUND THEN
        RETURN;
    END IF;

    v_interval := CASE p_granularity
        WHEN 'minute' THEN '1 minute'
        WHEN 'hour'   THEN '1 hour'
        WHEN 'day'    THEN '1 day'
        ELSE               '1 hour'
    END;

    v_num_expr := CASE v_aggregation
        WHEN 'COUNT'        THEN 'count(e.id)::numeric'
        WHEN 'COUNT_UNIQUE' THEN 'count(distinct e.subject_id)::numeric'
        WHEN 'SUM'          THEN format('sum((e.payload->>%L)::numeric)', v_payload_field)
        WHEN 'AVG'          THEN format('avg((e.payload->>%L)::numeric)', v_payload_field)
        ELSE                     'count(e.id)::numeric'
    END;

    IF v_denom_event_type IS NOT NULL THEN
        v_denom_expr := CASE v_denom_agg
            WHEN 'COUNT'        THEN 'count(d.id)::numeric'
            WHEN 'COUNT_UNIQUE' THEN 'count(distinct d.subject_id)::numeric'
            ELSE                     'count(d.id)::numeric'
        END;

        v_sql := format(
            'SELECT
                n.variant_id::text,
                n.variant_name::text,
                n.is_control,
                n.bucket_start,
                n.bucket_start + %L::interval AS bucket_end,
                CASE WHEN d.denom_val > 0
                     THEN n.num_val / d.denom_val
                     ELSE NULL
                END AS value
             FROM (
                 SELECT e.variant_id::text, e.variant_name::text, e.is_control,
                        date_trunc(%L, e.occurred_at) AS bucket_start,
                        %s AS num_val
                 FROM mv_events_enriched e
                 WHERE e.experiment_id = %L
                   AND e.event_type_key = %L
                   AND e.occurred_at BETWEEN %L AND %L
                 GROUP BY e.variant_id, e.variant_name, e.is_control,
                          date_trunc(%L, e.occurred_at)
             ) n
             LEFT JOIN (
                 SELECT d.variant_id::text,
                        date_trunc(%L, d.occurred_at) AS bucket_start,
                        %s AS denom_val
                 FROM mv_events_enriched d
                 WHERE d.experiment_id = %L
                   AND d.event_type_key = %L
                   AND d.occurred_at BETWEEN %L AND %L
                 GROUP BY d.variant_id,
                          date_trunc(%L, d.occurred_at)
             ) d ON n.variant_id = d.variant_id
                AND n.bucket_start = d.bucket_start
             ORDER BY n.variant_id, n.bucket_start',
            v_interval,
            p_granularity, v_num_expr,
            p_experiment_id, v_event_type, p_date_from, p_date_to,
            p_granularity,
            p_granularity, v_denom_expr,
            p_experiment_id, v_denom_event_type, p_date_from, p_date_to,
            p_granularity
        );
    ELSE
        v_sql := format(
            'SELECT
                e.variant_id::text,
                e.variant_name::text,
                e.is_control,
                date_trunc(%L, e.occurred_at)                AS bucket_start,
                date_trunc(%L, e.occurred_at) + %L::interval AS bucket_end,
                %s                                           AS value
             FROM mv_events_enriched e
             WHERE e.experiment_id = %L
               AND e.event_type_key = %L
               AND e.occurred_at BETWEEN %L AND %L
             GROUP BY e.variant_id, e.variant_name, e.is_control,
                      date_trunc(%L, e.occurred_at)
             ORDER BY e.variant_id, date_trunc(%L, e.occurred_at)',
            p_granularity, p_granularity, v_interval,
            v_num_expr,
            p_experiment_id, v_event_type, p_date_from, p_date_to,
            p_granularity, p_granularity
        );
    END IF;

    RETURN QUERY EXECUTE v_sql;
END;
$$;
"""
