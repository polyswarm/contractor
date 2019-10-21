pragma solidity ^0.5.0;

import "openzeppelin-solidity/contracts/access/Roles.sol";

contract ArbiterManagerRole {
    using Roles for Roles.Role;

    event ArbiterManagerAdded(address indexed account);
    event ArbiterManagerRemoved(address indexed account);

    Roles.Role private _arbiterManagers;

    constructor () internal {
        _addArbiterManager(msg.sender);
    }

    modifier onlyArbiterManager() {
        require(isArbiterManager(msg.sender));
        _;
    }

    function isArbiterManager(address account) public view returns (bool) {
        return _arbiterManagers.has(account);
    }

    function addArbiterManager(address account) public onlyArbiterManager {
        _addArbiterManager(account);
    }

    function renounceArbiterManager() public {
        _removeArbiterManager(msg.sender);
    }

    function _addArbiterManager(address account) internal {
        _arbiterManagers.add(account);
        emit ArbiterManagerAdded(account);
    }

    function _removeArbiterManager(address account) internal {
        _arbiterManagers.remove(account);
        emit ArbiterManagerRemoved(account);
    }
}
