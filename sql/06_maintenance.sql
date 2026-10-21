SELECT relname, n_live_tup, n_dead_tup,
       last_vacuum, last_autovacuum,
       last_analyze, last_autoanalyze
FROM pg_stat_user_tables
WHERE schemaname = 'query_lab';


UPDATE query_lab.accounts
SET display_name = display_name || ' revised',
    updated_at = now()
WHERE id % 3 = 0;


VACUUM (ANALYZE, VERBOSE) query_lab.accounts;


SELECT pid, state,
       now() - xact_start AS transaction_age,
       wait_event_type, wait_event
FROM pg_stat_activity
WHERE datname = current_database()
  AND (xact_start IS NOT NULL OR backend_xmin IS NOT NULL)
  AND pid <> pg_backend_pid()
ORDER BY xact_start NULLS LAST;


ALTER TABLE query_lab.transactions SET (
    autovacuum_vacuum_scale_factor = 0.005,
    autovacuum_vacuum_threshold = 10000,
    autovacuum_analyze_scale_factor = 0.005,
    autovacuum_analyze_threshold = 10000
);
