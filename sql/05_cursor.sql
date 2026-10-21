PREPARE lab_next_page (timestamptz, bigint) AS
SELECT t.id, t.created_at, t.amount_minor, t.status,
       a.display_name
FROM query_lab.transactions AS t
JOIN query_lab.accounts AS a ON a.id = t.account_id
WHERE t.created_at >= timestamptz '2026-01-15 00:00:00+00'
  AND t.created_at <  timestamptz '2026-01-16 00:00:00+00'
  AND t.is_balance_impacted IS TRUE
  AND t.transaction_class
          NOT IN ('Commission', 'Charge', 'StampDuty')
  AND NOT (t.transaction_class = 'Internal'
           AND a.account_type = 'Commission')
  AND (t.created_at, t.id) < ($1, $2)
ORDER BY t.created_at DESC, t.id DESC
LIMIT 1000;
