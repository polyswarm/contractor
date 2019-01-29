import pytest

from eth_tester.exceptions import TransactionFailed
from eth_utils import to_checksum_address

ZERO_HASH = b'\0' * 32


def int_to_address(x):
    return to_checksum_address('0x{0:040x}'.format(x))


def test_revert_when_sent_ether(erc20_relay, eth_tester):
    ERC20Relay = erc20_relay.ERC20Relay
    network = erc20_relay.network

    with pytest.raises(TransactionFailed):
        sender = eth_tester.get_accounts()[0]
        network.w3.eth.sendTransaction({'from': sender, 'to': ERC20Relay.address, 'value': 1})


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
    ERC20Relay.functions.addVerifier(int_to_address(2)).transact({'from': verifier_manager.address})

    ERC20Relay.functions.setFeeManager(fee_manager.address).transact({'from': owner})
    with pytest.raises(TransactionFailed):
        ERC20Relay.functions.setNctEthExchangeRate(2000).transact({'from': owner})
    ERC20Relay.functions.setNctEthExchangeRate(2000).transact({'from': fee_manager.address})


def test_should_allow_owner_to_add_verifiers(erc20_relay):
    ERC20Relay = erc20_relay.ERC20Relay

    owner = ERC20Relay.owner

    ERC20Relay.functions.addVerifier(int_to_address(1)).transact({'from': owner})


def test_should_allow_owner_to_remove_verifiers(erc20_relay):
    ERC20Relay = erc20_relay.ERC20Relay

    owner = ERC20Relay.owner

    ERC20Relay.functions.addVerifier(int_to_address(1)).transact({'from': owner})
    ERC20Relay.functions.removeVerifier(int_to_address(1)).transact({'from': owner})


def test_should_not_allow_zero_address_as_verifier(erc20_relay):
    ERC20Relay = erc20_relay.ERC20Relay

    owner = ERC20Relay.owner

    with pytest.raises(TransactionFailed):
        ERC20Relay.functions.addVerifier(int_to_address(0)).transact({'from': owner})
    with pytest.raises(TransactionFailed):
        ERC20Relay.functions.removeVerifier(int_to_address(0)).transact({'from': owner})


def test_should_not_allow_adding_duplicate_verifiers(erc20_relay):
    ERC20Relay = erc20_relay.ERC20Relay

    owner = ERC20Relay.owner

    ERC20Relay.functions.addVerifier(int_to_address(1)).transact({'from': owner})
    with pytest.raises(TransactionFailed):
        ERC20Relay.functions.addVerifier(int_to_address(1)).transact({'from': owner})


def test_should_not_allow_removing_non_verifiers(erc20_relay):
    ERC20Relay = erc20_relay.ERC20Relay

    owner = ERC20Relay.owner

    with pytest.raises(TransactionFailed):
        ERC20Relay.functions.removeVerifier(int_to_address(1)).transact({'from': owner})


def test_should_not_allow_removing_verifiers_if_would_drop_below_minimum(erc20_relay):
    ERC20Relay = erc20_relay.ERC20Relay

    owner = ERC20Relay.owner
    verifier = ERC20Relay.verifiers[0]

    with pytest.raises(TransactionFailed):
        ERC20Relay.functions.removeVerifier(verifier.address).transact({'from': owner})


def test_report_active_verifiers(erc20_relay):
    ERC20Relay = erc20_relay.ERC20Relay

    owner = ERC20Relay.owner
    verifiers = {v.address for v in ERC20Relay.verifiers}

    assert set(ERC20Relay.functions.activeVerifiers().call()) == verifiers

    ERC20Relay.functions.addVerifier(int_to_address(1)).transact({'from': owner})
    verifiers.add(int_to_address(1))

    assert set(ERC20Relay.functions.activeVerifiers().call()) == verifiers


def test_report_number_of_verifiers(erc20_relay):
    ERC20Relay = erc20_relay.ERC20Relay

    owner = ERC20Relay.owner
    verifiers = ERC20Relay.verifiers

    for i in range(10):
        assert ERC20Relay.functions.numberOfVerifiers().call() == i + len(verifiers)
        ERC20Relay.functions.addVerifier(int_to_address(i + 1)).transact({'from': owner})


def test_calculate_number_of_needed_votes(erc20_relay):
    ERC20Relay = erc20_relay.ERC20Relay

    owner = ERC20Relay.owner
    verifiers = ERC20Relay.verifiers

    for i in range(10):
        assert ERC20Relay.functions.requiredVerifiers().call() == ((i + len(verifiers)) * 2) // 3
        ERC20Relay.functions.addVerifier(int_to_address(i + 1)).transact({'from': owner})


def test_should_report_if_address_is_a_verifier(erc20_relay):
    ERC20Relay = erc20_relay.ERC20Relay

    owner = ERC20Relay.owner
    verifiers = ERC20Relay.verifiers

    for verifier in verifiers:
        assert ERC20Relay.functions.isVerifier(verifier.address).call()

    for i in range(10):
        ERC20Relay.functions.addVerifier(int_to_address(i + 1)).transact({'from': owner})
        assert ERC20Relay.functions.isVerifier(int_to_address(i + 1)).call()


def test_regression_remove_verifiers(erc20_relay):
    ERC20Relay = erc20_relay.ERC20Relay

    owner = ERC20Relay.owner

    ERC20Relay.functions.addVerifier(int_to_address(1)).transact({'from': owner})
    ERC20Relay.functions.addVerifier(int_to_address(2)).transact({'from': owner})
    ERC20Relay.functions.removeVerifier(int_to_address(1)).transact({'from': owner})
    ERC20Relay.functions.removeVerifier(int_to_address(2)).transact({'from': owner})


def test_should_only_allow_verifiers_to_approve_withdrawals(erc20_relay):
    ERC20Relay = erc20_relay.ERC20Relay

    user = ERC20Relay.users[0]

    with pytest.raises(TransactionFailed):
        ERC20Relay.functions.approveWithdrawal(user.address, 1, ZERO_HASH, ZERO_HASH, 0).transact(
            {'from': user.address})


def test_should_allow_verifiers_to_approve_withdrawals(erc20_relay):
    NectarToken = erc20_relay.NectarToken
    ERC20Relay = erc20_relay.ERC20Relay
    network = erc20_relay.network

    user = ERC20Relay.users[0]
    verifiers = ERC20Relay.verifiers
    fee_wallet = ERC20Relay.fee_wallet

    amount = 1000 * 10 ** 18
    txhash = NectarToken.functions.transfer(ERC20Relay.address, amount).transact({'from': user.address})
    receipt = network.wait_for_transaction(txhash)
    block_hash = receipt.blockHash
    block_number = receipt.blockNumber

    ERC20Relay.functions.approveWithdrawal(user.address, amount, txhash, block_hash, block_number).transact(
        {'from': verifiers[0].address})
    transfer_txhash = ERC20Relay.functions.approveWithdrawal(user.address, amount, txhash, block_hash,
                                                             block_number).transact({'from': verifiers[1].address})
    ERC20Relay.functions.approveWithdrawal(user.address, amount, txhash, block_hash, block_number).transact(
        {'from': verifiers[2].address})

    transfer = network.wait_and_process_receipt(transfer_txhash, NectarToken.events.Transfer())
    assert transfer[0].args['from'] == ERC20Relay.address
    assert transfer[0].args['to'] == fee_wallet.address
    assert transfer[1].args['from'] == ERC20Relay.address
    assert transfer[1].args['to'] == user.address


def test_reject_approvals_of_different_transactions_with_same_hash(erc20_relay):
    ERC20Relay = erc20_relay.ERC20Relay

    user0 = ERC20Relay.users[0]
    user1 = ERC20Relay.users[1]
    verifiers = ERC20Relay.verifiers

    amount = 1000 * 10 ** 18

    ERC20Relay.functions.approveWithdrawal(user0.address, amount, ZERO_HASH, ZERO_HASH, 0).transact(
        {'from': verifiers[0].address})
    with pytest.raises(TransactionFailed):
        ERC20Relay.functions.approveWithdrawal(user0.address, 2 * amount, ZERO_HASH, ZERO_HASH, 0).transact(
            {'from': verifiers[0].address})

    ERC20Relay.functions.approveWithdrawal(user1.address, amount, ZERO_HASH, ZERO_HASH, 1).transact(
        {'from': verifiers[0].address})
    with pytest.raises(TransactionFailed):
        ERC20Relay.functions.approveWithdrawal(user1.address, amount, ZERO_HASH, ZERO_HASH, 1).transact(
            {'from': verifiers[1].address})


def test_reject_approving_multiple_times(erc20_relay):
    NectarToken = erc20_relay.NectarToken
    ERC20Relay = erc20_relay.ERC20Relay
    network = erc20_relay.network

    user = ERC20Relay.users[0]
    verifier = ERC20Relay.verifiers[0]

    amount = 1000 * 10 ** 18
    txhash = NectarToken.functions.transfer(ERC20Relay.address, amount).transact({'from': user.address})
    receipt = network.wait_for_transaction(txhash)
    block_hash = receipt.blockHash
    block_number = receipt.blockNumber

    ERC20Relay.functions.approveWithdrawal(user.address, amount, txhash, block_hash, block_number).transact(
        {'from': verifier.address})
    with pytest.raises(TransactionFailed):
        ERC20Relay.functions.approveWithdrawal(user.address, amount, txhash, block_hash, block_number).transact(
            {'from': verifier.address})


def test_unapprove_withdrawal_non_verifier(erc20_relay):
    NectarToken = erc20_relay.NectarToken
    ERC20Relay = erc20_relay.ERC20Relay
    network = erc20_relay.network

    user = ERC20Relay.users[0]
    verifier = ERC20Relay.verifiers[0]

    amount = 1000 * 10 ** 18
    txhash = NectarToken.functions.transfer(ERC20Relay.address, amount).transact({'from': user.address})
    receipt = network.wait_for_transaction(txhash)
    block_hash = receipt.blockHash
    block_number = receipt.blockNumber

    ERC20Relay.functions.approveWithdrawal(user.address, amount, txhash, block_hash, block_number).transact(
        {'from': verifier.address})
    with pytest.raises(TransactionFailed):
        ERC20Relay.functions.unapproveWithdrawal(txhash, block_hash, block_number).transact({'from': user.address})


def test_unapprove_withdrawal(erc20_relay):
    NectarToken = erc20_relay.NectarToken
    ERC20Relay = erc20_relay.ERC20Relay
    network = erc20_relay.network

    user = ERC20Relay.users[0]
    verifier = ERC20Relay.verifiers[0]

    amount = 1000 * 10 ** 18
    txhash = NectarToken.functions.transfer(ERC20Relay.address, amount).transact({'from': user.address})
    receipt = network.wait_for_transaction(txhash)
    block_hash = receipt.blockHash
    block_number = receipt.blockNumber

    ERC20Relay.functions.approveWithdrawal(user.address, amount, txhash, block_hash, block_number).transact(
        {'from': verifier.address})
    ERC20Relay.functions.unapproveWithdrawal(txhash, block_hash, block_number).transact({'from': verifier.address})


def test_unapprove_non_existent_withdrawal(erc20_relay):
    ERC20Relay = erc20_relay.ERC20Relay

    verifier = ERC20Relay.verifiers[0]

    with pytest.raises(TransactionFailed):
        ERC20Relay.functions.unapproveWithdrawal(ZERO_HASH, ZERO_HASH, 0).transact({'from': verifier.address})


def test_unapprove_processed_withdrawal(erc20_relay):
    NectarToken = erc20_relay.NectarToken
    ERC20Relay = erc20_relay.ERC20Relay
    network = erc20_relay.network

    user = ERC20Relay.users[0]
    verifiers = ERC20Relay.verifiers

    amount = 1000 * 10 ** 18
    txhash = NectarToken.functions.transfer(ERC20Relay.address, amount).transact({'from': user.address})
    receipt = network.wait_for_transaction(txhash)
    block_hash = receipt.blockHash
    block_number = receipt.blockNumber

    ERC20Relay.functions.approveWithdrawal(user.address, amount, txhash, block_hash, block_number).transact(
        {'from': verifiers[0].address})
    ERC20Relay.functions.approveWithdrawal(user.address, amount, txhash, block_hash, block_number).transact(
        {'from': verifiers[1].address})

    with pytest.raises(TransactionFailed):
        ERC20Relay.functions.unapproveWithdrawal(txhash, block_hash, block_number).transact(
            {'from': verifiers[0].address})


def test_regression_reject_withdrawal_less_than_or_equal_to_fees(erc20_relay):
    NectarToken = erc20_relay.NectarToken
    ERC20Relay = erc20_relay.ERC20Relay
    network = erc20_relay.network

    user = ERC20Relay.users[0]
    verifiers = ERC20Relay.verifiers

    amount = ERC20Relay.functions.fees().call()
    txhash = NectarToken.functions.transfer(ERC20Relay.address, amount).transact({'from': user.address})
    receipt = network.wait_for_transaction(txhash)
    block_hash = receipt.blockHash
    block_number = receipt.blockNumber

    with pytest.raises(TransactionFailed):
        ERC20Relay.functions.approveWithdrawal(user.address, amount, txhash, block_hash, block_number).transact(
            {'from': verifiers[0].address})


def test_only_verifiers_can_anchor_blocks(erc20_relay):
    ERC20Relay = erc20_relay.ERC20Relay

    user = ERC20Relay.users[0]

    with pytest.raises(TransactionFailed):
        ERC20Relay.functions.anchor(ZERO_HASH, 0).transact({'from': user.address})


def test_verifiers_should_be_allowed_to_anchor_blocks(erc20_relay):
    ERC20Relay = erc20_relay.ERC20Relay
    network = erc20_relay.network

    verifiers = ERC20Relay.verifiers

    ERC20Relay.functions.anchor(ZERO_HASH, 0).transact({'from': verifiers[0].address})
    txhash = ERC20Relay.functions.anchor(ZERO_HASH, 0).transact({'from': verifiers[1].address})
    ERC20Relay.functions.anchor(ZERO_HASH, 0).transact({'from': verifiers[2].address})

    anchor = network.wait_and_process_receipt(txhash, ERC20Relay.events.AnchoredBlock())
    assert anchor[0].args['blockHash'] == ZERO_HASH
    assert anchor[0].args['blockNumber'] == 0


def test_reject_multiple_anchors(erc20_relay):
    ERC20Relay = erc20_relay.ERC20Relay

    verifier = ERC20Relay.verifiers[0]

    ERC20Relay.functions.anchor(ZERO_HASH, 0).transact({'from': verifier.address})
    with pytest.raises(TransactionFailed):
        ERC20Relay.functions.anchor(ZERO_HASH, 0).transact({'from': verifier.address})


def test_contested_block(erc20_relay):
    ERC20Relay = erc20_relay.ERC20Relay
    network = erc20_relay.network

    verifier = ERC20Relay.verifiers[0]

    ERC20Relay.functions.anchor(ZERO_HASH, 0).transact({'from': verifier.address})
    txhash = ERC20Relay.functions.anchor(ZERO_HASH, 1).transact({'from': verifier.address})

    contested = network.wait_and_process_receipt(txhash, ERC20Relay.events.ContestedBlock())
    assert contested[0].args['blockHash'] == ZERO_HASH
    assert contested[0].args['blockNumber'] == 0


def test_not_contested_if_processed(erc20_relay):
    ERC20Relay = erc20_relay.ERC20Relay
    network = erc20_relay.network

    verifiers = ERC20Relay.verifiers

    ERC20Relay.functions.anchor(ZERO_HASH, 0).transact({'from': verifiers[0].address})
    ERC20Relay.functions.anchor(ZERO_HASH, 0).transact({'from': verifiers[1].address})
    ERC20Relay.functions.anchor(ZERO_HASH, 0).transact({'from': verifiers[2].address})

    txhash = ERC20Relay.functions.anchor(ZERO_HASH, 1).transact({'from': verifiers[0].address})
    contested = network.wait_and_process_receipt(txhash, ERC20Relay.events.ContestedBlock())

    assert len(contested) == 0


def test_verifier_can_unanchor(erc20_relay):
    ERC20Relay = erc20_relay.ERC20Relay

    verifier = ERC20Relay.verifiers[0]

    ERC20Relay.functions.anchor(ZERO_HASH, 0).transact({'from': verifier.address})
    ERC20Relay.functions.unanchor().transact({'from': verifier.address})


def test_cannot_unanchor_processed_blocks(erc20_relay):
    ERC20Relay = erc20_relay.ERC20Relay

    verifiers = ERC20Relay.verifiers

    ERC20Relay.functions.anchor(ZERO_HASH, 0).transact({'from': verifiers[0].address})
    ERC20Relay.functions.anchor(ZERO_HASH, 0).transact({'from': verifiers[1].address})
    ERC20Relay.functions.anchor(ZERO_HASH, 0).transact({'from': verifiers[2].address})

    with pytest.raises(TransactionFailed):
        ERC20Relay.functions.unanchor().transact({'from': verifiers[0].address})
