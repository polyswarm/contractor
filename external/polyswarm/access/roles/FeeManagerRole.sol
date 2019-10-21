pragma solidity ^0.5.0;


contract FeeManagerRole {

    event NewFeeManager(
        address indexed previousManager,
        address indexed newManager
    );

    address private _feeManager;

    constructor () internal {
        _feeManager = msg.sender;
    }

        /** Function only callable by fee manager */
    modifier onlyFeeManager() {
        require(_feeManager == msg.sender, "Sender is not FeeManager");
        _;
    }

        /**
     * Set account which can update fees
     *
     * @param newFeeManager The new fee manager
     */
    function setFeeManager(address newFeeManager) external onlyFeeManager {
        address old = _feeManager;
        _feeManager = newFeeManager;
        emit NewFeeManager(old, _feeManager);
    }
}
