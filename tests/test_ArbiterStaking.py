def test_should_be_owned(arbiter_staking):
    assert arbiter_staking.network.address == arbiter_staking.ArbiterStaking.functions.owner().call()
