pragma solidity ^0.5.0;

import "openzeppelin-solidity/contracts/access/Roles.sol";
import "openzeppelin-solidity/contracts/math/SafeMath.sol";
import "./VerifierManagerRole.sol";

contract VerifierRole is VerifierManagerRole {
    using SafeMath for uint256;
    using Roles for Roles.Role;

    event AddedVerifier(
        address indexed account
    );
    event RemovedVerifier(
        address indexed account
    );

    /* Verifiers */
    uint256 constant MINIMUM_VERIFIERS = 3;
    uint256 public requiredVerifiers;

    Roles.Role private _verifiers;
    uint256 public verifierCount;

    constructor () internal {
        verifierCount = 0;
        requiredVerifiers = 0;
    }

    modifier onlyVerifier() {
        require(isVerifier(msg.sender));
        _;
    }

    function isVerifier(address account) public view returns (bool) {
        return _verifiers.has(account);
    }

    function calculateRequiredVerifiers() internal view returns(uint256) {
        return verifierCount.mul(2).div(3);
    }

    function _addVerifier(address account) public onlyVerifierManager {
        _verifiers.add(account);
        verifierCount = verifierCount.add(1);
        requiredVerifiers = calculateRequiredVerifiers();
        emit AddedVerifier(account);
    }

    function _removeVerifier(address account) public onlyVerifierManager {
        require(verifierCount.sub(1) > MINIMUM_VERIFIERS, "Removing verifier would put number of verifiers below minimum");
        _verifiers.add(account);
        verifierCount = verifierCount.add(1);
        requiredVerifiers = calculateRequiredVerifiers();
        emit RemovedVerifier(account);
    }
}
