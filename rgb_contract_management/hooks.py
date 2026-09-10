# -*- coding: utf-8 -*-


def post_init_hook(env):
    """Migrate legacy USD/LYD percentage fields to currency split lines."""
    _migrate_contract_currency_split(env)
    _migrate_invoice_currency_split(env)


def _migrate_contract_currency_split(env):
    Contract = env['rgb.contract'].sudo()
    Split = env['rgb.contract.currency.split'].sudo()
    usd = env.ref('base.USD', raise_if_not_found=False)
    lyd = env.ref('base.LYD', raise_if_not_found=False)

    for contract in Contract.search([]):
        if Split.search_count([('contract_id', '=', contract.id)]):
            continue

        lines = []
        sequence = 10
        total = 0.0

        if usd and contract.dollar_percentage:
            lines.append({
                'sequence': sequence,
                'currency_id': usd.id,
                'percentage': contract.dollar_percentage,
            })
            total += contract.dollar_percentage
            sequence += 10

        if lyd and contract.libya_dinar_percentage:
            lines.append({
                'sequence': sequence,
                'currency_id': lyd.id,
                'percentage': contract.libya_dinar_percentage,
            })
            total += contract.libya_dinar_percentage
            sequence += 10

        if lines and total < 100.0 and contract.currency_id:
            remainder = 100.0 - total
            if remainder > 0.0001:
                existing_currency_ids = {line['currency_id'] for line in lines}
                if contract.currency_id.id not in existing_currency_ids:
                    lines.append({
                        'sequence': sequence,
                        'currency_id': contract.currency_id.id,
                        'percentage': remainder,
                    })

        if lines:
            Split.create([dict(line, contract_id=contract.id) for line in lines])


def _migrate_invoice_currency_split(env):
    Move = env['account.move'].sudo()
    Split = env['rgb.account.move.currency.split'].sudo()
    usd = env.ref('base.USD', raise_if_not_found=False)
    lyd = env.ref('base.LYD', raise_if_not_found=False)

    for move in Move.search([('contract_id', '!=', False)]):
        if Split.search_count([('move_id', '=', move.id)]):
            continue

        lines = []
        sequence = 10
        total = 0.0

        if usd and move.dollar_percentage:
            lines.append({
                'sequence': sequence,
                'currency_id': usd.id,
                'percentage': move.dollar_percentage,
            })
            total += move.dollar_percentage
            sequence += 10

        if lyd and move.libya_dinar_percentage:
            lines.append({
                'sequence': sequence,
                'currency_id': lyd.id,
                'percentage': move.libya_dinar_percentage,
            })
            total += move.libya_dinar_percentage
            sequence += 10

        if not lines and move.contract_id.currency_split_ids:
            for split_line in move.contract_id.currency_split_ids:
                lines.append({
                    'sequence': split_line.sequence,
                    'currency_id': split_line.currency_id.id,
                    'percentage': split_line.percentage,
                })
        elif lines and total < 100.0 and move.currency_id:
            remainder = 100.0 - total
            if remainder > 0.0001:
                existing_currency_ids = {line['currency_id'] for line in lines}
                if move.currency_id.id not in existing_currency_ids:
                    lines.append({
                        'sequence': sequence,
                        'currency_id': move.currency_id.id,
                        'percentage': remainder,
                    })

        if lines:
            Split.create([dict(line, move_id=move.id) for line in lines])
