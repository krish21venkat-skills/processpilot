# POL-07 Audit and Retention
## 1. Audit log content
1.1 Every automated decision must be logged with a timestamp, invoice ID, decision and cited policy sections.
1.2 Every human approval is logged with approver ID, role and timestamp.
1.3 Every bot action and retry is logged with its outcome.
## 2. Retention
2.1 Invoice records and audit logs are retained for 8 years.
2.2 Bot execution logs are retained for 1 year.
## 3. Access
3.1 Audit logs are read-only for all users, including administrators.
3.2 Audit log access by auditors is granted on request and recorded.
