# Publishing package

Suggested title: Before 500 Million Rows: Fix the PostgreSQL Query That Already Does Too Much Work

Subtitle: A reproducible guide to date filters, execution plans, partial indexes, and cursor pagination - with measured results from one million transactions.

The revised article is in `article.md`. Four PNGs under `assets/` correspond to Figures 1-4 in the Markdown. Keep their captions: they identify the measured dataset and distinguish saved-output screenshots from a live SQL-client capture.

Place each SQL block in a code block in your Medium draft. Upload the corresponding PNG at each image marker and retain its caption. Keep the results table as text or use the results screenshot if table formatting is inconvenient. Add your hosted companion-project link once you choose where to publish the ZIP or repository; no public URL has been created by this task.

Suggested tags: PostgreSQL, SQL, Database, Performance, Backend Development.

Do not describe this as a completed 500-million-row benchmark. The recorded capacity check stopped that load; the actual query results come from one million rows. Replace the scale section only after a larger run produces a verified row count and saved plans.
