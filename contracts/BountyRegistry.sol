pragma solidity ^0.5.0;

import "openzeppelin-solidity/contracts/ownership/Ownable.sol";
import "openzeppelin-solidity/contracts/lifecycle/Pausable.sol";
import "openzeppelin-solidity/contracts/math/SafeMath.sol";
import "openzeppelin-solidity/contracts/token/ERC20/SafeERC20.sol";
import "./ArbiterStaking.sol";
import "./NectarToken.sol";
import "polyswarm/lifecycle/Deprecatable.sol";
import "polyswarm/access/roles/ArbiterRole.sol";
import "polyswarm/access/roles/FeeManagerRole.sol";
import "polyswarm/access/roles/WindowManagerRole.sol";


contract BountyRegistry is ArbiterRole, FeeManagerRole, WindowManagerRole, Deprecatable, Pausable, Ownable {
    using SafeMath for uint256;
    using SafeERC20 for NectarToken;

    string public constant VERSION = "1.5.0";

    enum ArtifactType {FILE, URL, _END}

    struct Bounty {
        uint128 guid;
        ArtifactType  artifactType;
        address author;
        string artifactURI;
        uint256 numArtifacts;
        uint256 expirationBlock;
        address assignedArbiter;
        bool quorumReached;
        uint256 quorumBlock;
        uint256 quorumMask;
        string metadata;
    }

    struct Assertion {
        address author;
        uint256 mask;
        uint256 commitment;
        uint256 nonce;
        uint256 verdicts;
        string metadata;
    }

    struct Vote {
        address author;
        uint256 votes;
        bool validBloom;
    }

    event NewBounty(
        uint128 guid,
        uint256 artifactType,
        address author,
        uint256[] amount,
        string artifactURI,
        uint256 expirationBlock,
        string metadata
    );

    event NewAssertion(
        uint128 bountyGuid,
        address author,
        uint256 index,
        uint256[] bid,
        uint256 mask,
        uint256 numArtifacts,
        uint256 commitment
    );

    event RevealedAssertion(
        uint128 bountyGuid,
        address author,
        uint256 index,
        uint256 nonce,
        uint256 verdicts,
        uint256 numArtifacts,
        string metadata
    );

    event NewVote(
        uint128 bountyGuid,
        uint256 votes,
        uint256 numArtifacts,
        address voter
    );

    event QuorumReached(
        uint128 bountyGuid
    );

    event SettledBounty(
        uint128 bountyGuid,
        address settler,
        uint256 payout
    );

    ArbiterStaking public staking;
    NectarToken internal token;

    uint256 public constant BOUNTY_AMOUNT_MINIMUM = 2000000000000000000; // Per artifact
    uint256 public constant ASSERTION_BID_ARTIFACT_MINIMUM = 62500000000000000; // Per artifact
    uint256 public constant ASSERTION_BID_ARTIFACT_MAXIMUM = 1000000000000000000; // Per artifact
    uint256 public constant DEFAULT_BOUNTY_FEE = 62500000000000000;
    uint256 public constant DEFAULT_ASSERTION_FEE = 31250000000000000;
    uint256 public constant MAX_DURATION = 100; // BLOCKS
    uint256 public constant VALID_HASH_PERIOD = 256; // number of blocks in the past you can still get a blockhash

    uint256 public bountyFee;
    uint256 public assertionFee;

    event FeesUpdated(
        uint256 bountyFee,
        uint256 assertionFee
    );

    event WindowsUpdated(
        uint256 assertionRevealWindow,
        uint256 arbiterVoteWindow
    );

    uint256 public arbiterVoteWindow;
    uint256 public assertionRevealWindow;
    uint128[] public bountyGuids;
    mapping(uint128 => Bounty) public bountiesByGuid;
    mapping(uint128 => uint256[]) public amountsByGuid;
    mapping(uint128 => Assertion[]) public assertionsByGuid;
    mapping(uint128 => uint256[][]) public assertionBidByGuid;
    mapping(uint128 => Vote[]) public votesByGuid;
    mapping(uint128 => uint256[8]) public bloomByGuid;
    mapping(uint128 => mapping(uint256 => uint256)) public quorumVotesByGuid;
    mapping(uint256 => mapping(uint256 => uint256)) public voteCountByGuid;
    mapping(uint256 => mapping(address => bool)) public arbiterVoteRegistryByGuid;
    mapping(uint256 => mapping(address => bool)) public expertAssertionRegistryByGuid;
    mapping(uint128 => mapping(address => bool)) public bountySettled;

    /**
     * Construct a new BountyRegistry
     *
     * @param _token address of NCT token to use
     */
    constructor(address _token, address _arbiterStaking, uint256 _arbiterVoteWindow, uint256 _assertionRevealWindow) Ownable() public {
        bountyFee = DEFAULT_BOUNTY_FEE;
        assertionFee = DEFAULT_ASSERTION_FEE;
        token = NectarToken(_token);
        staking = ArbiterStaking(_arbiterStaking);
        arbiterVoteWindow = _arbiterVoteWindow;
        assertionRevealWindow = _assertionRevealWindow;
    }


    /**
     * Set bounty fee in NCT
     *
     * @param newBountyFee The new bounty fee in NCT
     */
    function setBountyFee(uint256 newBountyFee) external onlyFeeManager {
        bountyFee = newBountyFee;
        emit FeesUpdated(bountyFee, assertionFee);
    }

    /**
     * Set assertion fee in NCT
     *
     * @param newAssertionFee The new assertion fee in NCT
     */
    function setAssertionFee(uint256 newAssertionFee) external onlyFeeManager {
        assertionFee = newAssertionFee;
        emit FeesUpdated(bountyFee, assertionFee);
    }

    /**
     * Set arbiter voting window in blocks
     *
     * @param newAssertionRevealWindow The new assertion reveal window in blocks
     * @param newArbiterVoteWindow The new arbiter voting window in blocks
     */
    function setWindows(uint256 newAssertionRevealWindow, uint256 newArbiterVoteWindow) external onlyWindowManager {
        arbiterVoteWindow = newArbiterVoteWindow;
        assertionRevealWindow = newAssertionRevealWindow;
        emit WindowsUpdated(assertionRevealWindow, arbiterVoteWindow);
    }

    /**
     * Get the number of 1 bits in a uint256
     * @param value some uint256 to count
     * @return number of set bits in the given value
     */
    function countBits(uint256 value) internal pure returns (uint256 result) {
        uint8[16] memory bits = [0, 1, 1, 2, 1, 2, 2, 3, 1, 2, 2, 3, 2, 3, 3, 4];
        result = 0;
        uint256 modified = value;
        if (value != 0) {
            for (uint256 i = 0; i < 64; i++) {
                result =  result.add(bits[modified & 0xf]);
                modified = modified >> 4;
            }
        }
    }

    /**
     * Get the bid value for the artifact at the given index of the bounty.
     * Uses the bid portion array, and mask to compute the correct index to read from.
     *
     * @param mask Mask of artifacts that have a bid
     * @param bid Array of bids for each artifact that matches with a set mask
     * @param index Index for the artifact in the verdicts/mask array
     * @return uin256 that represents the bid for a specific artifact

     */
    function getArtifactBid(uint256 mask, uint256[] memory bid, uint256 index) internal pure returns (uint256 value) {
        value = 0;
        if ((mask & (1 << index)) > 0) {
            // 256 is correct here, because we want to move the value at index off the page
            uint256 bidIndex = countBits(mask << (256 - index) >> (256 - index));
            value = bid[bidIndex];
        }
    }

    /**
     * Get the whole amount array for the given bounty
     * @param bountyGuid the guid for the requested bounty
     */
    function getAmounts(uint128 bountyGuid) external view returns (uint256[] memory amounts) {
        require(bountiesByGuid[bountyGuid].author != address(0), "");
        amounts = amountsByGuid[bountyGuid];
    }

    /**
     * Get the whole bid array for the given assertion
     * @param bountyGuid the guid of the bounty asserted on
     * @param assertionId the id of the assertion to retrieve
     */
    function getBids(uint128 bountyGuid, uint256 assertionId) external view returns (uint256[] memory bids) {
        require(bountiesByGuid[bountyGuid].author != address(0) && assertionBidByGuid[bountyGuid].length >= assertionId, "");
        bids = assertionBidByGuid[bountyGuid][assertionId];
    }

    /**
     * Function called by end users and ambassadors to post a bounty
     *
     * @param guid the guid of the bounty, must be unique
     * @param amount the amount of NCT to post as a reward
     * @param artifactURI uri of the artifacts comprising this bounty
     * @param durationBlocks duration of this bounty in blocks
     */
    function postBounty(
        uint128 guid,
        uint256 artifactType,
        uint256[] calldata amount,
        string calldata artifactURI,
        uint256 numArtifacts,
        uint256 durationBlocks,
        uint256[8] calldata bloom,
        string calldata metadata
    )
    external
    whenNotPaused
    whenNotDeprecated
    {
        // Check if a bounty with this GUID has already been initialized
        require(bountiesByGuid[guid].author == address(0), "GUID already in use");
        // Check that we have an amount per artifact
        require(amount.length == numArtifacts, "Amount must match numArtifacts");
        // Check that the artifact values are valid
        require(bytes(artifactURI).length > 0 && numArtifacts <= 256 && numArtifacts > 0 && uint256(ArtifactType._END) > artifactType, "Invalid artifact parameters");
        // Check that our duration is non-zero and less than or equal to the max
        require(durationBlocks > 0 && durationBlocks <= MAX_DURATION, "Invalid bounty duration");

        uint256 amount_sum = 0;
        for (uint i = 0; i < amount.length; i++) {
            // Check that our bounty amount is sufficient for each artifact
            require(amount[i] >= BOUNTY_AMOUNT_MINIMUM, "Amount below minimum");
            amount_sum = amount_sum.add(amount[i]);
        }

        // Assess fees and transfer bounty amount into escrow
        token.safeTransferFrom(msg.sender, address(this), amount_sum.add(bountyFee));

        bountiesByGuid[guid].guid = guid;
        bountiesByGuid[guid].artifactType = ArtifactType(artifactType);
        bountiesByGuid[guid].author = msg.sender;
        bountiesByGuid[guid].artifactURI = artifactURI;
        bountiesByGuid[guid].metadata = metadata;
        // Number of artifacts is submitted as part of the bounty, we have no
        // way to check how many exist in this IPFS resource. For an IPFS
        // resource with N artifacts, if numArtifacts < N only the first
        // numArtifacts artifacts are included in this bounty, if numArtifacts >
        // N then the last N - numArtifacts bounties are considered benign.
        bountiesByGuid[guid].numArtifacts = numArtifacts;
        bountiesByGuid[guid].expirationBlock = durationBlocks.add(block.number);

        bountyGuids.push(guid);

        amountsByGuid[guid] = amount;
        bloomByGuid[guid] = bloom;

        Bounty storage b = bountiesByGuid[guid];

        emit NewBounty(
            b.guid,
            uint256(b.artifactType),
            b.author,
            amount,
            b.artifactURI,
            b.expirationBlock,
            b.metadata
        );
    }

    /**
     * Function called by security experts to post an assertion on a bounty
     *
     * @param bountyGuid the guid of the bounty to assert on
     * @param bid array of amounts of NCT to bid on an artifact
     * @param mask the artifacts to assert on from the set in the bounty
     * @param commitment a commitment hash of the verdicts being asserted, equal
     *      to keccak256(verdicts ^ keccak256(nonce)) where nonce != 0
     */
    function postAssertion(
        uint128 bountyGuid,
        uint256[] calldata bid,
        uint256 mask,
        uint256 commitment
    )
        external
        whenNotPaused
    {
        // Check if this bounty has been initialized
        require(bountiesByGuid[bountyGuid].author != address(0), "Bounty not initialized");
        // Check if this bounty is active
        require(getCurrentRound(bountyGuid) == 0, "Bounty inactive");
        // Check if bid meets minimum value
        require(bid.length == countBits(mask), "Bid does not match mask count");
        // Check if the sender has already made an assertion
        require(expertAssertionRegistryByGuid[bountyGuid][msg.sender] == false, "Sender has already asserted");

        uint256 bid_sum = 0;
        for (uint i = 0; i < bid.length; i++) {
            require(bid[i] >= ASSERTION_BID_ARTIFACT_MINIMUM && bid[i] <= ASSERTION_BID_ARTIFACT_MAXIMUM, "Bid not between min & max");
            bid_sum = bid_sum.add(bid[i]);
        }

        // Assess fees and transfer bid amount into escrow
        token.safeTransferFrom(msg.sender, address(this), bid_sum.add(assertionFee));

        expertAssertionRegistryByGuid[bountyGuid][msg.sender] = true;

        Assertion memory a = Assertion(
            msg.sender,
            mask,
            commitment,
            0,
            0,
            ""
        );

        uint256 index = assertionsByGuid[bountyGuid].push(a) - 1;
        assertionBidByGuid[bountyGuid].push(bid);
        uint256 numArtifacts = bountiesByGuid[bountyGuid].numArtifacts;

        emit NewAssertion(
            bountyGuid,
            a.author,
            index,
            bid,
            a.mask,
            numArtifacts,
            a.commitment
        );
    }

    // https://ethereum.stackexchange.com/questions/4170/how-to-convert-a-uint-to-bytes-in-solidity
    function uint256_to_bytes(uint256 x) private pure returns (bytes memory b) {
        b = new bytes(32);
        // solium-disable-next-line security/no-inline-assembly
        assembly { mstore(add(b, 32), x) }
    }

    /**
     * Function called by security experts to reveal an assertion after bounty
     * expiration
     *
     * @param bountyGuid the guid of the bounty to assert on
     * @param assertionId the id of the assertion to reveal
     * @param nonce the nonce used to generate the commitment hash
     * @param verdicts the verdicts making up this assertion
     * @param metadata optional metadata to include in the assertion
     */
    function revealAssertion(
        uint128 bountyGuid,
        uint256 assertionId,
        uint256 nonce,
        uint256 verdicts,
        string calldata metadata
    )
        external
        whenNotPaused
    {
        // Check if this bounty has been initialized
        require(bountiesByGuid[bountyGuid].author != address(0), "Bounty not initialized");
        // Check that the bounty is no longer active
        require(getCurrentRound(bountyGuid) == 1, "Bounty not in reveal window");
        // Get numArtifacts to help decode all zero verdicts
        uint256 numArtifacts = bountiesByGuid[bountyGuid].numArtifacts;

        // Zero is defined as an invalid nonce
        require(nonce != 0, "Invalid nonce");

        // Check our id
        require(assertionId < assertionsByGuid[bountyGuid].length, "Invalid assertion ID");

        Assertion storage a = assertionsByGuid[bountyGuid][assertionId];
        require(a.author == msg.sender, "Incorrect assertion author");
        require(a.nonce == 0, "Bounty already revealed");

        // Check our commitment hash, by xor-ing verdicts with the hashed nonce
        // and the sender's address prevent copying assertions by submitting the
        // same commitment hash and nonce during the reveal round
        uint256 hashed_nonce = uint256(keccak256(uint256_to_bytes(nonce)));
        uint256 commitment = uint256(keccak256(uint256_to_bytes(verdicts ^ hashed_nonce ^ uint256(msg.sender))));
        require(commitment == a.commitment, "Commitment hash mismatch");

        a.nonce = nonce;
        a.verdicts = verdicts;
        a.metadata = metadata;

        emit RevealedAssertion(
            bountyGuid,
            a.author,
            assertionId,
            a.nonce,
            a.verdicts,
            numArtifacts,
            a.metadata
        );
    }

    /**
     * Function called by arbiter after bounty expiration to settle with their
     * ground truth determination and pay out assertion rewards
     *
     * @param bountyGuid the guid of the bounty to settle
     * @param votes bitset of votes representing ground truth for the
     *      bounty's artifacts
     */
    function voteOnBounty(
        uint128 bountyGuid,
        uint256 votes,
        bool validBloom
    )
        external
        onlyArbiter
        whenNotPaused
    {
        Bounty storage bounty = bountiesByGuid[bountyGuid];
        Vote[] storage bountyVotes = votesByGuid[bountyGuid];

        // Check if this bounty has been initialized
        require(bounty.author != address(0), "Bounty not initialized");
        // Check that this is the voting round
        uint256 round = getCurrentRound(bountyGuid);
        require(round == 2 || round == 3, "Bounty not in voting window");
        // Check to make sure arbiters can't double vote
        require(arbiterVoteRegistryByGuid[bountyGuid][msg.sender] == false, "Arbiter has already voted");

        Vote memory a = Vote(
            msg.sender,
            votes,
            validBloom
        );

        votesByGuid[bountyGuid].push(a);

        staking.recordBounty(msg.sender, bountyGuid, block.number);
        arbiterVoteRegistryByGuid[bountyGuid][msg.sender] = true;
        uint256 tempQuorumMask = 0;
        uint256 quorumCount = 0;
        mapping (uint256 => uint256) storage quorumVotes = quorumVotesByGuid[bountyGuid];
        for (uint256 i = 0; i < bounty.numArtifacts; i++) {
            if (bounty.quorumMask != 0 && (bounty.quorumMask & (1 << i) != 0)) {
                tempQuorumMask = tempQuorumMask.add(calculateMask(i, 1));
                quorumCount = quorumCount.add(1);
                continue;
            }

            if (votes & (1 << i) != 0) {
                quorumVotes[i] = quorumVotes[i].add(1);
            }

            uint256 benignVotes = bountyVotes.length.sub(quorumVotes[i]);
            uint256 maxBenignValue = arbiterCount.sub(quorumVotes[i]);
            uint256 maxMalValue = arbiterCount.sub(benignVotes);

            if (quorumVotes[i] >= maxBenignValue || benignVotes > maxMalValue) {
                tempQuorumMask = tempQuorumMask.add(calculateMask(i, 1));
                quorumCount = quorumCount.add(1);
            }
        }

        // set new mask
        bounty.quorumMask = tempQuorumMask;

        // check if all arbiters have voted or if we have quorum for all the artifacts
        if ((bountyVotes.length == arbiterCount || quorumCount == bounty.numArtifacts) && !bounty.quorumReached)  {
            bounty.quorumReached = true;
            bounty.quorumBlock = block.number.sub(bountiesByGuid[bountyGuid].expirationBlock);
            emit QuorumReached(bountyGuid);
        }

        emit NewVote(bountyGuid, votes, bounty.numArtifacts, msg.sender);
    }


    /**
    * Function to calculate the refund from a bounty
    * @param bounty bounty to calculate refund
    * @param assertionLength the length of assertions on this bounty
    * @param votesLength the length of votes on this bounty
    * @param totalAmount the sum of amount array for this bounty
    * @return refund given to ambassador
    */
    function calculateBountyRefund(Bounty storage bounty, uint256 assertionLength, uint256 votesLength, uint256 totalAmount) private view returns (uint256 bountyRefund) {
        bountyRefund = 0;
        if (assertionLength == 0 && votesLength == 0) {
            // Refund the bounty amount and fees to ambassador
            bountyRefund = totalAmount.add(bountyFee);
        } else if (assertionLength == 0) {
            // Refund the bounty amount ambassador
            bountyRefund = totalAmount;
        }
    }

    // This struct exists to move state from settleBounty into memory from stack
    // to avoid solidity limitations
    struct ArtifactPot {
        uint256 numWinners;
        uint256 numLosers;
        uint256 winnerPool;
        uint256 loserPool;
    }

    /**
    * Function to calculate the refund from a bounty, and expert rewards
    * @param bounty bounty to calculate rewards against
    * @param amount the amount array for this bounty
    * @param assertions the assertions on this bounty
    * @param assertionBids the bid arrays for each assertion
    * @param votes the votes on this bounty
    * @param quorumVotes the votes for each artifact for a malicious quorum
    * @return refund given to ambassador
    */
    function calculateExpertRewards(Bounty storage bounty, uint256[] storage amount, Assertion[] storage assertions, uint256[][] storage assertionBids, Vote[] storage votes, mapping (uint256 => uint256) storage quorumVotes) private view returns (uint256 bountyRefund, uint256[] memory expertRewards) {
        uint256[][] memory artifactBids = new uint256[][](bounty.numArtifacts);

        expertRewards = new uint256[](assertions.length);
        bountyRefund = 0;

        if(votes.length == 0) {
            bountyRefund = bountyFee;
            for (uint j = 0; j < assertions.length; j++) {
                expertRewards[j] = expertRewards[j].add(assertionFee);
                for (uint i = 0; i < assertionBids[j].length; i++) {
                        expertRewards[j] = amount[i].div(assertions.length).add(expertRewards[j]).add(assertionBids[j][i]);
                }
            }
        } else {
            for (uint i = 0; i < bounty.numArtifacts; i++) {
                ArtifactPot memory ap = ArtifactPot({numWinners: 0, numLosers: 0, winnerPool: 0, loserPool: 0});
                // Tie goes to malicious
                bool consensus = quorumVotes[i] >= votes.length.sub(quorumVotes[i]);
                artifactBids[i] = new uint256[](assertions.length);

                for (uint j = 0; j < assertions.length; j++) {
                    Assertion storage assertion = assertions[j];
                    artifactBids[i][j] = getArtifactBid(assertion.mask, assertionBids[j], i);
                    uint256 bid = artifactBids[i][j];
                    if (assertion.mask & (1 << i) > 0) {
                        // If they haven't revealed set to incorrect value
                        bool malicious = assertion.nonce == 0
                                ? !consensus
                                : (assertion.verdicts & assertion.mask) & (1 << i) > 0;

                        if (malicious == consensus) {
                            ap.numWinners = ap.numWinners.add(1);
                            ap.winnerPool = ap.winnerPool.add(bid);
                        } else {
                            ap.numLosers = ap.numLosers.add(1);
                            ap.loserPool = ap.loserPool.add(bid);
                        }
                    }
                }

                // If nobody asserted on this artifact, refund the ambassador
                if (ap.numWinners == 0 && ap.numLosers == 0) {
                    bountyRefund = amount[i].add(bountyRefund);
                } else {
                    for (uint j = 0; j < assertions.length; j++) {
                        uint256 reward = 0;
                        Assertion storage assertion = assertions[j];
                        if (assertion.mask & (1 << i) > 0) {
                            bool malicious = assertion.nonce == 0
                            ? !consensus
                            : (assertion.verdicts & assertion.mask) & (1 << i) != 0;
                            if (malicious == consensus) {
                                uint256 amount = amount[i];
                                uint256 bid = artifactBids[i][j];
                                reward = reward.add(bid);
                                // Take a portion of the losing bids
                                reward = bid.mul(ap.loserPool).div(ap.winnerPool).add(reward);
                                // Take a portion of the amount (for this artifact)
                                reward = bid.mul(amount).div(ap.winnerPool).add(reward);
                            }
                        }
                        expertRewards[j] = expertRewards[j].add(reward);
                    }
                }
            }
        }
    }

    /**
     * Function to calculate the reward rewards from a bounty
     *
     * @param bountyGuid the guid of the bounty to calculate
     * @return Rewards distributed by the bounty
     */
    function calculateBountyRewards(
        uint128 bountyGuid
    )
        private
        view
        returns (uint256 bountyRefund, uint256 arbiterReward, uint256[] memory expertRewards)
    {
        Bounty storage bounty = bountiesByGuid[bountyGuid];
        uint256[] storage amount = amountsByGuid[bountyGuid];
        Assertion[] storage assertions = assertionsByGuid[bountyGuid];
        uint256[][] storage assertionBids = assertionBidByGuid[bountyGuid];
        Vote[] storage votes = votesByGuid[bountyGuid];

        uint256 totalAmount = 0;
        for (uint i = 0; i < bounty.numArtifacts; i++) {
            totalAmount  = totalAmount.add(amount[i]);
        }

        // Calculate bounty refund
        bountyRefund = calculateBountyRefund(bounty, assertions.length, votes.length, totalAmount);
        // Calculate expertRewards
        if (bountyRefund == 0) {
            mapping (uint256 => uint256) storage quorumVotes = quorumVotesByGuid[bountyGuid];
            (bountyRefund, expertRewards) = calculateExpertRewards(bounty, amount, assertions, assertionBids, votes, quorumVotes);
        } else {
            expertRewards = new uint256[](assertions.length);
        }

        // Calculate rewards
        uint256 pot = assertionFee.mul(assertions.length).add(bountyFee).add(totalAmount);
        for (uint i = 0; i < assertions.length; i++) {
            uint256[] storage bids = assertionBids[i];
            for (uint j = 0; j < bids.length; j++) {
                pot = pot.add(bids[j]);
            }
        }

        pot = pot.sub(bountyRefund);
        for (uint i = 0; i < assertions.length; i++) {
            pot = pot.sub(expertRewards[i]);
        }
        arbiterReward = pot;
    }

    /**
     * Function called after window has closed to handle reward disbursal
     *
     * This function will pay out rewards if the the bounty has a super majority
     * @param bountyGuid the guid of the bounty to settle
     */
    function settleBounty(uint128 bountyGuid) external whenNotPaused {
        Bounty storage bounty = bountiesByGuid[bountyGuid];
        Assertion[] storage assertions = assertionsByGuid[bountyGuid];

        // Check if this bountiesByGuid[bountyGuid] has been initialized
        require(bounty.author != address(0), "Bounty not initialized");
        // Check if this bounty has been previously resolved for the sender
        require(!bountySettled[bountyGuid][msg.sender], "Sender already settled");
        // Check that the voting round has closed
        uint round = getCurrentRound(bountyGuid);
        require(round == 3 || round == 4, "No Quorum and vote active");

        if (isArbiter(msg.sender)) {
            require(round == 4, "Voting round still active");
            if (bounty.assignedArbiter == address(0)) {
                if (bounty.expirationBlock.add(assertionRevealWindow).add(arbiterVoteWindow).add(VALID_HASH_PERIOD) >= block.number) {
                    bounty.assignedArbiter = getWeightedRandomArbiter(bountyGuid);
                } else {
                    bounty.assignedArbiter = msg.sender;
                }
            }
        }

        uint256 payout = 0;
        uint256 bountyRefund;
        uint256 arbiterReward;
        uint256[] memory expertRewards;
        (bountyRefund, arbiterReward, expertRewards) = calculateBountyRewards(bountyGuid);

        bountySettled[bountyGuid][msg.sender] = true;

        // Disburse rewards
        if (bountyRefund != 0 && bounty.author == msg.sender) {
            token.safeTransfer(bounty.author, bountyRefund);
            payout = payout.add(bountyRefund);
        }

        for (uint i = 0; i < assertions.length; i++) {
            if (expertRewards[i] != 0 && assertions[i].author == msg.sender) {
                token.safeTransfer(assertions[i].author, expertRewards[i]);
                payout = payout.add(expertRewards[i]);
            }
        }

        if (arbiterReward != 0 && bounty.assignedArbiter == msg.sender) {
            token.safeTransfer(bounty.assignedArbiter, arbiterReward);
            payout = payout.add(arbiterReward);
        }

        emit SettledBounty(bountyGuid, msg.sender, payout);
    }

    /**
     *  Generates a random number from 0 to range based on the last block hash
     *
     *  @param seed random number for reproducing
     *  @param range end range for random number
     */
    function randomGen(uint256 targetBlock, uint seed, uint256 range) private view returns (int256) {
        return int256(uint256(keccak256(abi.encodePacked(blockhash(targetBlock), seed))) % range);
    }

    /**
     * Gets a random Arbiter weighted by the amount of Nectar they have
     *
     * @param bountyGuid the guid of the bounty
     */
    function getWeightedRandomArbiter(uint128 bountyGuid) private view returns (address voter) {
        require(bountiesByGuid[bountyGuid].author != address(0), "Bounty not initialized");

        Bounty memory bounty = bountiesByGuid[bountyGuid];
        Vote[] memory votes = votesByGuid[bountyGuid];
        voter = address(0);
        if (votes.length > 0) {
            uint256 sum = 0;
            int256 randomNum;
            uint256[] memory stakingBalances = new uint256[](votes.length);

            for (uint i = 0; i < votes.length; i++) {
                uint256 balance = staking.balanceOf(votes[i].author);
                stakingBalances[i] = balance;
                sum = sum.add(balance);
            }

            randomNum = randomGen(bounty.expirationBlock.add(assertionRevealWindow).add(arbiterVoteWindow), block.number, sum);

            for (uint i = 0; i < votes.length; i++) {
                randomNum -= int256(stakingBalances[i]);

                if (randomNum <= 0) {
                    voter = votes[i].author;
                    break;
                }
            }
        }
    }

    /**
     * Get the total number of bounties tracked by the contract
     * @return total number of bounties
     */
    function getNumberOfBounties() external view returns (uint256) {
        return bountyGuids.length;
    }

    /**
     * Get the current round for a bounty
     *
     * @param bountyGuid the guid of the bounty
     * @return the current round
     *      0 = assertions being accepted
     *      1 = assertions being revealed
     *      2 = arbiters voting
     *      3 = arbiters voting, and quorum reached
     *      4 = bounty finished
     */
    function getCurrentRound(uint128 bountyGuid) public view returns (uint256) {
        // Check if this bounty has been initialized
        require(bountiesByGuid[bountyGuid].author != address(0), "Bounty not initialized");

        Bounty memory bounty = bountiesByGuid[bountyGuid];

        if (bounty.expirationBlock > block.number) {
            return 0;
        } else if (bounty.expirationBlock.add(assertionRevealWindow) > block.number) {
            return 1;
        } else if (bounty.expirationBlock.add(assertionRevealWindow).add(arbiterVoteWindow) > block.number &&
                  !bounty.quorumReached) {
            return 2;
        } else if (bounty.expirationBlock.add(assertionRevealWindow).add(arbiterVoteWindow) > block.number) {
            return 3;
        } else {
            return 4;
        }
    }

    /**
     * Gets the number of assertions for a bounty
     *
     * @param bountyGuid the guid of the bounty
     * @return number of assertions for the given bounty
     */
    function getNumberOfAssertions(uint128 bountyGuid) external view returns (uint) {
        // Check if this bounty has been initialized
        require(bountiesByGuid[bountyGuid].author != address(0), "Bounty not initialized");

        return assertionsByGuid[bountyGuid].length;
    }

    /**
     * Gets the vote count for a specific bounty
     *
     * @param bountyGuid the guid of the bounty
     */
    function getNumberOfVotes(uint128 bountyGuid) external view returns (uint256) {
        require(bountiesByGuid[bountyGuid].author != address(0), "Bounty not initialized");

        return votesByGuid[bountyGuid].length;
    }

    /**
     * Gets all the voters for a specific bounty
     *
     * @param bountyGuid the guid of the bounty
     */
    function getVoters(uint128 bountyGuid) external view returns (address[] memory) {
        require(bountiesByGuid[bountyGuid].author != address(0), "Bounty not initialized");

        Vote[] memory votes = votesByGuid[bountyGuid];
        uint count = votes.length;

        address[] memory voters = new address[](count);

        for (uint i = 0; i < count; i++) {
            voters[i] = votes[i].author;
        }

        return voters;
    }

    /** Candidate for future arbiter */
    struct Candidate {
        address addr;
        uint256 count;
    }

    /**
     * View function displays most active bounty posters over past
     * ARBITER_LOOKBACK_RANGE bounties to select future arbiters
     *
     * @return sorted array of most active bounty posters
     */
    function getArbiterCandidates() external view returns (address[] memory) {
        require(bountyGuids.length > 0, "No bounties have been placed");

        uint256 count = 0;
        Candidate[] memory candidates = new Candidate[](ARBITER_LOOKBACK_RANGE);

        uint256 lastBounty = 0;
        if (bountyGuids.length > ARBITER_LOOKBACK_RANGE) {
            lastBounty = bountyGuids.length.sub(ARBITER_LOOKBACK_RANGE);
        }

        for (uint i = bountyGuids.length; i > lastBounty; i--) {
            address addr = bountiesByGuid[bountyGuids[i.sub(1)]].author;
            bool found = false;
            for (uint j = 0; j < count; j++) {
                if (candidates[j].addr == addr) {
                    candidates[j].count = candidates[j].count.add(1);
                    found = true;
                    break;
                }
            }

            if (!found) {
                candidates[count] = Candidate(addr, 1);
                count = count.add(1);
            }
        }

        address[] memory ret = new address[](count);

        for (uint i = 0; i < ret.length; i++) {
            uint256 next = 0;
            uint256 value = candidates[0].count;

            for (uint j = 0; j < count; j++) {
                if (candidates[j].count > value) {
                    next = j;
                    value = candidates[j].count;
                }
            }

            ret[i] = candidates[next].addr;
            candidates[next] = candidates[count.sub(1)];
            count = count.sub(1);
        }

        return ret;
    }

    function calculateMask(uint256 i, uint256 b) private pure returns(uint256) {
        if (b != 0) {
            return 1 << i;
        }

        return 0;
    }

    /**
     * View function displays the most active bounty voters over past
     * ARBITER_LOOKBACK_RANGE bounties to select future arbiters
     *
     * @return a sorted array of most active bounty voters and a boolean array of whether
     * or not they were active in 90% of bounty votes
     */

    function getActiveArbiters() external view returns (address[] memory, bool[] memory) {
        require(bountyGuids.length > 0, "No bounties have been placed");
        uint256 count = 0;
        uint256 threshold = bountyGuids.length.div(10).mul(9);
        address[] memory ret_addr = new address[](count);
        bool[] memory ret_arbiter_ativity_threshold = new bool[](count);

        Candidate[] memory candidates = new Candidate[](ARBITER_LOOKBACK_RANGE);

        uint256 lastBounty = 0;

        if (bountyGuids.length > ARBITER_LOOKBACK_RANGE) {
            lastBounty = bountyGuids.length.sub(ARBITER_LOOKBACK_RANGE);
            threshold = lastBounty.div(10).mul(9);
        }

        for (uint i = bountyGuids.length.sub(1); i > lastBounty; i--) {
            Vote[] memory votes = votesByGuid[bountyGuids[i]];

            for (uint j = 0; j < votes.length; j++) {
                bool found = false;
                address addr = votes[j].author;

                for (uint256 k = 0; k < count; k++) {
                    if (candidates[k].addr == addr) {
                        candidates[k].count = candidates[k].count.add(1);
                        found = true;
                        break;
                    }
                }

                if (!found) {
                    candidates[count] = Candidate(addr, 1);
                    count = count.add(1);
                }

            }

        }


        for (uint i = 0; i < ret_addr.length; i++) {
            uint256 next = 0;
            uint256 value = candidates[0].count;

            for (uint j = 0; j < count; j++) {
                if (candidates[j].count > value) {
                    next = j;
                    value = candidates[j].count;
                }
            }

            ret_addr[i] = candidates[next].addr;
            ret_arbiter_ativity_threshold[i] = candidates[next].count.div(10).mul(9) >= threshold;

            count = count.sub(1);
            candidates[next] = candidates[count];
        }

        return (ret_addr, ret_arbiter_ativity_threshold);
    }
}
