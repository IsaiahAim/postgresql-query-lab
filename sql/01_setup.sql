CREATE SCHEMA query_lab;

CREATE TABLE query_lab.accounts (
    id bigint PRIMARY KEY,
    display_name text NOT NULL,
    account_type text NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE query_lab.transactions (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    account_id bigint NOT NULL
        REFERENCES query_lab.accounts(id),
    created_at timestamptz NOT NULL,
    amount_minor bigint NOT NULL,
    status text NOT NULL,
    transaction_class text NOT NULL,
    is_balance_impacted boolean NOT NULL,
    reference text NOT NULL
);


INSERT INTO query_lab.accounts
    (id, display_name, account_type)
SELECT
    n,
    'Demo Account ' || n,
    CASE WHEN n % 20 = 0
         THEN 'Commission' ELSE 'Customer' END
FROM generate_series(1, 10000) AS g(n);


INSERT INTO query_lab.transactions (
    account_id, created_at, amount_minor, status,
    transaction_class, is_balance_impacted, reference
)
SELECT
    1 + ((hashtextextended(n::text, 11) & 9223372036854775807) % 10000),
    timestamptz '2026-01-01 00:00:00+00'
        + ((n % 30)::int * interval '1 day')
        + ((((n - 1) / 300) % 86400)::int * interval '1 second'),
    100 + ((n * 7919) % 1000000),
    CASE WHEN n % 9 = 0 THEN 'Pending' ELSE 'Successful' END,
    CASE n % 7
        WHEN 0 THEN 'Commission'
        WHEN 1 THEN 'Charge'
        WHEN 2 THEN 'StampDuty'
        WHEN 3 THEN 'Internal'
        ELSE 'Transfer'
    END,
    (hashtextextended(n::text, 23) & 9223372036854775807) % 5 <> 0,
    'LAB-' || n
FROM generate_series(1::bigint, 1000000::bigint) AS g(n);

ANALYZE query_lab.accounts;
ANALYZE query_lab.transactions;


CREATE INDEX lab_transactions_created_at_idx
ON query_lab.transactions (created_at);
