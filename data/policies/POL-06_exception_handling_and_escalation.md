# POL-06 Exception Handling and Escalation
## 1. Exception types
1.1 A business exception is caused by invoice data or policy, for example a missing field or a duplicate.
1.2 A system exception is caused by technology, for example an application timeout or a login failure.
## 2. Business exceptions
2.1 Business exceptions, such as a missing field, an invalid value or a duplicate invoice, must not be retried automatically.
2.2 Business exceptions are returned to the business owner with the reason.
## 3. System exceptions
3.1 System exceptions may be retried at most 2 times, at least 5 minutes apart.
3.2 If the second retry fails, the exception must be escalated.
## 4. Fixes
4.1 A data fix may be proposed automatically but must be approved by a human before it is applied.
4.2 Amounts, vendor details and bank details must never be changed automatically.
## 5. Escalation
5.1 Unknown or repeated failures are escalated to RPA Support L2.
5.2 Failures affecting more than 10 invoices in one hour are priority 1 and escalated immediately.
5.3 Escalations include the invoice ID, failure type, log excerpt and actions already taken.
