pragma solidity ^0.5.0;


contract VerifierManagerRole {
    event NewVerifierManager(
        address indexed previousManager,
        address indexed newManager
    );

    address private _verifierManager;

    constructor () internal {
        _verifierManager = msg.sender;
    }

    /** Function only callable by fee manager */
    modifier onlyVerifierManager() {
        require(_verifierManager == msg.sender);
        _;
    }

    /**
     * Set account which can update fees
     *
     * @param newVerifierManager The new fee manager
     */
    function setVerifierManager(address newVerifierManager) external onlyVerifierManager {
        address old = _verifierManager;
        _verifierManager = newVerifierManager;
        emit NewVerifierManager(old, _verifierManager);
    }
}
