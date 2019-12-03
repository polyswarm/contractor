pragma solidity ^0.5.0;

import "openzeppelin-solidity/contracts/access/roles/PauserRole.sol";
import "openzeppelin-solidity/contracts/ownership/Ownable.sol";
import "../access/roles/DeprecatorRole.sol";

/**
 * @title Pausable
 * @dev Base contract which allows children to implement an emergency stop mechanism.
 */
contract Deprecatable is DeprecatorRole {
    event Deprecated(
        bool rollover
    );
    event Undeprecated();

    uint256 public deprecatedBlock;
    bool public rollover;

    constructor () internal {
        deprecatedBlock = 0;
        rollover = false;
    }

    /** Function only callable when not deprecated */
    modifier whenNotDeprecated() {
        require(deprecatedBlock <= 0);
        _;
    }

    /** Function only callable when deprecated */
    modifier whenDeprecated() {
        require(deprecatedBlock > 0);
        _;
    }

    /**
     * Deprecate this contract
     * The contract disables new bounties, but allows other parts to function
     */
    function deprecate(bool _rollover) external onlyDeprecator whenNotDeprecated {
        deprecatedBlock = block.number;
        rollover = _rollover;
        emit Deprecated(rollover);
    }

    /**
     * Undo deprecate om this contract
     * The re-enables anything disabled by deprecation
     */
    function undeprecate() external onlyDeprecator whenDeprecated {
        deprecatedBlock = block.number;
        rollover = false;
        emit Undeprecated();
    }
}
