pragma solidity ^0.5.0;

import "contracts/BountyRegistry.sol";


contract TestBountyRegistry is BountyRegistry {

    constructor(address _token, address _arbiterStaking, uint256 _arbiterVoteWindow, uint256 _assertionRevealWindow)
        BountyRegistry(_token, _arbiterStaking, _arbiterVoteWindow, _assertionRevealWindow)  public {

    }

    function testCountBits(uint256 value) external pure returns (uint256 result) {
        result = countBits(value);
    }

    function testGetArtifactBid(uint256 mask, uint256[] calldata bid, uint256 index) external pure returns (uint256 value) {
        value = getArtifactBid(mask, bid, index);
    }
}
