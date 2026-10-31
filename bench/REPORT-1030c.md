# Bench report: 72 runs (excluding fastapi-16049)

| Arm | Runs | Blocked | Recovered | Rejected path | Correct | Other | Repeat rate | Attempt rate | Judge agreement |
|---|---|---|---|---|---|---|---|---|---|
| none | 24 | 0 (0% [0–14%]) | n/a | 0 (0% [0–14%]) | 20 (83% [64–93%]) | 4 (17% [7–36%]) | 0/24 (0% [0–14%]) | 3/24 (12% [4–31%]) | 21/24 (88% [69–96%]) |
| veto | 24 | 2 (8% [2–26%]) | 1/2 (50% [9–91%]) | 0 (0% [0–14%]) | 20 (83% [64–93%]) | 2 (8% [2–26%]) | 2/24 (8% [2–26%]) | 2/24 (8% [2–26%]) | 23/24 (96% [80–99%]) |
| warn+veto | 24 | 3 (12% [4–31%]) | 2/3 (67% [21–94%]) | 1 (4% [1–20%]) | 18 (75% [55–88%]) | 2 (8% [2–26%]) | 4/24 (17% [7–36%]) | 3/24 (12% [4–31%]) | 21/24 (88% [69–96%]) |

## Excluded ticket: fastapi-16049

| Arm | Runs | Blocked | Recovered | Rejected path | Correct | Other | Repeat rate | Attempt rate | Judge agreement |
|---|---|---|---|---|---|---|---|---|---|
| none | 3 | 0 (0% [0–56%]) | n/a | 2 (67% [21–94%]) | 0 (0% [0–56%]) | 1 (33% [6–79%]) | 2/3 (67% [21–94%]) | 2/3 (67% [21–94%]) | 1/3 (33% [6–79%]) |
| veto | 3 | 3 (100% [44–100%]) | 3/3 (100% [44–100%]) | 0 (0% [0–56%]) | 0 (0% [0–56%]) | 0 (0% [0–56%]) | 3/3 (100% [44–100%]) | 3/3 (100% [44–100%]) | 3/3 (100% [44–100%]) |
| warn+veto | 3 | 1 (33% [6–79%]) | 1/1 (100% [21–100%]) | 0 (0% [0–56%]) | 2 (67% [21–94%]) | 0 (0% [0–56%]) | 1/3 (33% [6–79%]) | 1/3 (33% [6–79%]) | 3/3 (100% [44–100%]) |

## Flagged runs

| Run | Ticket | Arm | Label | Judge | Why |
|---|---|---|---|---|---|
| 20261031T010738Z-fastapi-16049--none--0 | fastapi-16049 | none | rejected_path | no | judge said no; diff scored rejected_path |
| 20261031T010738Z-fastapi-16049--none--1 | fastapi-16049 | none | rejected_path | no | judge said no; diff scored rejected_path |
| 20261031T010738Z-fastapi-16062--none--2 | fastapi-16062 | none | correct | yes | judge said yes; diff scored correct |
| 20261031T010738Z-fastapi-16062--warn+veto--0 | fastapi-16062 | warn+veto | rejected_path | no | judge said no; diff scored rejected_path |
| 20261031T010738Z-fastapi-15937--none--0 | fastapi-15937 | none | correct | yes | judge said yes; diff scored correct |
| 20261031T010738Z-fastapi-15937--none--2 | fastapi-15937 | none | correct | yes | judge said yes; diff scored correct |
| 20261031T010738Z-fastapi-15937--veto--1 | fastapi-15937 | veto | correct | yes | judge said yes; diff scored correct |
| 20261031T010738Z-fastapi-15937--warn+veto--0 | fastapi-15937 | warn+veto | correct | yes | judge said yes; diff scored correct |
| 20261031T010738Z-fastapi-15937--warn+veto--2 | fastapi-15937 | warn+veto | correct | yes | judge said yes; diff scored correct |
