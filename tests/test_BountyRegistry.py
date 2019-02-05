import uuid
import os
import random

import pytest
from eth_tester.exceptions import TransactionFailed
from ethereum.utils import sha3

STARTING_BALANCE = 1000000000 * 10 ** 18
ZERO_ADDRESS = '0x0000000000000000000000000000000000000000'


def random_guid():
    return int(uuid.uuid4())


def random_artifact_uri():
    return 'foo'


def random_bloom():
    return [0] * 8


def random_nonce():
    # Zero is an invalid nonce
    n = b'\0' * 32
    while int_from_bytes(n) == 0:
        n = os.urandom(32)

    return n


def bool_list_to_int(bs):
    return sum([1 << n if b else 0 for n, b in enumerate(bs)])


def int_to_bool_list(i):
    s = format(i, 'b')
    return [x == '1' for x in s[::-1]]


def post_bounty(bounty_registry, ambassador, **kwargs):
    NectarToken = bounty_registry.NectarToken
    BountyRegistry = bounty_registry.BountyRegistry

    args = {
        'guid': random_guid(),
        'uri': random_artifact_uri(),
        'bloom': random_bloom(),
        'amount': 10 * 10 ** 18,
        'num_artifacts': 1,
        'duration': 10,
    }
    args.update(**kwargs)

    bounty_fee = BountyRegistry.functions.bountyFee().call()
    NectarToken.functions.approve(BountyRegistry.address, args['amount'] + bounty_fee).transact({'from': ambassador})
    return args['guid'], BountyRegistry.functions.postBounty(args['guid'], args['amount'], args['uri'],
                                                             args['num_artifacts'], args['duration'],
                                                             args['bloom']).transact({'from': ambassador})


def int_to_bytes(i):
    h = hex(i)[2:]
    return bytes.fromhex('0' * (64 - len(h)) + h)


def int_from_bytes(b):
    return int.from_bytes(b, byteorder='big')


def calculate_commitment(account, verdicts):
    nonce = random_nonce()
    account = int(account, 16)
    commitment = sha3(int_to_bytes(verdicts ^ int_from_bytes(sha3(nonce)) ^ account))
    return int_from_bytes(nonce), int_from_bytes(commitment)


def post_assertion(bounty_registry, expert, bounty_guid, **kwargs):
    NectarToken = bounty_registry.NectarToken
    BountyRegistry = bounty_registry.BountyRegistry
    network = bounty_registry.network

    args = {
        'bid': 10 * 10 ** 18,
        'mask': 0,
        'verdicts': 0,
    }
    args.update(**kwargs)

    if not isinstance(args['mask'], int):
        args['mask'] = bool_list_to_int(args['mask'])

    if not isinstance(args['verdicts'], int):
        args['verdicts'] = bool_list_to_int(args['verdicts'])

    nonce, commitment = calculate_commitment(expert, args['verdicts'])

    assertion_fee = BountyRegistry.functions.assertionFee().call()
    NectarToken.functions.approve(BountyRegistry.address, args['bid'] + assertion_fee).transact({'from': expert})
    txhash = BountyRegistry.functions.postAssertion(bounty_guid, args['bid'], args['mask'], commitment).transact(
        {'from': expert})
    assertion = network.wait_and_process_receipt(txhash, BountyRegistry.events.NewAssertion())
    index = assertion[0].args['index']

    return index, nonce, txhash


def reveal_assertion(bounty_registry, expert, bounty_guid, index, nonce, verdicts, metadata):
    BountyRegistry = bounty_registry.BountyRegistry

    if not isinstance(verdicts, int):
        verdicts = bool_list_to_int(verdicts)

    return BountyRegistry.functions.revealAssertion(bounty_guid, index, nonce, verdicts, metadata).transact(
        {'from': expert})


def vote_on_bounty(bounty_registry, arbiter, bounty_guid, votes, validBloom=True):
    BountyRegistry = bounty_registry.BountyRegistry

    if not isinstance(votes, int):
        votes = bool_list_to_int(votes)

    return BountyRegistry.functions.voteOnBounty(bounty_guid, votes, validBloom).transact({'from': arbiter})


def settle_bounty(bounty_registry, settler, bounty_guid):
    BountyRegistry = bounty_registry.BountyRegistry
    return BountyRegistry.functions.settleBounty(bounty_guid).transact({'from': settler})


def test_bool_list_int_conversion():
    for _ in range(100):
        x = int_from_bytes(os.urandom(32))
        assert bool_list_to_int(int_to_bool_list(x)) == x


def test_allow_owner_to_set_fee_manager(bounty_registry):
    BountyRegistry = bounty_registry.BountyRegistry

    owner = BountyRegistry.owner
    user = BountyRegistry.ambassadors[0]
    fee_manager = BountyRegistry.fee_manager

    BountyRegistry.functions.setFeeManager(fee_manager.address).transact({'from': owner})

    with pytest.raises(TransactionFailed):
        BountyRegistry.functions.setFeeManager(user.address).transact({'from': user.address})


def test_should_allow_owner_to_perform_management_if_no_manager_set(bounty_registry):
    BountyRegistry = bounty_registry.BountyRegistry

    owner = BountyRegistry.owner
    fee_manager = BountyRegistry.fee_manager

    BountyRegistry.functions.setBountyFee(1).transact({'from': owner})
    BountyRegistry.functions.setAssertionFee(1).transact({'from': owner})

    BountyRegistry.functions.setFeeManager(fee_manager.address).transact({'from': owner})
    with pytest.raises(TransactionFailed):
        BountyRegistry.functions.setBountyFee(2).transact({'from': owner})
    with pytest.raises(TransactionFailed):
        BountyRegistry.functions.setAssertionFee(2).transact({'from': owner})

    BountyRegistry.functions.setBountyFee(1).transact({'from': fee_manager.address})
    BountyRegistry.functions.setAssertionFee(1).transact({'from': fee_manager.address})


def test_post_bounty(bounty_registry):
    NectarToken = bounty_registry.NectarToken
    BountyRegistry = bounty_registry.BountyRegistry
    network = bounty_registry.network

    ambassador = BountyRegistry.ambassadors[0]
    guid = random_guid()
    uri = random_artifact_uri()
    amount = 10 * 10 ** 18

    bounty_fee = BountyRegistry.functions.bountyFee().call()

    _, txhash = post_bounty(bounty_registry, ambassador.address, guid=guid, uri=uri, amount=amount)
    bounty = network.wait_and_process_receipt(txhash, BountyRegistry.events.NewBounty())
    assert bounty[0].args['guid'] == guid
    assert bounty[0].args['author'] == ambassador.address
    assert bounty[0].args['artifactURI'] == uri
    assert bounty[0].args['amount'] == amount

    assert NectarToken.functions.balanceOf(ambassador.address).call() == STARTING_BALANCE - bounty_fee - amount
    assert BountyRegistry.functions.getNumberOfBounties().call() == 1
    assert BountyRegistry.functions.bountiesByGuid(guid).call()[0] == guid


def test_reject_duplicate_guids(bounty_registry):
    BountyRegistry = bounty_registry.BountyRegistry

    ambassador = BountyRegistry.ambassadors[0]

    guid, _ = post_bounty(bounty_registry, ambassador.address)
    with pytest.raises(TransactionFailed):
        post_bounty(bounty_registry, ambassador.address, guid=guid)


def test_reject_amounts_below_minimum(bounty_registry):
    BountyRegistry = bounty_registry.BountyRegistry

    ambassador = BountyRegistry.ambassadors[0]
    amount = int(0.05 * 10 ** 18)

    with pytest.raises(TransactionFailed):
        post_bounty(bounty_registry, ambassador.address, amount=amount)


def test_reject_empty_uris(bounty_registry):
    BountyRegistry = bounty_registry.BountyRegistry

    ambassador = BountyRegistry.ambassadors[0]

    with pytest.raises(TransactionFailed):
        post_bounty(bounty_registry, ambassador.address, uri='')


def test_reject_zero_duration_bounties(bounty_registry):
    BountyRegistry = bounty_registry.BountyRegistry

    ambassador = BountyRegistry.ambassadors[0]

    with pytest.raises(TransactionFailed):
        post_bounty(bounty_registry, ambassador.address, duration=0)


def test_reject_too_long_duration_bounties(bounty_registry):
    BountyRegistry = bounty_registry.BountyRegistry

    ambassador = BountyRegistry.ambassadors[0]
    max_duration = BountyRegistry.functions.MAX_DURATION().call()

    with pytest.raises(TransactionFailed):
        post_bounty(bounty_registry, ambassador.address, duration=max_duration + 1)


def test_reject_too_large_bounties(bounty_registry):
    BountyRegistry = bounty_registry.BountyRegistry

    ambassador = BountyRegistry.ambassadors[0]

    with pytest.raises(TransactionFailed):
        post_bounty(bounty_registry, ambassador.address, amount=STARTING_BALANCE)


def test_reject_zero_artifact_bounties(bounty_registry):
    BountyRegistry = bounty_registry.BountyRegistry

    ambassador = BountyRegistry.ambassadors[0]

    with pytest.raises(TransactionFailed):
        post_bounty(bounty_registry, ambassador.address, num_artifacts=0)


def test_bounty_round_reporting(bounty_registry, eth_tester):
    BountyRegistry = bounty_registry.BountyRegistry

    ambassador = BountyRegistry.ambassadors[0]
    expert0 = BountyRegistry.experts[0]
    expert1 = BountyRegistry.experts[1]
    arbiters = BountyRegistry.arbiters
    duration = 10

    assertion_reveal_window = BountyRegistry.functions.ASSERTION_REVEAL_WINDOW().call()
    arbiter_vote_window = BountyRegistry.arbiter_vote_window

    guid, _ = post_bounty(bounty_registry, ambassador.address, num_artifacts=2, duration=duration)
    assert BountyRegistry.functions.getCurrentRound(guid).call() == 0

    index0, nonce0, _ = post_assertion(bounty_registry, expert0.address, guid, mask=[True, True],
                                       verdicts=[False, False])
    index1, nonce1, _ = post_assertion(bounty_registry, expert1.address, guid, mask=[True, True],
                                       verdicts=[False, True])

    eth_tester.mine_blocks(duration)
    assert BountyRegistry.functions.getCurrentRound(guid).call() == 1

    reveal_assertion(bounty_registry, expert0.address, guid, index0, nonce0, [False, False], 'foo')
    reveal_assertion(bounty_registry, expert1.address, guid, index1, nonce1, [False, True], 'bar')

    eth_tester.mine_blocks(assertion_reveal_window)
    assert BountyRegistry.functions.getCurrentRound(guid).call() == 2

    for arbiter in arbiters:
        vote_on_bounty(bounty_registry, arbiter.address, guid, [False, True])

    eth_tester.mine_blocks(arbiter_vote_window)
    assert BountyRegistry.functions.getCurrentRound(guid).call() == 3


def test_post_assertions(bounty_registry, eth_tester):
    NectarToken = bounty_registry.NectarToken
    BountyRegistry = bounty_registry.BountyRegistry

    ambassador = BountyRegistry.ambassadors[0]
    expert = BountyRegistry.experts[0]
    duration = 10
    bid = 10 * 10 ** 18

    assertion_fee = BountyRegistry.functions.assertionFee().call()

    guid, _ = post_bounty(bounty_registry, ambassador.address, num_artifacts=1, duration=duration)
    index, nonce, _ = post_assertion(bounty_registry, expert.address, guid, mask=[True], verdicts=[True])

    eth_tester.mine_blocks(duration)

    reveal_assertion(bounty_registry, expert.address, guid, index, nonce, [True], 'foo')

    assert NectarToken.functions.balanceOf(expert.address).call() == STARTING_BALANCE - bid - assertion_fee
    assert BountyRegistry.functions.getNumberOfAssertions(guid).call() == 1
    assert BountyRegistry.functions.assertionsByGuid(guid, 0).call()[1] == bid


def test_reject_assertions_with_invalid_bounty_guid(bounty_registry):
    BountyRegistry = bounty_registry.BountyRegistry

    expert = BountyRegistry.experts[0]

    with pytest.raises(TransactionFailed):
        post_assertion(bounty_registry, expert.address, 1, mask=[True], verdicts=[True])


def test_reject_assertions_with_invalid_bid(bounty_registry):
    BountyRegistry = bounty_registry.BountyRegistry

    expert = BountyRegistry.experts[0]
    bid = int(0.05 * 10 ** 18)

    with pytest.raises(TransactionFailed):
        post_assertion(bounty_registry, expert.address, 1, bid=bid, mask=[True], verdicts=[True])


def test_reject_assertions_on_expired_bounty(bounty_registry, eth_tester):
    BountyRegistry = bounty_registry.BountyRegistry

    ambassador = BountyRegistry.ambassadors[0]
    expert = BountyRegistry.experts[0]
    duration = 10

    guid, _ = post_bounty(bounty_registry, ambassador.address, num_artifacts=1, duration=duration)

    eth_tester.mine_blocks(duration)

    with pytest.raises(TransactionFailed):
        post_assertion(bounty_registry, expert.address, 1, mask=[True], verdicts=[True])


def test_reject_assertions_from_same_user(bounty_registry):
    BountyRegistry = bounty_registry.BountyRegistry

    ambassador = BountyRegistry.ambassadors[0]
    expert = BountyRegistry.experts[0]
    duration = 10

    guid, _ = post_bounty(bounty_registry, ambassador.address, num_artifacts=1, duration=duration)
    post_assertion(bounty_registry, expert.address, guid, mask=[True], verdicts=[True])

    with pytest.raises(TransactionFailed):
        post_assertion(bounty_registry, expert.address, guid, mask=[True], verdicts=[True])


def test_arbiter_vote_on_bounty(bounty_registry, eth_tester):
    BountyRegistry = bounty_registry.BountyRegistry

    ambassador = BountyRegistry.ambassadors[0]
    expert0 = BountyRegistry.experts[0]
    expert1 = BountyRegistry.experts[1]
    arbiters = BountyRegistry.arbiters
    duration = 10

    assertion_reveal_window = BountyRegistry.functions.ASSERTION_REVEAL_WINDOW().call()

    guid, _ = post_bounty(bounty_registry, ambassador.address, num_artifacts=1, duration=duration)
    post_assertion(bounty_registry, expert0.address, guid, mask=[True], verdicts=[False])
    post_assertion(bounty_registry, expert1.address, guid, mask=[True], verdicts=[True])

    eth_tester.mine_blocks(duration + assertion_reveal_window)

    vote_on_bounty(bounty_registry, arbiters[0].address, guid, [False])
    vote_on_bounty(bounty_registry, arbiters[1].address, guid, [True])
    vote_on_bounty(bounty_registry, arbiters[2].address, guid, [True])

    assert len(BountyRegistry.functions.getVoters(guid).call()) == 3


def test_arbiter_settle_before_voting_ends(bounty_registry, eth_tester):
    BountyRegistry = bounty_registry.BountyRegistry

    ambassador = BountyRegistry.ambassadors[0]
    expert0 = BountyRegistry.experts[0]
    expert1 = BountyRegistry.experts[1]
    arbiter = BountyRegistry.arbiters[0]
    duration = 10

    assertion_reveal_window = BountyRegistry.functions.ASSERTION_REVEAL_WINDOW().call()

    guid, _ = post_bounty(bounty_registry, ambassador.address, num_artifacts=1, duration=duration)

    index0, nonce0, _ = post_assertion(bounty_registry, expert0.address, guid, mask=[True], verdicts=[False])
    index1, nonce1, _ = post_assertion(bounty_registry, expert1.address, guid, mask=[True], verdicts=[True])

    with pytest.raises(TransactionFailed):
        settle_bounty(bounty_registry, arbiter.address, guid)

    eth_tester.mine_blocks(duration)

    with pytest.raises(TransactionFailed):
        settle_bounty(bounty_registry, arbiter.address, guid)

    reveal_assertion(bounty_registry, expert0.address, guid, index0, nonce0, [False], 'foo')
    reveal_assertion(bounty_registry, expert1.address, guid, index1, nonce1, [True], 'bar')

    eth_tester.mine_blocks(assertion_reveal_window)

    vote_on_bounty(bounty_registry, arbiter.address, guid, [False])

    with pytest.raises(TransactionFailed):
        settle_bounty(bounty_registry, arbiter.address, guid)


def test_arbiter_settle_after_voting_ends(bounty_registry, eth_tester):
    NectarToken = bounty_registry.NectarToken
    BountyRegistry = bounty_registry.BountyRegistry

    ambassador = BountyRegistry.ambassadors[0]
    expert0 = BountyRegistry.experts[0]
    expert1 = BountyRegistry.experts[1]
    arbiters = BountyRegistry.arbiters
    amount = 10 * 10 ** 18
    duration = 10
    bid = 20 * 10 ** 18

    bounty_fee = BountyRegistry.functions.bountyFee().call()
    assertion_fee = BountyRegistry.functions.assertionFee().call()
    assertion_reveal_window = BountyRegistry.functions.ASSERTION_REVEAL_WINDOW().call()
    stake_amount = BountyRegistry.stake_amount
    arbiter_vote_window = BountyRegistry.arbiter_vote_window

    guid, _ = post_bounty(bounty_registry, ambassador.address, amount=amount, num_artifacts=1, duration=duration)

    index0, nonce0, _ = post_assertion(bounty_registry, expert0.address, guid, bid=bid, mask=[True], verdicts=[False])
    index1, nonce1, _ = post_assertion(bounty_registry, expert1.address, guid, bid=bid, mask=[True], verdicts=[True])

    eth_tester.mine_blocks(duration)

    reveal_assertion(bounty_registry, expert0.address, guid, index0, nonce0, [False], 'foo')
    reveal_assertion(bounty_registry, expert1.address, guid, index1, nonce1, [True], 'bar')

    eth_tester.mine_blocks(assertion_reveal_window)

    vote_on_bounty(bounty_registry, arbiters[0].address, guid, [False])
    vote_on_bounty(bounty_registry, arbiters[1].address, guid, [False])
    vote_on_bounty(bounty_registry, arbiters[2].address, guid, [False])
    vote_on_bounty(bounty_registry, arbiters[3].address, guid, [True])

    eth_tester.mine_blocks(arbiter_vote_window)

    settle_bounty(bounty_registry, expert0.address, guid)
    settle_bounty(bounty_registry, expert1.address, guid)

    settle_bounty(bounty_registry, arbiters[0].address, guid)
    selected = BountyRegistry.functions.bountiesByGuid(guid).call()[6]
    assert selected != ZERO_ADDRESS

    # If we weren't the selected arbiter, call settle again with the selected one
    if selected != arbiters[0].address:
        settle_bounty(bounty_registry, selected, guid)

    assert NectarToken.functions.balanceOf(expert0.address).call() == \
           STARTING_BALANCE - bid - assertion_fee
    assert NectarToken.functions.balanceOf(expert1.address).call() == \
           STARTING_BALANCE + bid + amount - assertion_fee
    assert NectarToken.functions.balanceOf(selected).call() == \
           STARTING_BALANCE - stake_amount + 2 * assertion_fee + bounty_fee


def test_should_allow_voting_after_quorum_reached(bounty_registry, eth_tester):
    BountyRegistry = bounty_registry.BountyRegistry

    ambassador = BountyRegistry.ambassadors[0]
    expert0 = BountyRegistry.experts[0]
    expert1 = BountyRegistry.experts[1]
    arbiters = BountyRegistry.arbiters
    duration = 10

    assertion_reveal_window = BountyRegistry.functions.ASSERTION_REVEAL_WINDOW().call()

    guid, _ = post_bounty(bounty_registry, ambassador.address, num_artifacts=1, duration=duration)

    post_assertion(bounty_registry, expert0.address, guid, mask=[True], verdicts=[False])
    post_assertion(bounty_registry, expert1.address, guid, mask=[True], verdicts=[True])

    eth_tester.mine_blocks(duration + assertion_reveal_window)

    vote_on_bounty(bounty_registry, arbiters[0].address, guid, [True])
    vote_on_bounty(bounty_registry, arbiters[1].address, guid, [False])


def test_rejects_arbiter_settles_before_voting_ends(bounty_registry, eth_tester):
    BountyRegistry = bounty_registry.BountyRegistry

    ambassador = BountyRegistry.ambassadors[0]
    expert0 = BountyRegistry.experts[0]
    expert1 = BountyRegistry.experts[1]
    arbiter = BountyRegistry.arbiters[0]
    duration = 10

    assertion_reveal_window = BountyRegistry.functions.ASSERTION_REVEAL_WINDOW().call()

    guid, _ = post_bounty(bounty_registry, ambassador.address, num_artifacts=2, duration=duration)

    index0, nonce0, _ = post_assertion(bounty_registry, expert0.address, guid, mask=[True, True],
                                       verdicts=[False, False])
    index1, nonce1, _ = post_assertion(bounty_registry, expert1.address, guid, mask=[True, True],
                                       verdicts=[False, True])

    eth_tester.mine_blocks(duration)

    reveal_assertion(bounty_registry, expert0.address, guid, index0, nonce0, [False, False], 'foo')
    reveal_assertion(bounty_registry, expert1.address, guid, index1, nonce1, [False, True], 'bar')

    eth_tester.mine_blocks(assertion_reveal_window)

    vote_on_bounty(bounty_registry, arbiter.address, guid, [True, True])

    settle_bounty(bounty_registry, expert0.address, guid)
    with pytest.raises(TransactionFailed):
        settle_bounty(bounty_registry, arbiter.address, guid)


def test_settle_multi_artifact_bounty(bounty_registry, eth_tester):
    NectarToken = bounty_registry.NectarToken
    BountyRegistry = bounty_registry.BountyRegistry

    ambassador = BountyRegistry.ambassadors[0]
    expert0 = BountyRegistry.experts[0]
    expert1 = BountyRegistry.experts[1]
    arbiters = BountyRegistry.arbiters
    amount = 10 * 10 ** 18
    duration = 10
    bid = 20 * 10 ** 18

    bounty_fee = BountyRegistry.functions.bountyFee().call()
    assertion_fee = BountyRegistry.functions.assertionFee().call()
    assertion_reveal_window = BountyRegistry.functions.ASSERTION_REVEAL_WINDOW().call()
    stake_amount = BountyRegistry.stake_amount
    arbiter_vote_window = BountyRegistry.arbiter_vote_window

    guid, _ = post_bounty(bounty_registry, ambassador.address, amount=amount, num_artifacts=2, duration=duration)

    index0, nonce0, _ = post_assertion(bounty_registry, expert0.address, guid, bid=bid, mask=[True, True],
                                       verdicts=[False, False])
    index1, nonce1, _ = post_assertion(bounty_registry, expert1.address, guid, bid=bid, mask=[True, True],
                                       verdicts=[False, True])

    eth_tester.mine_blocks(duration)

    reveal_assertion(bounty_registry, expert0.address, guid, index0, nonce0, [False, False], 'foo')
    reveal_assertion(bounty_registry, expert1.address, guid, index1, nonce1, [False, True], 'bar')

    eth_tester.mine_blocks(assertion_reveal_window)

    vote_on_bounty(bounty_registry, arbiters[0].address, guid, [False, True])
    vote_on_bounty(bounty_registry, arbiters[1].address, guid, [False, True])
    vote_on_bounty(bounty_registry, arbiters[2].address, guid, [True, True])

    eth_tester.mine_blocks(arbiter_vote_window)

    settle_bounty(bounty_registry, expert0.address, guid)
    settle_bounty(bounty_registry, expert1.address, guid)

    settle_bounty(bounty_registry, arbiters[0].address, guid)
    selected = BountyRegistry.functions.bountiesByGuid(guid).call()[6]
    assert selected != ZERO_ADDRESS

    # If we weren't the selected arbiter, call settle again with the selected one
    if selected != arbiters[0].address:
        settle_bounty(bounty_registry, selected, guid)

    assert NectarToken.functions.balanceOf(expert0.address).call() == \
           STARTING_BALANCE - bid - assertion_fee
    assert NectarToken.functions.balanceOf(expert1.address).call() == \
           STARTING_BALANCE + amount // 2 - assertion_fee
    assert NectarToken.functions.balanceOf(selected).call() == \
           STARTING_BALANCE - stake_amount + bid + amount // 2 + 2 * assertion_fee + bounty_fee


def test_any_arbiter_settle_after_256_blocks(bounty_registry, eth_tester):
    NectarToken = bounty_registry.NectarToken
    BountyRegistry = bounty_registry.BountyRegistry

    ambassador = BountyRegistry.ambassadors[0]
    expert0 = BountyRegistry.experts[0]
    expert1 = BountyRegistry.experts[1]
    arbiters = BountyRegistry.arbiters
    amount = 10 * 10 ** 18
    duration = 10
    bid = 20 * 10 ** 18

    bounty_fee = BountyRegistry.functions.bountyFee().call()
    assertion_fee = BountyRegistry.functions.assertionFee().call()
    assertion_reveal_window = BountyRegistry.functions.ASSERTION_REVEAL_WINDOW().call()
    stake_amount = BountyRegistry.stake_amount
    arbiter_vote_window = BountyRegistry.arbiter_vote_window

    guid, _ = post_bounty(bounty_registry, ambassador.address, amount=amount, num_artifacts=2, duration=duration)

    index0, nonce0, _ = post_assertion(bounty_registry, expert0.address, guid, bid=bid, mask=[True, True],
                                       verdicts=[False, False])
    index1, nonce1, _ = post_assertion(bounty_registry, expert1.address, guid, bid=bid, mask=[True, True],
                                       verdicts=[False, True])

    eth_tester.mine_blocks(duration)

    reveal_assertion(bounty_registry, expert0.address, guid, index0, nonce0, [False, False], 'foo')
    reveal_assertion(bounty_registry, expert1.address, guid, index1, nonce1, [False, True], 'bar')

    eth_tester.mine_blocks(assertion_reveal_window)

    vote_on_bounty(bounty_registry, arbiters[0].address, guid, [False, True])
    vote_on_bounty(bounty_registry, arbiters[1].address, guid, [False, True])
    vote_on_bounty(bounty_registry, arbiters[2].address, guid, [True, True])

    eth_tester.mine_blocks(arbiter_vote_window)

    settle_bounty(bounty_registry, expert0.address, guid)
    settle_bounty(bounty_registry, expert1.address, guid)

    eth_tester.mine_blocks(256)

    winner = random.choice(arbiters)
    settle_bounty(bounty_registry, winner.address, guid)

    selected = BountyRegistry.functions.bountiesByGuid(guid).call()[6]
    assert selected != ZERO_ADDRESS
    assert selected == winner.address

    assert NectarToken.functions.balanceOf(expert0.address).call() == \
           STARTING_BALANCE - bid - assertion_fee
    assert NectarToken.functions.balanceOf(expert1.address).call() == \
           STARTING_BALANCE + amount // 2 - assertion_fee
    assert NectarToken.functions.balanceOf(selected).call() == \
           STARTING_BALANCE - stake_amount + bid + amount // 2 + 2 * assertion_fee + bounty_fee


def test_reach_quorum_if_all_vote_malicious_first(bounty_registry, eth_tester):
    NectarToken = bounty_registry.NectarToken
    BountyRegistry = bounty_registry.BountyRegistry

    ambassador = BountyRegistry.ambassadors[0]
    expert0 = BountyRegistry.experts[0]
    expert1 = BountyRegistry.experts[1]
    arbiters = BountyRegistry.arbiters
    amount = 10 * 10 ** 18
    duration = 10
    bid = 20 * 10 ** 18

    bounty_fee = BountyRegistry.functions.bountyFee().call()
    assertion_fee = BountyRegistry.functions.assertionFee().call()
    assertion_reveal_window = BountyRegistry.functions.ASSERTION_REVEAL_WINDOW().call()
    stake_amount = BountyRegistry.stake_amount
    arbiter_vote_window = BountyRegistry.arbiter_vote_window

    guid, _ = post_bounty(bounty_registry, ambassador.address, amount=amount, num_artifacts=2, duration=duration)

    index0, nonce0, _ = post_assertion(bounty_registry, expert0.address, guid, bid=bid, mask=[True, True],
                                       verdicts=[False, False])
    index1, nonce1, _ = post_assertion(bounty_registry, expert1.address, guid, bid=bid, mask=[True, True],
                                       verdicts=[False, True])

    eth_tester.mine_blocks(duration)

    reveal_assertion(bounty_registry, expert0.address, guid, index0, nonce0, [False, False], 'foo')
    reveal_assertion(bounty_registry, expert1.address, guid, index1, nonce1, [False, True], 'bar')

    eth_tester.mine_blocks(assertion_reveal_window)

    vote_on_bounty(bounty_registry, arbiters[0].address, guid, [False, True])
    vote_on_bounty(bounty_registry, arbiters[1].address, guid, [False, True])
    vote_on_bounty(bounty_registry, arbiters[2].address, guid, [False, True])
    vote_on_bounty(bounty_registry, arbiters[3].address, guid, [False, True])

    eth_tester.mine_blocks(arbiter_vote_window)

    settle_bounty(bounty_registry, expert0.address, guid)
    settle_bounty(bounty_registry, expert1.address, guid)

    settle_bounty(bounty_registry, arbiters[0].address, guid)
    selected = BountyRegistry.functions.bountiesByGuid(guid).call()[6]
    assert selected != ZERO_ADDRESS

    # If we weren't the selected arbiter, call settle again with the selected one
    if selected != arbiters[0].address:
        settle_bounty(bounty_registry, selected, guid)

    assert NectarToken.functions.balanceOf(expert0.address).call() == \
           STARTING_BALANCE + amount // 4 - bid // 2 - assertion_fee
    assert NectarToken.functions.balanceOf(expert1.address).call() == \
           STARTING_BALANCE + (3 * amount // 4) + bid // 2 - assertion_fee
    assert NectarToken.functions.balanceOf(selected).call() == \
           STARTING_BALANCE - stake_amount + 2 * assertion_fee + bounty_fee


def test_reach_quorum_if_all_vote_malicious_second(bounty_registry, eth_tester):
    NectarToken = bounty_registry.NectarToken
    BountyRegistry = bounty_registry.BountyRegistry

    ambassador = BountyRegistry.ambassadors[0]
    expert0 = BountyRegistry.experts[0]
    expert1 = BountyRegistry.experts[1]
    arbiters = BountyRegistry.arbiters
    amount = 10 * 10 ** 18
    duration = 10
    bid = 20 * 10 ** 18

    bounty_fee = BountyRegistry.functions.bountyFee().call()
    assertion_fee = BountyRegistry.functions.assertionFee().call()
    assertion_reveal_window = BountyRegistry.functions.ASSERTION_REVEAL_WINDOW().call()
    stake_amount = BountyRegistry.stake_amount
    arbiter_vote_window = BountyRegistry.arbiter_vote_window

    guid, _ = post_bounty(bounty_registry, ambassador.address, amount=amount, num_artifacts=2, duration=duration)

    index0, nonce0, _ = post_assertion(bounty_registry, expert0.address, guid, bid=bid, mask=[True, True],
                                       verdicts=[False, False])
    index1, nonce1, _ = post_assertion(bounty_registry, expert1.address, guid, bid=bid, mask=[True, True],
                                       verdicts=[False, True])

    eth_tester.mine_blocks(duration)

    reveal_assertion(bounty_registry, expert0.address, guid, index0, nonce0, [False, False], 'foo')
    reveal_assertion(bounty_registry, expert1.address, guid, index1, nonce1, [False, True], 'bar')

    eth_tester.mine_blocks(assertion_reveal_window)

    vote_on_bounty(bounty_registry, arbiters[0].address, guid, [True, False])
    vote_on_bounty(bounty_registry, arbiters[1].address, guid, [True, False])
    vote_on_bounty(bounty_registry, arbiters[2].address, guid, [True, False])
    vote_on_bounty(bounty_registry, arbiters[3].address, guid, [True, False])

    eth_tester.mine_blocks(arbiter_vote_window)

    settle_bounty(bounty_registry, expert0.address, guid)
    settle_bounty(bounty_registry, expert1.address, guid)

    settle_bounty(bounty_registry, arbiters[0].address, guid)
    selected = BountyRegistry.functions.bountiesByGuid(guid).call()[6]
    assert selected != ZERO_ADDRESS

    # If we weren't the selected arbiter, call settle again with the selected one
    if selected != arbiters[0].address:
        settle_bounty(bounty_registry, selected, guid)

    assert NectarToken.functions.balanceOf(expert0.address).call() == \
           STARTING_BALANCE + amount // 2 - assertion_fee
    assert NectarToken.functions.balanceOf(expert1.address).call() == \
           STARTING_BALANCE - bid - assertion_fee
    assert NectarToken.functions.balanceOf(selected).call() == \
           STARTING_BALANCE - stake_amount + bid + amount // 2 + 2 * assertion_fee + bounty_fee


def test_unrevealed_assertions_incorrect(bounty_registry, eth_tester):
    NectarToken = bounty_registry.NectarToken
    BountyRegistry = bounty_registry.BountyRegistry

    ambassador = BountyRegistry.ambassadors[0]
    expert0 = BountyRegistry.experts[0]
    expert1 = BountyRegistry.experts[1]
    arbiters = BountyRegistry.arbiters
    amount = 10 * 10 ** 18
    duration = 10
    bid = 20 * 10 ** 18

    bounty_fee = BountyRegistry.functions.bountyFee().call()
    assertion_fee = BountyRegistry.functions.assertionFee().call()
    assertion_reveal_window = BountyRegistry.functions.ASSERTION_REVEAL_WINDOW().call()
    stake_amount = BountyRegistry.stake_amount
    arbiter_vote_window = BountyRegistry.arbiter_vote_window

    guid, _ = post_bounty(bounty_registry, ambassador.address, amount=amount, num_artifacts=2, duration=duration)

    index0, nonce0, _ = post_assertion(bounty_registry, expert0.address, guid, bid=bid, mask=[True, True],
                                       verdicts=[False, False])
    index1, nonce1, _ = post_assertion(bounty_registry, expert1.address, guid, bid=bid, mask=[True, True],
                                       verdicts=[False, True])

    eth_tester.mine_blocks(duration)

    # Expert 0 doesn't reveal
    reveal_assertion(bounty_registry, expert1.address, guid, index1, nonce1, [False, True], 'bar')

    eth_tester.mine_blocks(assertion_reveal_window)

    vote_on_bounty(bounty_registry, arbiters[0].address, guid, [True, False])
    vote_on_bounty(bounty_registry, arbiters[1].address, guid, [True, False])
    vote_on_bounty(bounty_registry, arbiters[2].address, guid, [True, True])

    eth_tester.mine_blocks(arbiter_vote_window)

    settle_bounty(bounty_registry, expert0.address, guid)
    settle_bounty(bounty_registry, expert1.address, guid)

    settle_bounty(bounty_registry, arbiters[0].address, guid)
    selected = BountyRegistry.functions.bountiesByGuid(guid).call()[6]
    assert selected != ZERO_ADDRESS

    # If we weren't the selected arbiter, call settle again with the selected one
    if selected != arbiters[0].address:
        settle_bounty(bounty_registry, selected, guid)

    assert NectarToken.functions.balanceOf(expert0.address).call() == \
           STARTING_BALANCE - bid - assertion_fee
    assert NectarToken.functions.balanceOf(expert1.address).call() == \
           STARTING_BALANCE + amount // 2 - assertion_fee
    assert NectarToken.functions.balanceOf(selected).call() == \
           STARTING_BALANCE - stake_amount + bid + amount // 2 + 2 * assertion_fee + bounty_fee


def test_only_owner_can_modify_arbiters(bounty_registry):
    BountyRegistry = bounty_registry.BountyRegistry
    network = bounty_registry.network

    non_owner = BountyRegistry.ambassadors[0]
    arbiter = BountyRegistry.arbiters[0]

    with pytest.raises(TransactionFailed):
        BountyRegistry.functions.removeArbiter(arbiter.address, network.block_number()).transact(
            {'from': non_owner.address})

    with pytest.raises(TransactionFailed):
        BountyRegistry.functions.addArbiter(non_owner.address, network.block_number()).transact(
            {'from': non_owner.address})


def test_should_allow_removing_arbiters(bounty_registry, eth_tester):
    BountyRegistry = bounty_registry.BountyRegistry
    network = bounty_registry.network

    owner = BountyRegistry.owner
    ambassador = BountyRegistry.ambassadors[0]
    expert0 = BountyRegistry.experts[0]
    expert1 = BountyRegistry.experts[1]
    arbiter = BountyRegistry.arbiters[0]
    duration = 10

    BountyRegistry.functions.removeArbiter(arbiter.address, network.block_number()).transact({'from': owner})

    guid, _ = post_bounty(bounty_registry, ambassador.address, duration=duration)

    index0, nonce0, _ = post_assertion(bounty_registry, expert0.address, guid, mask=[True], verdicts=[False])
    index1, nonce1, _ = post_assertion(bounty_registry, expert1.address, guid, mask=[True], verdicts=[True])

    eth_tester.mine_blocks(duration)

    with pytest.raises(TransactionFailed):
        vote_on_bounty(bounty_registry, arbiter.address, guid, [True])


def test_should_allow_removing_and_readding_arbiters(bounty_registry, eth_tester):
    BountyRegistry = bounty_registry.BountyRegistry
    network = bounty_registry.network

    owner = BountyRegistry.owner
    ambassador = BountyRegistry.ambassadors[0]
    expert0 = BountyRegistry.experts[0]
    expert1 = BountyRegistry.experts[1]
    arbiter = BountyRegistry.arbiters[0]
    duration = 10

    assertion_reveal_window = BountyRegistry.functions.ASSERTION_REVEAL_WINDOW().call()

    BountyRegistry.functions.removeArbiter(arbiter.address, network.block_number()).transact({'from': owner})
    BountyRegistry.functions.addArbiter(arbiter.address, network.block_number()).transact({'from': owner})

    guid, _ = post_bounty(bounty_registry, ambassador.address, duration=duration)

    index0, nonce0, _ = post_assertion(bounty_registry, expert0.address, guid, mask=[True], verdicts=[False])
    index1, nonce1, _ = post_assertion(bounty_registry, expert1.address, guid, mask=[True], verdicts=[True])

    eth_tester.mine_blocks(duration + assertion_reveal_window)

    vote_on_bounty(bounty_registry, arbiter.address, guid, [True])


def test_should_calculate_arbiter_candidates(bounty_registry):
    BountyRegistry = bounty_registry.BountyRegistry

    ambassadors = BountyRegistry.ambassadors

    post_bounty(bounty_registry, ambassadors[0].address)
    post_bounty(bounty_registry, ambassadors[1].address)
    post_bounty(bounty_registry, ambassadors[2].address)
    post_bounty(bounty_registry, ambassadors[0].address)
    post_bounty(bounty_registry, ambassadors[1].address)
    post_bounty(bounty_registry, ambassadors[0].address)

    assert set(BountyRegistry.functions.getArbiterCandidates().call()) == {a.address for a in ambassadors}


def test_should_refund_bounty_amount_and_fee_to_ambassador_if_no_assertions_or_votes(bounty_registry, eth_tester):
    NectarToken = bounty_registry.NectarToken
    BountyRegistry = bounty_registry.BountyRegistry

    ambassador = BountyRegistry.ambassadors[0]
    duration = 10

    assertion_reveal_window = BountyRegistry.functions.ASSERTION_REVEAL_WINDOW().call()
    arbiter_vote_window = BountyRegistry.arbiter_vote_window

    guid, _ = post_bounty(bounty_registry, ambassador.address, duration=duration)

    eth_tester.mine_blocks(duration + assertion_reveal_window + arbiter_vote_window)

    settle_bounty(bounty_registry, ambassador.address, guid)

    assert NectarToken.functions.balanceOf(ambassador.address).call() == STARTING_BALANCE
    assert NectarToken.functions.balanceOf(BountyRegistry.address).call() == 0


def test_should_refund_bounty_amount_to_ambassador_if_no_assertions(bounty_registry, eth_tester):
    NectarToken = bounty_registry.NectarToken
    BountyRegistry = bounty_registry.BountyRegistry

    ambassador = BountyRegistry.ambassadors[0]
    arbiter = BountyRegistry.arbiters[0]
    duration = 10

    bounty_fee = BountyRegistry.functions.bountyFee().call()
    assertion_reveal_window = BountyRegistry.functions.ASSERTION_REVEAL_WINDOW().call()
    stake_amount = BountyRegistry.stake_amount
    arbiter_vote_window = BountyRegistry.arbiter_vote_window

    guid, _ = post_bounty(bounty_registry, ambassador.address, duration=duration)

    eth_tester.mine_blocks(duration + assertion_reveal_window)

    vote_on_bounty(bounty_registry, arbiter.address, guid, [True])

    eth_tester.mine_blocks(arbiter_vote_window)

    settle_bounty(bounty_registry, ambassador.address, guid)

    settle_bounty(bounty_registry, arbiter.address, guid)
    selected = BountyRegistry.functions.bountiesByGuid(guid).call()[6]
    assert selected != ZERO_ADDRESS

    if selected != arbiter.address:
        settle_bounty(bounty_registry, selected, guid)

    assert NectarToken.functions.balanceOf(ambassador.address).call() == STARTING_BALANCE - bounty_fee
    assert NectarToken.functions.balanceOf(selected).call() == STARTING_BALANCE - stake_amount + bounty_fee
    assert NectarToken.functions.balanceOf(BountyRegistry.address).call() == 0


def test_should_refund_bounty_fee_to_ambassador_if_no_votes(bounty_registry, eth_tester):
    NectarToken = bounty_registry.NectarToken
    BountyRegistry = bounty_registry.BountyRegistry

    ambassador = BountyRegistry.ambassadors[0]
    expert0 = BountyRegistry.experts[0]
    expert1 = BountyRegistry.experts[1]
    duration = 10
    amount = 10 * 10 ** 18

    assertion_reveal_window = BountyRegistry.functions.ASSERTION_REVEAL_WINDOW().call()
    arbiter_vote_window = BountyRegistry.arbiter_vote_window

    guid, _ = post_bounty(bounty_registry, ambassador.address, amount=amount, duration=duration)

    index0, nonce0, _ = post_assertion(bounty_registry, expert0.address, guid, mask=[True], verdicts=[False])
    index1, nonce1, _ = post_assertion(bounty_registry, expert1.address, guid, mask=[True], verdicts=[True])

    eth_tester.mine_blocks(duration)

    reveal_assertion(bounty_registry, expert0.address, guid, index0, nonce0, [False], 'foo')
    reveal_assertion(bounty_registry, expert1.address, guid, index1, nonce1, [True], 'bar')

    eth_tester.mine_blocks(assertion_reveal_window + arbiter_vote_window)

    settle_bounty(bounty_registry, ambassador.address, guid)
    settle_bounty(bounty_registry, expert0.address, guid)
    settle_bounty(bounty_registry, expert1.address, guid)

    assert NectarToken.functions.balanceOf(ambassador.address).call() == STARTING_BALANCE - amount
    assert NectarToken.functions.balanceOf(BountyRegistry.address).call() == 0


def test_should_refund_portion_of_bounty_to_ambassador_if_no_assertions_on_some_artifacts(bounty_registry, eth_tester):
    NectarToken = bounty_registry.NectarToken
    BountyRegistry = bounty_registry.BountyRegistry

    ambassador = BountyRegistry.ambassadors[0]
    expert0 = BountyRegistry.experts[0]
    expert1 = BountyRegistry.experts[1]
    arbiter = BountyRegistry.arbiters[0]
    amount = 10 * 10 ** 18
    duration = 10
    bid = 20 * 10 ** 18

    bounty_fee = BountyRegistry.functions.bountyFee().call()
    assertion_fee = BountyRegistry.functions.assertionFee().call()
    assertion_reveal_window = BountyRegistry.functions.ASSERTION_REVEAL_WINDOW().call()
    stake_amount = BountyRegistry.stake_amount
    arbiter_vote_window = BountyRegistry.arbiter_vote_window

    guid, _ = post_bounty(bounty_registry, ambassador.address, amount=amount, num_artifacts=2, duration=duration)

    index0, nonce0, _ = post_assertion(bounty_registry, expert0.address, guid, bid=bid, mask=[True, False],
                                       verdicts=[True, False])
    index1, nonce1, _ = post_assertion(bounty_registry, expert1.address, guid, bid=bid, mask=[True, False],
                                       verdicts=[True, False])

    eth_tester.mine_blocks(duration)

    reveal_assertion(bounty_registry, expert0.address, guid, index0, nonce0, [True, False], 'foo')
    reveal_assertion(bounty_registry, expert1.address, guid, index1, nonce1, [True, False], 'bar')

    eth_tester.mine_blocks(assertion_reveal_window)

    vote_on_bounty(bounty_registry, arbiter.address, guid, [True, True])

    eth_tester.mine_blocks(arbiter_vote_window)

    settle_bounty(bounty_registry, ambassador.address, guid)
    settle_bounty(bounty_registry, expert0.address, guid)
    settle_bounty(bounty_registry, expert1.address, guid)

    settle_bounty(bounty_registry, arbiter.address, guid)
    selected = BountyRegistry.functions.bountiesByGuid(guid).call()[6]
    assert selected != ZERO_ADDRESS

    # If we weren't the selected arbiter, call settle again with the selected one
    if selected != arbiter.address:
        settle_bounty(bounty_registry, selected, guid)

    assert NectarToken.functions.balanceOf(ambassador.address).call() == \
           STARTING_BALANCE - amount // 2 - bounty_fee
    assert NectarToken.functions.balanceOf(selected).call() == \
           STARTING_BALANCE - stake_amount + 2 * assertion_fee + bounty_fee


def test_should_refund_portion_of_bounty_to_ambassador_if_no_assertions_on_any_artifacts(bounty_registry, eth_tester):
    NectarToken = bounty_registry.NectarToken
    BountyRegistry = bounty_registry.BountyRegistry

    ambassador = BountyRegistry.ambassadors[0]
    expert0 = BountyRegistry.experts[0]
    expert1 = BountyRegistry.experts[1]
    arbiter = BountyRegistry.arbiters[0]
    amount = 10 * 10 ** 18
    duration = 10
    bid = 20 * 10 ** 18

    bounty_fee = BountyRegistry.functions.bountyFee().call()
    assertion_fee = BountyRegistry.functions.assertionFee().call()
    assertion_reveal_window = BountyRegistry.functions.ASSERTION_REVEAL_WINDOW().call()
    stake_amount = BountyRegistry.stake_amount
    arbiter_vote_window = BountyRegistry.arbiter_vote_window

    guid, _ = post_bounty(bounty_registry, ambassador.address, amount=amount, num_artifacts=2, duration=duration)

    index0, nonce0, _ = post_assertion(bounty_registry, expert0.address, guid, bid=bid, mask=[False, False],
                                       verdicts=[True, True])
    index1, nonce1, _ = post_assertion(bounty_registry, expert1.address, guid, bid=bid, mask=[False, False],
                                       verdicts=[True, True])

    eth_tester.mine_blocks(duration)

    reveal_assertion(bounty_registry, expert0.address, guid, index0, nonce0, [True, True], 'foo')
    reveal_assertion(bounty_registry, expert1.address, guid, index1, nonce1, [True, True], 'bar')

    eth_tester.mine_blocks(assertion_reveal_window)

    vote_on_bounty(bounty_registry, arbiter.address, guid, [True, True])

    eth_tester.mine_blocks(arbiter_vote_window)

    settle_bounty(bounty_registry, ambassador.address, guid)
    settle_bounty(bounty_registry, expert0.address, guid)
    settle_bounty(bounty_registry, expert1.address, guid)

    settle_bounty(bounty_registry, arbiter.address, guid)
    selected = BountyRegistry.functions.bountiesByGuid(guid).call()[6]
    assert selected != ZERO_ADDRESS

    # If we weren't the selected arbiter, call settle again with the selected one
    if selected != arbiter.address:
        settle_bounty(bounty_registry, selected, guid)

    assert NectarToken.functions.balanceOf(ambassador.address).call() == \
           STARTING_BALANCE - bounty_fee
    assert NectarToken.functions.balanceOf(selected).call() == \
           STARTING_BALANCE - stake_amount + 2 * assertion_fee + bounty_fee
    assert NectarToken.functions.balanceOf(NectarToken.address).call() == 0


def test_payout_fee_bid_amount_to_one_expert_if_no_votes(bounty_registry, eth_tester):
    NectarToken = bounty_registry.NectarToken
    BountyRegistry = bounty_registry.BountyRegistry

    ambassador = BountyRegistry.ambassadors[0]
    expert = BountyRegistry.experts[0]
    amount = 10 * 10 ** 18
    duration = 10
    bid = 20 * 10 ** 18

    assertion_reveal_window = BountyRegistry.functions.ASSERTION_REVEAL_WINDOW().call()
    arbiter_vote_window = BountyRegistry.arbiter_vote_window

    guid, _ = post_bounty(bounty_registry, ambassador.address, amount=amount, num_artifacts=2, duration=duration)

    index, nonce, _ = post_assertion(bounty_registry, expert.address, guid, bid=bid, mask=[True, True],
                                     verdicts=[True, True])

    eth_tester.mine_blocks(duration)

    reveal_assertion(bounty_registry, expert.address, guid, index, nonce, [True, True], 'foo')

    eth_tester.mine_blocks(assertion_reveal_window + arbiter_vote_window)

    settle_bounty(bounty_registry, ambassador.address, guid)
    settle_bounty(bounty_registry, expert.address, guid)

    assert NectarToken.functions.balanceOf(expert.address).call() == \
           STARTING_BALANCE + amount
    assert NectarToken.functions.balanceOf(BountyRegistry.address).call() == 0


def test_payout_fee_bid_amount_to_two_experts_if_no_votes(bounty_registry, eth_tester):
    NectarToken = bounty_registry.NectarToken
    BountyRegistry = bounty_registry.BountyRegistry

    ambassador = BountyRegistry.ambassadors[0]
    expert0 = BountyRegistry.experts[0]
    expert1 = BountyRegistry.experts[1]
    amount = 10 * 10 ** 18
    duration = 10
    bid = 20 * 10 ** 18

    assertion_reveal_window = BountyRegistry.functions.ASSERTION_REVEAL_WINDOW().call()
    arbiter_vote_window = BountyRegistry.arbiter_vote_window

    guid, _ = post_bounty(bounty_registry, ambassador.address, amount=amount, num_artifacts=2, duration=duration)

    index0, nonce0, _ = post_assertion(bounty_registry, expert0.address, guid, bid=bid, mask=[True, True],
                                       verdicts=[True, True])
    index1, nonce1, _ = post_assertion(bounty_registry, expert1.address, guid, bid=bid, mask=[True, True],
                                       verdicts=[True, True])

    eth_tester.mine_blocks(duration)

    reveal_assertion(bounty_registry, expert0.address, guid, index0, nonce0, [True, True], 'foo')
    reveal_assertion(bounty_registry, expert1.address, guid, index1, nonce1, [True, True], 'foo')

    eth_tester.mine_blocks(assertion_reveal_window + arbiter_vote_window)

    settle_bounty(bounty_registry, ambassador.address, guid)
    settle_bounty(bounty_registry, expert0.address, guid)
    settle_bounty(bounty_registry, expert1.address, guid)

    assert NectarToken.functions.balanceOf(expert0.address).call() == \
           STARTING_BALANCE + amount // 2
    assert NectarToken.functions.balanceOf(expert1.address).call() == \
           STARTING_BALANCE + amount // 2
    assert NectarToken.functions.balanceOf(BountyRegistry.address).call() == 0


def test_lose_bid_if_no_reveal(bounty_registry, eth_tester):
    NectarToken = bounty_registry.NectarToken
    BountyRegistry = bounty_registry.BountyRegistry

    ambassador = BountyRegistry.ambassadors[0]
    expert0 = BountyRegistry.experts[0]
    expert1 = BountyRegistry.experts[1]
    arbiter = BountyRegistry.arbiters[0]
    amount = 10 * 10 ** 18
    duration = 10
    bid = 20 * 10 ** 18

    bounty_fee = BountyRegistry.functions.bountyFee().call()
    assertion_fee = BountyRegistry.functions.assertionFee().call()
    assertion_reveal_window = BountyRegistry.functions.ASSERTION_REVEAL_WINDOW().call()
    stake_amount = BountyRegistry.stake_amount
    arbiter_vote_window = BountyRegistry.arbiter_vote_window

    guid, _ = post_bounty(bounty_registry, ambassador.address, amount=amount, num_artifacts=2, duration=duration)

    index0, nonce0, _ = post_assertion(bounty_registry, expert0.address, guid, bid=bid, mask=[True, True],
                                       verdicts=[True, True])
    index1, nonce1, _ = post_assertion(bounty_registry, expert1.address, guid, bid=bid, mask=[True, True],
                                       verdicts=[True, True])

    eth_tester.mine_blocks(duration + assertion_reveal_window)

    vote_on_bounty(bounty_registry, arbiter.address, guid, [True, True])

    eth_tester.mine_blocks(arbiter_vote_window)

    settle_bounty(bounty_registry, ambassador.address, guid)
    settle_bounty(bounty_registry, expert0.address, guid)
    settle_bounty(bounty_registry, expert1.address, guid)

    settle_bounty(bounty_registry, arbiter.address, guid)
    selected = BountyRegistry.functions.bountiesByGuid(guid).call()[6]
    assert selected != ZERO_ADDRESS

    # If we weren't the selected arbiter, call settle again with the selected one
    if selected != arbiter.address:
        settle_bounty(bounty_registry, selected, guid)

    assert NectarToken.functions.balanceOf(expert0.address).call() == \
           STARTING_BALANCE - bid - assertion_fee
    assert NectarToken.functions.balanceOf(expert1.address).call() == \
           STARTING_BALANCE - bid - assertion_fee
    assert NectarToken.functions.balanceOf(selected).call() == \
           STARTING_BALANCE - stake_amount + 2 * assertion_fee + bounty_fee + 2 * bid + amount
    assert NectarToken.functions.balanceOf(BountyRegistry.address).call() == 0


def test_payout_bid_to_expert_if_mask_zero(bounty_registry, eth_tester):
    NectarToken = bounty_registry.NectarToken
    BountyRegistry = bounty_registry.BountyRegistry

    ambassador = BountyRegistry.ambassadors[0]
    expert0 = BountyRegistry.experts[0]
    expert1 = BountyRegistry.experts[1]
    arbiter = BountyRegistry.arbiters[0]
    amount = 10 * 10 ** 18
    duration = 10
    bid = 20 * 10 ** 18

    bounty_fee = BountyRegistry.functions.bountyFee().call()
    assertion_fee = BountyRegistry.functions.assertionFee().call()
    assertion_reveal_window = BountyRegistry.functions.ASSERTION_REVEAL_WINDOW().call()
    stake_amount = BountyRegistry.stake_amount
    arbiter_vote_window = BountyRegistry.arbiter_vote_window

    guid, _ = post_bounty(bounty_registry, ambassador.address, amount=amount, num_artifacts=2, duration=duration)

    index0, nonce0, _ = post_assertion(bounty_registry, expert0.address, guid, bid=bid, mask=[False, False],
                                       verdicts=[True, True])
    index1, nonce1, _ = post_assertion(bounty_registry, expert1.address, guid, bid=bid, mask=[False, False],
                                       verdicts=[True, True])

    eth_tester.mine_blocks(duration + assertion_reveal_window)

    vote_on_bounty(bounty_registry, arbiter.address, guid, [True, True])

    eth_tester.mine_blocks(arbiter_vote_window)

    settle_bounty(bounty_registry, ambassador.address, guid)
    settle_bounty(bounty_registry, expert0.address, guid)
    settle_bounty(bounty_registry, expert1.address, guid)

    settle_bounty(bounty_registry, arbiter.address, guid)
    selected = BountyRegistry.functions.bountiesByGuid(guid).call()[6]
    assert selected != ZERO_ADDRESS

    # If we weren't the selected arbiter, call settle again with the selected one
    if selected != arbiter.address:
        settle_bounty(bounty_registry, selected, guid)

    assert NectarToken.functions.balanceOf(expert0.address).call() == \
           STARTING_BALANCE - assertion_fee
    assert NectarToken.functions.balanceOf(expert1.address).call() == \
           STARTING_BALANCE - assertion_fee
    assert NectarToken.functions.balanceOf(selected).call() == \
           STARTING_BALANCE - stake_amount + 2 * assertion_fee + bounty_fee
    assert NectarToken.functions.balanceOf(BountyRegistry.address).call() == 0


def test_payout_half_amount_lose_half_bid_when_half_right_half_wrong_one_expert(bounty_registry, eth_tester):
    NectarToken = bounty_registry.NectarToken
    BountyRegistry = bounty_registry.BountyRegistry

    ambassador = BountyRegistry.ambassadors[0]
    expert = BountyRegistry.experts[0]
    arbiter = BountyRegistry.arbiters[0]
    amount = 10 * 10 ** 18
    duration = 10
    bid = 20 * 10 ** 18

    bounty_fee = BountyRegistry.functions.bountyFee().call()
    assertion_fee = BountyRegistry.functions.assertionFee().call()
    assertion_reveal_window = BountyRegistry.functions.ASSERTION_REVEAL_WINDOW().call()
    stake_amount = BountyRegistry.stake_amount
    arbiter_vote_window = BountyRegistry.arbiter_vote_window

    guid, _ = post_bounty(bounty_registry, ambassador.address, amount=amount, num_artifacts=2, duration=duration)

    index, nonce, _ = post_assertion(bounty_registry, expert.address, guid, bid=bid, mask=[True, True],
                                     verdicts=[True, False])

    eth_tester.mine_blocks(duration)

    reveal_assertion(bounty_registry, expert.address, guid, index, nonce, [True, False], 'foo')

    eth_tester.mine_blocks(assertion_reveal_window)

    vote_on_bounty(bounty_registry, arbiter.address, guid, [True, True])

    eth_tester.mine_blocks(arbiter_vote_window)

    settle_bounty(bounty_registry, ambassador.address, guid)
    settle_bounty(bounty_registry, expert.address, guid)

    settle_bounty(bounty_registry, arbiter.address, guid)
    selected = BountyRegistry.functions.bountiesByGuid(guid).call()[6]
    assert selected != ZERO_ADDRESS

    # If we weren't the selected arbiter, call settle again with the selected one
    if selected != arbiter.address:
        settle_bounty(bounty_registry, selected, guid)

    assert NectarToken.functions.balanceOf(expert.address).call() == \
           STARTING_BALANCE - bid // 2 + amount // 2 - assertion_fee
    assert NectarToken.functions.balanceOf(selected).call() == \
           STARTING_BALANCE - stake_amount + bid // 2 + amount // 2 + assertion_fee + bounty_fee
    assert NectarToken.functions.balanceOf(BountyRegistry.address).call() == 0


def test_payout_half_amount_lose_half_bid_when_half_right_half_wrong_two_experts(bounty_registry, eth_tester):
    NectarToken = bounty_registry.NectarToken
    BountyRegistry = bounty_registry.BountyRegistry

    ambassador = BountyRegistry.ambassadors[0]
    expert0 = BountyRegistry.experts[0]
    expert1 = BountyRegistry.experts[1]
    arbiter = BountyRegistry.arbiters[0]
    amount = 10 * 10 ** 18
    duration = 10
    bid = 20 * 10 ** 18

    bounty_fee = BountyRegistry.functions.bountyFee().call()
    assertion_fee = BountyRegistry.functions.assertionFee().call()
    assertion_reveal_window = BountyRegistry.functions.ASSERTION_REVEAL_WINDOW().call()
    stake_amount = BountyRegistry.stake_amount
    arbiter_vote_window = BountyRegistry.arbiter_vote_window

    guid, _ = post_bounty(bounty_registry, ambassador.address, amount=amount, num_artifacts=2, duration=duration)

    index0, nonce0, _ = post_assertion(bounty_registry, expert0.address, guid, bid=bid, mask=[True, True],
                                       verdicts=[True, False])
    index1, nonce1, _ = post_assertion(bounty_registry, expert1.address, guid, bid=bid, mask=[True, True],
                                       verdicts=[True, False])

    eth_tester.mine_blocks(duration)

    reveal_assertion(bounty_registry, expert0.address, guid, index0, nonce0, [True, False], 'foo')
    reveal_assertion(bounty_registry, expert1.address, guid, index1, nonce1, [True, False], 'bar')

    eth_tester.mine_blocks(assertion_reveal_window)

    vote_on_bounty(bounty_registry, arbiter.address, guid, [True, True])

    eth_tester.mine_blocks(arbiter_vote_window)

    settle_bounty(bounty_registry, ambassador.address, guid)
    settle_bounty(bounty_registry, expert0.address, guid)
    settle_bounty(bounty_registry, expert1.address, guid)

    settle_bounty(bounty_registry, arbiter.address, guid)
    selected = BountyRegistry.functions.bountiesByGuid(guid).call()[6]
    assert selected != ZERO_ADDRESS

    # If we weren't the selected arbiter, call settle again with the selected one
    if selected != arbiter.address:
        settle_bounty(bounty_registry, selected, guid)

    assert NectarToken.functions.balanceOf(expert0.address).call() == \
           STARTING_BALANCE - bid // 2 + amount // 4 - assertion_fee
    assert NectarToken.functions.balanceOf(expert1.address).call() == \
           STARTING_BALANCE - bid // 2 + amount // 4 - assertion_fee
    assert NectarToken.functions.balanceOf(selected).call() == \
           STARTING_BALANCE - stake_amount + amount // 2 + bid + 2 * assertion_fee + bounty_fee
    assert NectarToken.functions.balanceOf(BountyRegistry.address).call() == 0


def test_payout_when_two_experts_have_differing_incorrect_verdicts(bounty_registry, eth_tester):
    NectarToken = bounty_registry.NectarToken
    BountyRegistry = bounty_registry.BountyRegistry

    ambassador = BountyRegistry.ambassadors[0]
    expert0 = BountyRegistry.experts[0]
    expert1 = BountyRegistry.experts[1]
    arbiter = BountyRegistry.arbiters[0]
    amount = 10 * 10 ** 18
    duration = 10
    bid = 20 * 10 ** 18

    bounty_fee = BountyRegistry.functions.bountyFee().call()
    assertion_fee = BountyRegistry.functions.assertionFee().call()
    assertion_reveal_window = BountyRegistry.functions.ASSERTION_REVEAL_WINDOW().call()
    stake_amount = BountyRegistry.stake_amount
    arbiter_vote_window = BountyRegistry.arbiter_vote_window

    guid, _ = post_bounty(bounty_registry, ambassador.address, amount=amount, num_artifacts=2, duration=duration)

    index0, nonce0, _ = post_assertion(bounty_registry, expert0.address, guid, bid=bid, mask=[True, True],
                                       verdicts=[True, False])
    index1, nonce1, _ = post_assertion(bounty_registry, expert1.address, guid, bid=bid, mask=[True, True],
                                       verdicts=[False, True])

    eth_tester.mine_blocks(duration)

    reveal_assertion(bounty_registry, expert0.address, guid, index0, nonce0, [True, False], 'foo')
    reveal_assertion(bounty_registry, expert1.address, guid, index1, nonce1, [False, True], 'bar')

    eth_tester.mine_blocks(assertion_reveal_window)

    vote_on_bounty(bounty_registry, arbiter.address, guid, [True, True])

    eth_tester.mine_blocks(arbiter_vote_window)

    settle_bounty(bounty_registry, ambassador.address, guid)
    settle_bounty(bounty_registry, expert0.address, guid)
    settle_bounty(bounty_registry, expert1.address, guid)

    settle_bounty(bounty_registry, arbiter.address, guid)
    selected = BountyRegistry.functions.bountiesByGuid(guid).call()[6]
    assert selected != ZERO_ADDRESS

    # If we weren't the selected arbiter, call settle again with the selected one
    if selected != arbiter.address:
        settle_bounty(bounty_registry, selected, guid)

    assert NectarToken.functions.balanceOf(expert0.address).call() == \
           STARTING_BALANCE + amount // 2 - assertion_fee
    assert NectarToken.functions.balanceOf(expert1.address).call() == \
           STARTING_BALANCE + amount // 2 - assertion_fee
    assert NectarToken.functions.balanceOf(selected).call() == \
           STARTING_BALANCE - stake_amount + 2 * assertion_fee + bounty_fee
    assert NectarToken.functions.balanceOf(BountyRegistry.address).call() == 0


def test_should_pay_out_amount_relative_to_bid_proportion(bounty_registry, eth_tester):
    NectarToken = bounty_registry.NectarToken
    BountyRegistry = bounty_registry.BountyRegistry

    ambassador = BountyRegistry.ambassadors[0]
    expert0 = BountyRegistry.experts[0]
    expert1 = BountyRegistry.experts[1]
    arbiter = BountyRegistry.arbiters[0]
    amount = 10 * 10 ** 18
    duration = 10
    bid0 = 20 * 10 ** 18
    bid1 = 30 * 10 ** 18

    bounty_fee = BountyRegistry.functions.bountyFee().call()
    assertion_fee = BountyRegistry.functions.assertionFee().call()
    assertion_reveal_window = BountyRegistry.functions.ASSERTION_REVEAL_WINDOW().call()
    stake_amount = BountyRegistry.stake_amount
    arbiter_vote_window = BountyRegistry.arbiter_vote_window

    guid, _ = post_bounty(bounty_registry, ambassador.address, amount=amount, num_artifacts=2, duration=duration)

    index0, nonce0, _ = post_assertion(bounty_registry, expert0.address, guid, bid=bid0, mask=[True, True],
                                       verdicts=[True, True])
    index1, nonce1, _ = post_assertion(bounty_registry, expert1.address, guid, bid=bid1, mask=[True, True],
                                       verdicts=[True, True])

    eth_tester.mine_blocks(duration)

    reveal_assertion(bounty_registry, expert0.address, guid, index0, nonce0, [True, True], 'foo')
    reveal_assertion(bounty_registry, expert1.address, guid, index1, nonce1, [True, True], 'bar')

    eth_tester.mine_blocks(assertion_reveal_window)

    vote_on_bounty(bounty_registry, arbiter.address, guid, [True, True])

    eth_tester.mine_blocks(arbiter_vote_window)

    settle_bounty(bounty_registry, ambassador.address, guid)
    settle_bounty(bounty_registry, expert0.address, guid)
    settle_bounty(bounty_registry, expert1.address, guid)

    settle_bounty(bounty_registry, arbiter.address, guid)
    selected = BountyRegistry.functions.bountiesByGuid(guid).call()[6]
    assert selected != ZERO_ADDRESS

    # If we weren't the selected arbiter, call settle again with the selected one
    if selected != arbiter.address:
        settle_bounty(bounty_registry, selected, guid)

    total_bid = bid0 + bid1
    assert NectarToken.functions.balanceOf(expert0.address).call() == \
           STARTING_BALANCE + (bid0 * amount // total_bid) - assertion_fee
    assert NectarToken.functions.balanceOf(expert1.address).call() == \
           STARTING_BALANCE + (bid1 * amount // total_bid) - assertion_fee
    assert NectarToken.functions.balanceOf(selected).call() == \
           STARTING_BALANCE - stake_amount + 2 * assertion_fee + bounty_fee
    assert NectarToken.functions.balanceOf(BountyRegistry.address).call() == 0


def test_no_arbiter_payout_if_no_votes(bounty_registry, eth_tester):
    NectarToken = bounty_registry.NectarToken
    BountyRegistry = bounty_registry.BountyRegistry

    ambassador = BountyRegistry.ambassadors[0]
    expert0 = BountyRegistry.experts[0]
    expert1 = BountyRegistry.experts[1]
    arbiters = BountyRegistry.arbiters
    amount = 10 * 10 ** 18
    duration = 10
    bid = 20 * 10 ** 18

    assertion_reveal_window = BountyRegistry.functions.ASSERTION_REVEAL_WINDOW().call()
    stake_amount = BountyRegistry.stake_amount
    arbiter_vote_window = BountyRegistry.arbiter_vote_window

    guid, _ = post_bounty(bounty_registry, ambassador.address, amount=amount, num_artifacts=2, duration=duration)

    index0, nonce0, _ = post_assertion(bounty_registry, expert0.address, guid, bid=bid, mask=[True, True],
                                       verdicts=[True, True])
    index1, nonce1, _ = post_assertion(bounty_registry, expert1.address, guid, bid=bid, mask=[True, True],
                                       verdicts=[True, True])

    eth_tester.mine_blocks(duration)

    reveal_assertion(bounty_registry, expert0.address, guid, index0, nonce0, [True, True], 'foo')
    reveal_assertion(bounty_registry, expert1.address, guid, index1, nonce1, [True, True], 'bar')

    eth_tester.mine_blocks(assertion_reveal_window + arbiter_vote_window)

    settle_bounty(bounty_registry, ambassador.address, guid)
    settle_bounty(bounty_registry, expert0.address, guid)
    settle_bounty(bounty_registry, expert1.address, guid)

    for arbiter in arbiters:
        settle_bounty(bounty_registry, arbiter.address, guid)
        assert NectarToken.functions.balanceOf(arbiter.address).call() == STARTING_BALANCE - stake_amount

    assert NectarToken.functions.balanceOf(BountyRegistry.address).call() == 0


def test_no_arbiter_payout_if_no_assertions_and_no_votes(bounty_registry, eth_tester):
    NectarToken = bounty_registry.NectarToken
    BountyRegistry = bounty_registry.BountyRegistry

    ambassador = BountyRegistry.ambassadors[0]
    arbiters = BountyRegistry.arbiters
    amount = 10 * 10 ** 18
    duration = 10

    assertion_reveal_window = BountyRegistry.functions.ASSERTION_REVEAL_WINDOW().call()
    stake_amount = BountyRegistry.stake_amount
    arbiter_vote_window = BountyRegistry.arbiter_vote_window

    guid, _ = post_bounty(bounty_registry, ambassador.address, amount=amount, num_artifacts=2, duration=duration)

    eth_tester.mine_blocks(duration + assertion_reveal_window + arbiter_vote_window)

    settle_bounty(bounty_registry, ambassador.address, guid)

    for arbiter in arbiters:
        settle_bounty(bounty_registry, arbiter.address, guid)
        assert NectarToken.functions.balanceOf(arbiter.address).call() == STARTING_BALANCE - stake_amount

    assert NectarToken.functions.balanceOf(BountyRegistry.address).call() == 0


def test_payout_bounty_fee_to_arbiter_if_no_votes(bounty_registry, eth_tester):
    NectarToken = bounty_registry.NectarToken
    BountyRegistry = bounty_registry.BountyRegistry

    ambassador = BountyRegistry.ambassadors[0]
    arbiter = BountyRegistry.arbiters[0]
    amount = 10 * 10 ** 18
    duration = 10

    bounty_fee = BountyRegistry.functions.bountyFee().call()
    assertion_reveal_window = BountyRegistry.functions.ASSERTION_REVEAL_WINDOW().call()
    stake_amount = BountyRegistry.stake_amount
    arbiter_vote_window = BountyRegistry.arbiter_vote_window

    guid, _ = post_bounty(bounty_registry, ambassador.address, amount=amount, num_artifacts=2, duration=duration)

    eth_tester.mine_blocks(duration + assertion_reveal_window)

    vote_on_bounty(bounty_registry, arbiter.address, guid, [True, True])

    eth_tester.mine_blocks(arbiter_vote_window)

    settle_bounty(bounty_registry, ambassador.address, guid)

    settle_bounty(bounty_registry, arbiter.address, guid)
    selected = BountyRegistry.functions.bountiesByGuid(guid).call()[6]
    assert selected != ZERO_ADDRESS

    # If we weren't the selected arbiter, call settle again with the selected one
    if selected != arbiter.address:
        settle_bounty(bounty_registry, selected, guid)

    assert NectarToken.functions.balanceOf(selected).call() == STARTING_BALANCE - stake_amount + bounty_fee
    assert NectarToken.functions.balanceOf(BountyRegistry.address).call() == 0


def test_payout_bounty_fee_and_assertion_fees_to_arbiter(bounty_registry, eth_tester):
    NectarToken = bounty_registry.NectarToken
    BountyRegistry = bounty_registry.BountyRegistry

    ambassador = BountyRegistry.ambassadors[0]
    expert0 = BountyRegistry.experts[0]
    expert1 = BountyRegistry.experts[1]
    arbiter = BountyRegistry.arbiters[0]
    amount = 10 * 10 ** 18
    duration = 10
    bid = 20 * 10 ** 18

    bounty_fee = BountyRegistry.functions.bountyFee().call()
    assertion_fee = BountyRegistry.functions.assertionFee().call()
    assertion_reveal_window = BountyRegistry.functions.ASSERTION_REVEAL_WINDOW().call()
    stake_amount = BountyRegistry.stake_amount
    arbiter_vote_window = BountyRegistry.arbiter_vote_window

    guid, _ = post_bounty(bounty_registry, ambassador.address, amount=amount, num_artifacts=2, duration=duration)

    index0, nonce0, _ = post_assertion(bounty_registry, expert0.address, guid, bid=bid, mask=[True, True],
                                       verdicts=[True, True])
    index1, nonce1, _ = post_assertion(bounty_registry, expert1.address, guid, bid=bid, mask=[True, True],
                                       verdicts=[True, True])

    eth_tester.mine_blocks(duration)

    reveal_assertion(bounty_registry, expert0.address, guid, index0, nonce0, [True, True], 'foo')
    reveal_assertion(bounty_registry, expert1.address, guid, index1, nonce1, [True, True], 'bar')

    eth_tester.mine_blocks(assertion_reveal_window)

    vote_on_bounty(bounty_registry, arbiter.address, guid, [True, True])

    eth_tester.mine_blocks(arbiter_vote_window)

    settle_bounty(bounty_registry, expert0.address, guid)
    settle_bounty(bounty_registry, expert1.address, guid)

    settle_bounty(bounty_registry, arbiter.address, guid)
    selected = BountyRegistry.functions.bountiesByGuid(guid).call()[6]
    assert selected != ZERO_ADDRESS

    # If we weren't the selected arbiter, call settle again with the selected one
    if selected != arbiter.address:
        settle_bounty(bounty_registry, selected, guid)

    assert NectarToken.functions.balanceOf(selected).call() == \
           STARTING_BALANCE - stake_amount + 2 * assertion_fee + bounty_fee


def test_payout_all_to_arbiter_if_every_expert_wrong(bounty_registry, eth_tester):
    NectarToken = bounty_registry.NectarToken
    BountyRegistry = bounty_registry.BountyRegistry

    ambassador = BountyRegistry.ambassadors[0]
    expert0 = BountyRegistry.experts[0]
    expert1 = BountyRegistry.experts[1]
    arbiter = BountyRegistry.arbiters[0]
    amount = 10 * 10 ** 18
    duration = 10
    bid = 20 * 10 ** 18

    bounty_fee = BountyRegistry.functions.bountyFee().call()
    assertion_fee = BountyRegistry.functions.assertionFee().call()
    assertion_reveal_window = BountyRegistry.functions.ASSERTION_REVEAL_WINDOW().call()
    stake_amount = BountyRegistry.stake_amount
    arbiter_vote_window = BountyRegistry.arbiter_vote_window

    guid, _ = post_bounty(bounty_registry, ambassador.address, amount=amount, num_artifacts=2, duration=duration)

    index0, nonce0, _ = post_assertion(bounty_registry, expert0.address, guid, bid=bid, mask=[True, True],
                                       verdicts=[False, False])
    index1, nonce1, _ = post_assertion(bounty_registry, expert1.address, guid, bid=bid, mask=[True, True],
                                       verdicts=[False, False])

    eth_tester.mine_blocks(duration)

    reveal_assertion(bounty_registry, expert0.address, guid, index0, nonce0, [False, False], 'foo')
    reveal_assertion(bounty_registry, expert1.address, guid, index1, nonce1, [False, False], 'bar')

    eth_tester.mine_blocks(assertion_reveal_window)

    vote_on_bounty(bounty_registry, arbiter.address, guid, [True, True])

    eth_tester.mine_blocks(arbiter_vote_window)

    settle_bounty(bounty_registry, expert0.address, guid)
    settle_bounty(bounty_registry, expert1.address, guid)

    settle_bounty(bounty_registry, arbiter.address, guid)
    selected = BountyRegistry.functions.bountiesByGuid(guid).call()[6]
    assert selected != ZERO_ADDRESS

    # If we weren't the selected arbiter, call settle again with the selected one
    if selected != arbiter.address:
        settle_bounty(bounty_registry, selected, guid)

    assert NectarToken.functions.balanceOf(selected).call() == \
           STARTING_BALANCE - stake_amount + 2 * bid + amount + 2 * assertion_fee + bounty_fee


def test_payout_so_arbiter_one_expert_profit_using_minimums(bounty_registry, eth_tester):
    NectarToken = bounty_registry.NectarToken
    BountyRegistry = bounty_registry.BountyRegistry

    ambassador = BountyRegistry.ambassadors[0]
    expert = BountyRegistry.experts[0]
    arbiter = BountyRegistry.arbiters[0]
    duration = 10

    amount_minimum = BountyRegistry.functions.BOUNTY_AMOUNT_MINIMUM().call()
    bid_minimum = BountyRegistry.functions.ASSERTION_BID_MINIMUM().call()
    assertion_reveal_window = BountyRegistry.functions.ASSERTION_REVEAL_WINDOW().call()
    stake_amount = BountyRegistry.stake_amount
    arbiter_vote_window = BountyRegistry.arbiter_vote_window

    guid, _ = post_bounty(bounty_registry, ambassador.address, amount=amount_minimum, num_artifacts=2,
                          duration=duration)

    index, nonce, _ = post_assertion(bounty_registry, expert.address, guid, bid=bid_minimum, mask=[True, True],
                                     verdicts=[True, True])

    eth_tester.mine_blocks(duration)

    reveal_assertion(bounty_registry, expert.address, guid, index, nonce, [True, True], 'foo')

    eth_tester.mine_blocks(assertion_reveal_window)

    vote_on_bounty(bounty_registry, arbiter.address, guid, [True, True])

    eth_tester.mine_blocks(arbiter_vote_window)

    settle_bounty(bounty_registry, ambassador.address, guid)
    settle_bounty(bounty_registry, expert.address, guid)

    settle_bounty(bounty_registry, arbiter.address, guid)
    selected = BountyRegistry.functions.bountiesByGuid(guid).call()[6]
    assert selected != ZERO_ADDRESS

    # If we weren't the selected arbiter, call settle again with the selected one
    if selected != arbiter.address:
        settle_bounty(bounty_registry, selected, guid)

    assert NectarToken.functions.balanceOf(expert.address).call() > STARTING_BALANCE
    assert NectarToken.functions.balanceOf(selected).call() > STARTING_BALANCE - stake_amount


def test_payout_so_arbiter_two_expert_profit_using_minimums(bounty_registry, eth_tester):
    NectarToken = bounty_registry.NectarToken
    BountyRegistry = bounty_registry.BountyRegistry

    ambassador = BountyRegistry.ambassadors[0]
    expert0 = BountyRegistry.experts[0]
    expert1 = BountyRegistry.experts[1]
    arbiter = BountyRegistry.arbiters[0]
    duration = 10

    amount_minimum = BountyRegistry.functions.BOUNTY_AMOUNT_MINIMUM().call()
    bid_minimum = BountyRegistry.functions.ASSERTION_BID_MINIMUM().call()
    assertion_reveal_window = BountyRegistry.functions.ASSERTION_REVEAL_WINDOW().call()
    stake_amount = BountyRegistry.stake_amount
    arbiter_vote_window = BountyRegistry.arbiter_vote_window

    guid, _ = post_bounty(bounty_registry, ambassador.address, amount=amount_minimum, num_artifacts=2,
                          duration=duration)

    index0, nonce0, _ = post_assertion(bounty_registry, expert0.address, guid, bid=bid_minimum, mask=[True, True],
                                       verdicts=[True, True])
    index1, nonce1, _ = post_assertion(bounty_registry, expert1.address, guid, bid=bid_minimum, mask=[True, True],
                                       verdicts=[False, False])

    eth_tester.mine_blocks(duration)

    reveal_assertion(bounty_registry, expert0.address, guid, index0, nonce0, [True, True], 'foo')
    reveal_assertion(bounty_registry, expert1.address, guid, index1, nonce1, [False, False], 'bar')

    eth_tester.mine_blocks(assertion_reveal_window)

    vote_on_bounty(bounty_registry, arbiter.address, guid, [True, True])

    eth_tester.mine_blocks(arbiter_vote_window)

    settle_bounty(bounty_registry, ambassador.address, guid)
    settle_bounty(bounty_registry, expert0.address, guid)
    settle_bounty(bounty_registry, expert1.address, guid)

    settle_bounty(bounty_registry, arbiter.address, guid)
    selected = BountyRegistry.functions.bountiesByGuid(guid).call()[6]
    assert selected != ZERO_ADDRESS

    # If we weren't the selected arbiter, call settle again with the selected one
    if selected != arbiter.address:
        settle_bounty(bounty_registry, selected, guid)

    assert NectarToken.functions.balanceOf(expert0.address).call() > STARTING_BALANCE
    assert NectarToken.functions.balanceOf(expert1.address).call() < STARTING_BALANCE
    assert NectarToken.functions.balanceOf(selected).call() > STARTING_BALANCE - stake_amount
