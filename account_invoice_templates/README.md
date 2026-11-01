# Account Invoice Templates

Custom PDF invoice layouts for Arabian Nile (Akakos, Waha A/B, Gulf, Gulf Transport).

## Depends

- `account`
- `rgb_contract_management` (contract field on invoices + form inheritance)

## Features

- Extra fields on invoices and lines used by QWeb reports only (no sale pricelist logic).
- Print actions on **Accounting → Invoices** (PDF Akakos, Waha A/B, Gulf, Gulf Transport).
- When a **Contract** is selected on an invoice, template header fields are prefilled from the contract.

## Install

1. Install `rgb_contract_management`
2. Install `account_invoice_templates`
3. Mark task stages as **Global Stage** is unrelated — configure **Task Stages** under Project if you use global stages elsewhere.

## Reports

| Report | Use |
|--------|-----|
| PDF Akakos | Line no. + Abarios code + bank footer + extra info block |
| PDF Waha A | + Total USD share |
| PDF Waha B | + Total LYD share |
| PDF Gulf | USD + LYD shares |
| PDF Gulf Transport | Weight / payload columns + 15% desert charge |

Fill **USD %** / **LYD %** on the invoice before printing Waha/Gulf variants.
