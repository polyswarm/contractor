pragma solidity ^0.5.0;

import "openzeppelin-solidity/contracts/access/roles/PauserRole.sol";
import "openzeppelin-solidity/contracts/ownership/Ownable.sol";
import "../access/roles/DeprecationRole.sol";

/**
 * @title Pausable
 * @dev Base contract which allows children to implement an emergency stop mechanism.
 */
contract Deprecatable is DeprecatorRole {
    event Deprecated();

    uint256 public deprecatedBlock;

    constructor () internal {
        deprecatedBlock = 0;
    }

    /** Function only callable when not deprecated */
    modifier whenNotDeprecated() {
        require(deprecatedBlock <= 0);
        _;
    }

    /**
     * Deprecate this contract
     * The contract disables new bounties, but allows other parts to function
     */
    function deprecate() external onlyDeprecator whenNotDeprecated {
        deprecatedBlock = block.number;
        emit Deprecated();
    }
}
