# Evaluation Baseline v1

Date: 2026-10-27

## Dataset

- Development split: 30 cases, 26 grounded answers and 4 refusals.
- Locked test split: 30 cases, 26 grounded answers and 4 refusals.
- Every grounded citation was checked against its one-based physical PDF page.
- Every grounded citation has a non-empty section path.
- The locked test split was not executed until the development flow was frozen.

## Development Stability

The same code, index, model, prompt, and dataset were used for three complete
runs.

| Run | Passed | Pass rate | Recall@20 | Recall@30 | Final top 6 | Invalid citations | Errors |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| v7 | 30/30 | 100.0% | 100.0% | 100.0% | 100.0% | 0 | 0 |
| v8 | 29/30 | 96.7% | 100.0% | 100.0% | 100.0% | 0 | 0 |
| v9 | 29/30 | 96.7% | 100.0% | 100.0% | 100.0% | 0 | 0 |

Mean development pass rate: 97.8%.

The repeated failure was `huawei_b5_440-005`, which asks how to adjust volume.
The correct manual page presents the operation through keyboard key icons, but
the extracted text contains only action labels such as "减小音量" and
"增大音量". The chunk does not contain the key identity. This is a real chunk
completeness limitation, not a retrieval failure. The case remains in the
dataset and was not changed to hide the defect.

## Locked Test

The locked test was executed once after freezing development.

| Passed | Pass rate | Mode match | Citation hit | Recall@20 | Recall@30 | Final top 6 | Invalid citations | Errors |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 23/30 | 76.7% | 93.3% | 80.8% | 100.0% | 100.0% | 92.3% | 0 | 0 |

Average latency was 7.57 seconds and P95 latency was 19.64 seconds.

All seven failed cases retrieved the expected evidence in the RRF top 20.
Only two failed to place the expected evidence in the final top 6. Therefore,
the main gap in this run is after coarse retrieval: generation behavior,
evidence ordering, and some overly narrow evaluation expectations.

## Failure Review

| Case | Observed issue |
| --- | --- |
| `huawei_c5e_gen4-009` | Correct answer used the synonym "电量图标" while `required_facts` demanded "电池图标". |
| `huawei_b5_440-006` | Answer listed supported devices but did not repeat the interface name "USB-A". |
| `huawei_b5_440-007` | Broad safety question required one specific fact and did not put the preferred safety chunk in the final six. |
| `huawei_hm740-009` | Battery maintenance intent retrieved general power-saving evidence and missed the health-management chunk in the final six. |
| `huawei_b5_341w-006` | The manual states that angle and height can be adjusted but does not give the mechanical method; the case was labeled too optimistically as answerable. |
| `huawei_m272q-008` | Power-safety evidence was retrieved first, but the generator refused. |
| `huawei_m272q-010` | The answer was correct, but cited an alternate supporting page rather than the single page encoded in the expectation. |

## Freeze Rule

Do not modify the v1 locked test after this run and do not use it to tune
prompts, retrieval parameters, or model selection.

The next iteration must create a new development split that addresses:

- synonymous required facts and alternate valid evidence pages;
- broad questions that should not require one narrow fact;
- manual pages whose meaning depends on images or icon labels;
- explicit measurement of whether the generator refuses despite sufficient
  evidence.

The v1 locked test remains the sealed comparison point for that future
iteration.

## Reproduction

```powershell
.\.venv\Scripts\python.exe -m rag_app.eval_main --split dev --output reports\eval-dev-v9.json
.\.venv\Scripts\python.exe -m rag_app.eval_main --split test --output reports\eval-test-v1.json
```
