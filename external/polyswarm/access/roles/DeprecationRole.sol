pragma solidity ^0.5.0;

import "openzeppelin-solidity/contracts/access/Roles.sol";

contract DeprecatorRole {
    using Roles for Roles.Role;

    event DeprecatorAdded(address indexed account);
    event DeprecatorRemoved(address indexed account);

    Roles.Role private _deprecators;

    constructor () internal {
        _addDeprecator(msg.sender);
    }

    modifier onlyDeprecator() {
        require(isDeprecator(msg.sender));
        _;
    }

    function isDeprecator(address account) public view returns (bool) {
        return _deprecators.has(account);
    }

    function addDeprecator(address account) public onlyDeprecator {
        _addDeprecator(account);
    }

    function renounceDeprecator() public {
        _removeDeprecator(msg.sender);
    }

    function _addDeprecator(address account) internal {
        _deprecators.add(account);
        emit DeprecatorAdded(account);
    }

    function _removeDeprecator(address account) internal {
        _deprecators.remove(account);
        emit DeprecatorRemoved(account);
    }
}
