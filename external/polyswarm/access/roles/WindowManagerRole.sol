pragma solidity ^0.5.0;


contract WindowManagerRole {

    event NewWindowManager(
        address indexed previousManager,
        address indexed newManager
    );

    address private _windowManager;

    constructor () internal {
        _windowManager = msg.sender;
    }

    /** Function only callable by fee manager */
    modifier onlyWindowManager() {
        require(_windowManager == msg.sender);
        _;
    }

        /**
     * Set account which can update fees
     *
     * @param newWindowManager The new fee manager
     */
    function setWindowManager(address newWindowManager) external onlyWindowManager {
        address old = _windowManager;
        _windowManager = newWindowManager;
        emit NewWindowManager(old, _windowManager);
    }
}
