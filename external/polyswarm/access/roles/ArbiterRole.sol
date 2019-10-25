pragma solidity ^0.5.0;

import "openzeppelin-solidity/contracts/access/Roles.sol";
import "openzeppelin-solidity/contracts/math/SafeMath.sol";
import "./ArbiterManagerRole.sol";

contract ArbiterRole is ArbiterManagerRole {
    using SafeMath for uint256;
    using Roles for Roles.Role;

    event AddedArbiter(
        address indexed account,
        uint256 blockNumber
    );
    event RemovedArbiter(
        address indexed account,
        uint256 blockNumber
    );

    uint256 public constant ARBITER_LOOKBACK_RANGE = 100;

    Roles.Role private _arbiters;
    uint256 public arbiterCount;

    constructor () internal {
        arbiterCount = 0;
    }

    modifier onlyArbiter() {
        require(isArbiter(msg.sender));
        _;
    }

    function isArbiter(address account) public view returns (bool) {
        return _arbiters.has(account);
    }

    function addArbiter(address account, uint256 blockNumber) public onlyArbiterManager {
        _arbiters.add(account);
        arbiterCount = arbiterCount.add(1);
        emit AddedArbiter(account, blockNumber);
    }

    function removeArbiter(address account, uint256 blockNumber) public onlyArbiterManager {
        _arbiters.remove(account);
        arbiterCount = arbiterCount.sub(1);
        emit RemovedArbiter(account, blockNumber);
    }
}
