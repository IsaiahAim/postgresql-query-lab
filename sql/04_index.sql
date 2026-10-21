CREATE INDEX lab_transactions_feed_idx
ON query_lab.transactions (created_at DESC, id DESC)
WHERE is_balance_impacted IS TRUE
  AND transaction_class
          NOT IN ('Commission', 'Charge', 'StampDuty');

ANALYZE query_lab.transactions;
