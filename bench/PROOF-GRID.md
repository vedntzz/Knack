# Proof grid

Every installed rule against each gate a rule must pass before it guards.
PASS and FAIL come from the committed record of this exact rule text: the proof stored
in its registry entry (`knack reprove` or install), or a compile-log attempt whose rule
is byte-identical to the installed file. Held-out is scored again from data/heldout.
NOT RUN means the input the gate needs does not exist; each is listed below with why.
Tier is what the guard does on a new match today: block (a Confirmed root,
pinned to this rule or confirmed before pins existed) or warn (anything else).

| Decision | Roots | Tier | base | head | 0 FP tree | 0 FP release | rename | variants | compliant | held-out | Evidence |
|---|---|---|---|---|---|---|---|---|---|---|---|
| apache/airflow #74150 | airflow-74150-1 | warn | PASS | PASS | PASS | PASS | FAIL | FAIL | PASS | FAIL | knack reprove 2026-10-31 |
| apache/airflow #75025 | airflow-75025-1 | block | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | knack reprove 2026-10-31 |
| apache/airflow #75271 | airflow-75271-1, airflow-75271-2 | warn | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | knack reprove 2026-10-31 |
| apache/airflow #75734 | airflow-75734-1 | warn | PASS | PASS | PASS | PASS | PASS | FAIL | PASS | FAIL | knack reprove 2026-10-31 |
| apache/airflow #75774 | airflow-75774-1, airflow-75774-2 | block | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | knack reprove 2026-10-31 |
| fastapi/fastapi #14884 | fastapi-14884-1 | warn | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | knack reprove 2026-10-31 |
| fastapi/fastapi #15139 | fastapi-15139-1 | warn | PASS | PASS | PASS | PASS | PASS | PASS | PASS | FAIL | knack reprove 2026-10-31 |
| fastapi/fastapi #15515 | fastapi-15515-1, fastapi-15515-2 | warn | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | knack reprove 2026-10-31 |
| fastapi/fastapi #15937 | fastapi-15937-1 | warn | PASS | PASS | PASS | PASS | PASS | PASS | PASS | FAIL | knack reprove 2026-10-31 |
| fastapi/fastapi #15967 | fastapi-15967-1 | warn | PASS | PASS | PASS | PASS | PASS | PASS | PASS | FAIL | knack reprove 2026-10-31 |
| fastapi/fastapi #16049 | fastapi-16049-1 | warn | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | knack reprove 2026-10-31 |
| fastapi/fastapi #16062 | fastapi-16062-1 | warn | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | knack reprove 2026-10-31 |

base: 12 PASS, 0 FAIL, 0 NOT RUN
head: 12 PASS, 0 FAIL, 0 NOT RUN
0 FP tree: 12 PASS, 0 FAIL, 0 NOT RUN
0 FP release: 12 PASS, 0 FAIL, 0 NOT RUN
rename: 11 PASS, 1 FAIL, 0 NOT RUN
variants: 10 PASS, 2 FAIL, 0 NOT RUN
compliant: 12 PASS, 0 FAIL, 0 NOT RUN
held-out: 7 PASS, 5 FAIL, 0 NOT RUN

NOT RUN, and the input that does not exist:
- none

Decisions with no installed rule (never block or warn): airflow-75734-2, airflow-75774-3, fastapi-15139-2, fastapi-15937-2, fastapi-15937-3, fastapi-15937-4, fastapi-15967-2
