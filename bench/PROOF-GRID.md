# Proof grid

Every installed rule against each gate a rule must pass before it guards.
PASS and FAIL come from the committed record of this exact rule text: its install proof,
or a compile-log attempt whose rule is byte-identical to the installed file.
NOT RUN means no committed record shows that gate on this rule.
Tier is what the guard does on a new match today: block (a Confirmed root,
pinned to this rule or confirmed before pins existed) or warn (anything else).

| Decision | Roots | Tier | base | head | 0 FP tree | 0 FP release | rename | variants | compliant | held-out | Evidence |
|---|---|---|---|---|---|---|---|---|---|---|---|
| apache/airflow #74150 | airflow-74150-1 | warn | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | FAIL | none |
| apache/airflow #75025 | airflow-75025-1 | block | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | PASS | none |
| apache/airflow #75271 | airflow-75271-1, airflow-75271-2 | warn | PASS | PASS | PASS | NOT RUN | PASS | PASS | PASS | PASS | compile_run5_airflow.log #75271 attempt 5 |
| apache/airflow #75734 | airflow-75734-1 | warn | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | FAIL | none |
| apache/airflow #75774 | airflow-75774-1, airflow-75774-2 | block | PASS | PASS | PASS | NOT RUN | PASS | PASS | PASS | PASS | compile_run5_airflow.log #75774 attempt 3 |
| fastapi/fastapi #14884 | fastapi-14884-1 | warn | PASS | PASS | PASS | NOT RUN | PASS | PASS | PASS | PASS | compile_run5_fastapi.log #14884 attempt 2 |
| fastapi/fastapi #15139 | fastapi-15139-1 | warn | PASS | PASS | PASS | NOT RUN | PASS | PASS | PASS | FAIL | compile_run5_rerun_15139.log #15139 attempt 3 |
| fastapi/fastapi #15515 | fastapi-15515-1, fastapi-15515-2 | warn | PASS | PASS | PASS | NOT RUN | PASS | PASS | PASS | PASS | compile_run5_fastapi.log #15515 attempt 4 |
| fastapi/fastapi #15937 | fastapi-15937-1 | warn | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | FAIL | none |
| fastapi/fastapi #15967 | fastapi-15967-1 | warn | PASS | PASS | PASS | NOT RUN | PASS | PASS | PASS | FAIL | compile_run5_fastapi.log #15967 attempt 3 |
| fastapi/fastapi #16049 | fastapi-16049-1 | warn | PASS | PASS | PASS | NOT RUN | PASS | PASS | PASS | PASS | compile_run5_fastapi.log #16049 attempt 1 |
| fastapi/fastapi #16062 | fastapi-16062-1 | warn | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | PASS | none |

base: 7 PASS, 0 FAIL, 5 NOT RUN
head: 7 PASS, 0 FAIL, 5 NOT RUN
0 FP tree: 7 PASS, 0 FAIL, 5 NOT RUN
0 FP release: 0 PASS, 0 FAIL, 12 NOT RUN
rename: 7 PASS, 0 FAIL, 5 NOT RUN
variants: 7 PASS, 0 FAIL, 5 NOT RUN
compliant: 7 PASS, 0 FAIL, 5 NOT RUN
held-out: 7 PASS, 5 FAIL, 0 NOT RUN

Decisions with no installed rule (never block or warn): airflow-75734-2, airflow-75774-3, fastapi-15139-2, fastapi-15937-2, fastapi-15937-3, fastapi-15937-4, fastapi-15967-2
