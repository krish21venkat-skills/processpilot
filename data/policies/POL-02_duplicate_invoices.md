# POL-02 Duplicate Invoice Rules
## 1. Definition
1.1 An exact duplicate has the same vendor ID and the same invoice number as an earlier invoice.
1.2 A suspected duplicate has the same vendor, the same amount and an invoice date within 90 days of an earlier invoice, but a different invoice number.
## 2. Handling
2.1 Exact duplicates must be rejected and must not be processed or paid.
2.2 Suspected duplicates must be placed on hold for AP Manager review.
2.3 The reviewer records the decision and reason in the audit log.
## 3. Credit notes
3.1 A credit note must reference the original invoice number.
3.2 A credit note is never treated as a duplicate of the original invoice.
