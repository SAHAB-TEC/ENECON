# RGB Contract Management

Odoo 18 module for **Arabian Nile** contract lifecycle management.

## Features

- Purchase (contractor) and sale (customer) contracts
- Workflow: Draft → Under Approval → Approved → In Progress → Done
- Insurance types, PDF documents, and activation rules
- Performance and bank guarantees with attachments
- Payment conditions, multi-currency values (contract + LYD)
- Delay penalty calculation
- Linked `account.move` invoices with analytic distribution
- Email and activity on approval; cron reminders for guarantee and contract expiry

## Dependencies

- base, mail, account, analytic, purchase, sale_management

**No dependency** on `sdlc_construction_management`.

## Installation

1. Add `Arabian-Nile` to your `addons_path`
2. Update Apps list
3. Install **RGB Contract Management**

## Security groups

| Group | Access |
|-------|--------|
| Contract User | Create/edit contracts, create invoices |
| Contract Approver | Approve contracts |
| Contract Manager | Full access + configuration |

## Usage

1. Mark vendors as **Is Contractor** on the partner form (purchase contracts).
2. Create a contract in **Draft**, set approval responsible, and **Confirm**.
3. Approver **Approve**, then **Start** (requires insurance PDF).
4. **Create Invoice** from the contract; analytic account is applied to lines.

## Technical name

`rgb_contract_management`

Main model: `rgb.contract`
