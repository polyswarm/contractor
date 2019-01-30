def test_mint(nectar_token):
    NectarToken = nectar_token.NectarToken

    amount = 1000000000 * 10 ** 18
    for user in NectarToken.users:
        assert NectarToken.functions.balanceOf(user.address).call() == amount


def test_transfer(nectar_token):
    NectarToken = nectar_token.NectarToken

    amount = 1000000000 * 10 ** 18
    sender = NectarToken.users[0]
    receiver = NectarToken.users[1]

    NectarToken.functions.transfer(receiver.address, amount).transact({'from': sender.address})
    assert NectarToken.functions.balanceOf(receiver.address).call() == 2 * amount
    assert NectarToken.functions.balanceOf(sender.address).call() == 0
