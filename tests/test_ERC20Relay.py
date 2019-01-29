import pytest
from eth_tester.exceptions import TransactionFailed


def int_to_address(x):
    return '0x{0:040x}'.format(x)


def test_revert_when_sent_ether(erc20_relay, eth_tester):
    ERC20Relay = erc20_relay.ERC20Relay

    with pytest.raises(TransactionFailed):
        sender = eth_tester.get_accounts()[0]
        eth_tester.send_transaction({'from': sender, 'to': ERC20Relay.address, 'value': 1})


def test_allow_owner_to_set_managers(erc20_relay):
    ERC20Relay = erc20_relay.ERC20Relay

    owner = ERC20Relay.owner
    user = ERC20Relay.users[0]
    verifier_manager = ERC20Relay.verifier_manager
    fee_manager = ERC20Relay.fee_manager

    ERC20Relay.functions.setVerifierManager(verifier_manager.address).transact({'from': owner})
    ERC20Relay.functions.setFeeManager(fee_manager.address).transact({'from': owner})

    with pytest.raises(TransactionFailed):
        ERC20Relay.functions.setVerifierManager(user.address).transact({'from': user.address})

    with pytest.raises(TransactionFailed):
        ERC20Relay.functions.setFeeManager(user.address).transact({'from': user.address})


def test_should_allow_owner_to_perform_management_if_no_manager_set(erc20_relay):
    ERC20Relay = erc20_relay.ERC20Relay

    owner = ERC20Relay.owner
    verifier_manager = ERC20Relay.verifier_manager
    fee_manager = ERC20Relay.fee_manager

    ERC20Relay.functions.addVerifier(int_to_address(1)).transact({'from': owner})
    ERC20Relay.functions.setNctEthExchangeRate(1000).transact({'from': owner})

    ERC20Relay.functions.setVerifierManager(verifier_manager.address).transact({'from': owner})
    with pytest.raises(TransactionFailed):
        ERC20Relay.functions.addVerifier(int_to_address(2)).transact({'from': owner})
    with pytest.raises(TransactionFailed):
        ERC20Relay.functions.removeVerifier(int_to_address(1)).transact({'from': owner})

    ERC20Relay.functions.setFeeManager(fee_manager.address).transact({'from': owner})
    with pytest.raises(TransactionFailed):
        ERC20Relay.functions.setNctEthExchangeRate(2000).transact({'from': owner})
