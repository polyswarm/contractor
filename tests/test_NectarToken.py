import pytest
from eth_tester.exceptions import TransactionFailed

USER_STARTING_BALANCE = 3000000 * 10 ** 18
ARBITER_STARTING_BALANCE = 50000000 * 10 ** 18


def test_mint(nectar_token):
    NectarToken = nectar_token.NectarToken

    for user in NectarToken.users:
        assert NectarToken.functions.balanceOf(user.address).call() == USER_STARTING_BALANCE

    for arbiter in NectarToken.arbiters:
        assert NectarToken.functions.balanceOf(arbiter.address).call() == ARBITER_STARTING_BALANCE


def test_transfer(nectar_token):
    NectarToken = nectar_token.NectarToken

    sender = NectarToken.users[0]
    receiver = NectarToken.users[1]

    NectarToken.functions.transfer(receiver.address, USER_STARTING_BALANCE).transact({'from': sender.address})
    assert NectarToken.functions.balanceOf(receiver.address).call() == 2 * USER_STARTING_BALANCE
    assert NectarToken.functions.balanceOf(sender.address).call() == 0
