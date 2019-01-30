import pytest
from eth_tester.exceptions import TransactionFailed


def test_should_be_owned(arbiter_staking):
    ArbiterStaking = arbiter_staking.ArbiterStaking

    assert ArbiterStaking.functions.owner().call() == ArbiterStaking.owner


def test_should_be_pausable(arbiter_staking):
    NectarToken = arbiter_staking.NectarToken
    ArbiterStaking = arbiter_staking.ArbiterStaking
    network = arbiter_staking.network

    ArbiterStaking.functions.pause().transact({'from': ArbiterStaking.owner})
    assert ArbiterStaking.functions.paused().call()

    with pytest.raises(TransactionFailed):
        ArbiterStaking.functions.deposit(1).transact({'from': ArbiterStaking.arbiter.address})

    ArbiterStaking.functions.unpause().transact({'from': ArbiterStaking.owner})
    NectarToken.functions.approve(ArbiterStaking.address, 1).transact({'from': ArbiterStaking.arbiter.address})

    txhash = ArbiterStaking.functions.deposit(1).transact({'from': ArbiterStaking.arbiter.address})
    deposit = network.wait_and_process_receipt(txhash, ArbiterStaking.events.NewDeposit())
    assert deposit[0].args['from'] == ArbiterStaking.arbiter.address
    assert deposit[0].args['value'] == 1


def test_should_allow_deposits(arbiter_staking):
    NectarToken = arbiter_staking.NectarToken
    ArbiterStaking = arbiter_staking.ArbiterStaking
    network = arbiter_staking.network

    NectarToken.functions.approve(ArbiterStaking.address, 1).transact({'from': ArbiterStaking.arbiter.address})
    txhash = ArbiterStaking.functions.deposit(1).transact({'from': ArbiterStaking.arbiter.address})
    deposit = network.wait_and_process_receipt(txhash, ArbiterStaking.events.NewDeposit())
    assert deposit[0].args['from'] == ArbiterStaking.arbiter.address
    assert deposit[0].args['value'] == 1


def test_should_update_balance(arbiter_staking):
    NectarToken = arbiter_staking.NectarToken
    ArbiterStaking = arbiter_staking.ArbiterStaking
    network = arbiter_staking.network

    NectarToken.functions.approve(ArbiterStaking.address, 1).transact({'from': ArbiterStaking.arbiter.address})
    txhash = ArbiterStaking.functions.deposit(1).transact({'from': ArbiterStaking.arbiter.address})
    deposit = network.wait_and_process_receipt(txhash, ArbiterStaking.events.NewDeposit())
    assert deposit[0].args['from'] == ArbiterStaking.arbiter.address
    assert deposit[0].args['value'] == 1

    assert ArbiterStaking.functions.balanceOf(ArbiterStaking.arbiter.address).call() == 1


def test_update_withdrawable_balance(arbiter_staking, eth_tester):
    NectarToken = arbiter_staking.NectarToken
    ArbiterStaking = arbiter_staking.ArbiterStaking
    network = arbiter_staking.network

    NectarToken.functions.approve(ArbiterStaking.address, 1).transact({'from': ArbiterStaking.arbiter.address})
    txhash = ArbiterStaking.functions.deposit(1).transact({'from': ArbiterStaking.arbiter.address})
    deposit = network.wait_and_process_receipt(txhash, ArbiterStaking.events.NewDeposit())
    assert deposit[0].args['from'] == ArbiterStaking.arbiter.address
    assert deposit[0].args['value'] == 1

    eth_tester.mine_blocks(10)

    NectarToken.functions.approve(ArbiterStaking.address, 1).transact({'from': ArbiterStaking.arbiter.address})
    txhash = ArbiterStaking.functions.deposit(1).transact({'from': ArbiterStaking.arbiter.address})
    deposit = network.wait_and_process_receipt(txhash, ArbiterStaking.events.NewDeposit())
    assert deposit[0].args['from'] == ArbiterStaking.arbiter.address
    assert deposit[0].args['value'] == 1

    assert ArbiterStaking.functions.balanceOf(ArbiterStaking.arbiter.address).call() == 2
    assert ArbiterStaking.functions.withdrawableBalanceOf(ArbiterStaking.arbiter.address).call() == 0

    eth_tester.mine_blocks(ArbiterStaking.stake_duration - 10)
    assert ArbiterStaking.functions.withdrawableBalanceOf(ArbiterStaking.arbiter.address).call() == 1

    eth_tester.mine_blocks(10)
    assert ArbiterStaking.functions.withdrawableBalanceOf(ArbiterStaking.arbiter.address).call() == 2


def test_return_0_when_block_less_than_staking_duration(arbiter_staking):
    NectarToken = arbiter_staking.NectarToken
    ArbiterStaking = arbiter_staking.ArbiterStaking
    network = arbiter_staking.network

    NectarToken.functions.approve(ArbiterStaking.address, 1).transact({'from': ArbiterStaking.arbiter.address})
    txhash = ArbiterStaking.functions.deposit(1).transact({'from': ArbiterStaking.arbiter.address})
    deposit = network.wait_and_process_receipt(txhash, ArbiterStaking.events.NewDeposit())
    assert deposit[0].args['from'] == ArbiterStaking.arbiter.address
    assert deposit[0].args['value'] == 1

    assert ArbiterStaking.functions.withdrawableBalanceOf(ArbiterStaking.arbiter.address).call() == 0


def test_reject_deposit_over_max_staking(arbiter_staking):
    NectarToken = arbiter_staking.NectarToken
    ArbiterStaking = arbiter_staking.ArbiterStaking

    NectarToken.functions.approve(ArbiterStaking.address, 1).transact({'from': ArbiterStaking.arbiter.address})
    ArbiterStaking.functions.deposit(1).transact({'from': ArbiterStaking.arbiter.address})
    assert ArbiterStaking.functions.balanceOf(ArbiterStaking.arbiter.address).call() == 1

    amount = 100000000 * 10 ** 18
    NectarToken.functions.approve(ArbiterStaking.address, amount).transact({'from': ArbiterStaking.arbiter.address})
    with pytest.raises(TransactionFailed):
        ArbiterStaking.functions.deposit(amount).transact({'from': ArbiterStaking.arbiter.address})


def test_reject_deposit_from_non_arbiter(arbiter_staking):
    NectarToken = arbiter_staking.NectarToken
    BountyRegistry = arbiter_staking.BountyRegistry
    ArbiterStaking = arbiter_staking.ArbiterStaking
    network = arbiter_staking.network

    BountyRegistry.functions.removeArbiter(ArbiterStaking.arbiter.address, network.block_number()).transact(
        {'from': ArbiterStaking.owner})

    NectarToken.functions.approve(ArbiterStaking.address, 1).transact({'from': ArbiterStaking.arbiter.address})
    with pytest.raises(TransactionFailed):
        ArbiterStaking.functions.deposit(1).transact({'from': ArbiterStaking.arbiter.address})


def test_reject_withdrawal_with_no_deposits(arbiter_staking):
    ArbiterStaking = arbiter_staking.ArbiterStaking

    with pytest.raises(TransactionFailed):
        ArbiterStaking.functions.withdraw(1).transact({'from': ArbiterStaking.arbiter.address})


def test_allow_withdrawals_after_staking_time(arbiter_staking, eth_tester):
    NectarToken = arbiter_staking.NectarToken
    ArbiterStaking = arbiter_staking.ArbiterStaking
    network = arbiter_staking.network

    NectarToken.functions.approve(ArbiterStaking.address, 1).transact({'from': ArbiterStaking.arbiter.address})
    txhash = ArbiterStaking.functions.deposit(1).transact({'from': ArbiterStaking.arbiter.address})
    deposit = network.wait_and_process_receipt(txhash, ArbiterStaking.events.NewDeposit())
    assert deposit[0].args['from'] == ArbiterStaking.arbiter.address
    assert deposit[0].args['value'] == 1

    assert ArbiterStaking.functions.balanceOf(ArbiterStaking.arbiter.address).call() == 1
    assert ArbiterStaking.functions.withdrawableBalanceOf(ArbiterStaking.arbiter.address).call() == 0

    with pytest.raises(TransactionFailed):
        ArbiterStaking.functions.withdraw(1).transact({'from': ArbiterStaking.arbiter.address})

    eth_tester.mine_blocks(ArbiterStaking.stake_duration)

    assert ArbiterStaking.functions.balanceOf(ArbiterStaking.arbiter.address).call() == 1
    assert ArbiterStaking.functions.withdrawableBalanceOf(ArbiterStaking.arbiter.address).call() == 1

    txhash = ArbiterStaking.functions.withdraw(1).transact({'from': ArbiterStaking.arbiter.address})
    withdrawal = network.wait_and_process_receipt(txhash, ArbiterStaking.events.NewWithdrawal())
    assert withdrawal[0].args['to'] == ArbiterStaking.arbiter.address
    assert withdrawal[0].args['value'] == 1

    assert ArbiterStaking.functions.balanceOf(ArbiterStaking.arbiter.address).call() == 0
    assert ArbiterStaking.functions.withdrawableBalanceOf(ArbiterStaking.arbiter.address).call() == 0


def test_allow_combinations_of_deposits_and_withdrawals(arbiter_staking, eth_tester):
    NectarToken = arbiter_staking.NectarToken
    ArbiterStaking = arbiter_staking.ArbiterStaking

    def deposit(amount):
        NectarToken.functions.approve(ArbiterStaking.address, amount).transact({'from': ArbiterStaking.arbiter.address})
        return ArbiterStaking.functions.deposit(amount).transact({'from': ArbiterStaking.arbiter.address})

    def withdraw(amount):
        return ArbiterStaking.functions.withdraw(amount).transact({'from': ArbiterStaking.arbiter.address})

    def check_balances(balance, withdrawable_balance):
        assert ArbiterStaking.functions.balanceOf(ArbiterStaking.arbiter.address).call() == balance
        assert ArbiterStaking.functions.withdrawableBalanceOf(
            ArbiterStaking.arbiter.address).call() == withdrawable_balance

    check_balances(0, 0)

    deposit(10)
    eth_tester.mine_blocks(8)
    deposit(20)
    eth_tester.mine_blocks(8)
    deposit(30)
    eth_tester.mine_blocks(8)
    deposit(40)
    eth_tester.mine_blocks(8)

    check_balances(100, 0)

    eth_tester.mine_blocks(ArbiterStaking.stake_duration - 35)

    check_balances(100, 10)

    with pytest.raises(TransactionFailed):
        withdraw(20)
    withdraw(5)
    with pytest.raises(TransactionFailed):
        withdraw(10)
    withdraw(3)

    eth_tester.mine_blocks(10)

    with pytest.raises(TransactionFailed):
        withdraw(25)
    withdraw(22)

    eth_tester.mine_blocks(10)

    withdraw(30)

    eth_tester.mine_blocks(10)

    withdraw(15)

    check_balances(25, 25)


def test_eligible_arbiters_before_bounty_record(arbiter_staking):
    NectarToken = arbiter_staking.NectarToken
    ArbiterStaking = arbiter_staking.ArbiterStaking
    network = arbiter_staking.network

    assert not ArbiterStaking.functions.isEligible(ArbiterStaking.arbiter.address).call()

    amount = 10000000 * 10 ** 18
    NectarToken.functions.approve(ArbiterStaking.address, amount).transact({'from': ArbiterStaking.arbiter.address})
    txhash = ArbiterStaking.functions.deposit(amount).transact({'from': ArbiterStaking.arbiter.address})
    deposit = network.wait_and_process_receipt(txhash, ArbiterStaking.events.NewDeposit())
    assert deposit[0].args['from'] == ArbiterStaking.arbiter.address
    assert deposit[0].args['value'] == amount

    assert ArbiterStaking.functions.isEligible(ArbiterStaking.arbiter.address).call()


def test_eligible_arbiters_after_bounty_record(arbiter_staking):
    NectarToken = arbiter_staking.NectarToken
    ArbiterStaking = arbiter_staking.ArbiterStaking
    network = arbiter_staking.network

    assert not ArbiterStaking.functions.isEligible(ArbiterStaking.arbiter.address).call()

    amount = 10000000 * 10 ** 18
    NectarToken.functions.approve(ArbiterStaking.address, amount).transact({'from': ArbiterStaking.arbiter.address})
    txhash = ArbiterStaking.functions.deposit(amount).transact({'from': ArbiterStaking.arbiter.address})
    deposit = network.wait_and_process_receipt(txhash, ArbiterStaking.events.NewDeposit())
    assert deposit[0].args['from'] == ArbiterStaking.arbiter.address
    assert deposit[0].args['value'] == amount

    assert ArbiterStaking.functions.isEligible(ArbiterStaking.arbiter.address).call()

    # Set this to owner so we can call recordBounty directly
    ArbiterStaking.functions.setBountyRegistry(ArbiterStaking.owner).transact({'from': ArbiterStaking.owner})

    for i in range(9):
        ArbiterStaking.functions.recordBounty(ArbiterStaking.arbiter.address, i + 1, network.block_number()).transact(
            {'from': ArbiterStaking.owner})

    ArbiterStaking.functions.recordBounty(ArbiterStaking.owner, 10, network.block_number()).transact(
        {'from': ArbiterStaking.owner})

    assert ArbiterStaking.functions.isEligible(ArbiterStaking.arbiter.address).call()

    ArbiterStaking.functions.recordBounty(ArbiterStaking.owner, 11, network.block_number()).transact(
        {'from': ArbiterStaking.owner})

    assert not ArbiterStaking.functions.isEligible(ArbiterStaking.arbiter.address).call()
