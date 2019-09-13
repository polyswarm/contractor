from contractor.deployer import camel_case_to_snake_case, snake_case_to_camel_case


def test_camel_case_to_snake_case():
    assert camel_case_to_snake_case('ArbiterStaking') == 'arbiter_staking'
    assert camel_case_to_snake_case('BountyRegistry') == 'bounty_registry'
    assert camel_case_to_snake_case('ERC20Relay') == 'erc20_relay'
    assert camel_case_to_snake_case('NectarToken') == 'nectar_token'
    assert camel_case_to_snake_case('OfferRegistry') == 'offer_registry'


def test_snake_case_to_camel_case():
    assert snake_case_to_camel_case('arbiter_staking') == 'ArbiterStaking'
    assert snake_case_to_camel_case('bounty_registry') == 'BountyRegistry'
    assert snake_case_to_camel_case('erc20_relay') == 'ERC20Relay'
    assert snake_case_to_camel_case('nectar_token') == 'NectarToken'
    assert snake_case_to_camel_case('offer_registry') == 'OfferRegistry'
