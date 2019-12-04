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

    Roles.Role internal verifiers;
    uint256 public verifierCount;

    constructor(address[] memory _verifiers) internal {
        require(_verifiers.length >= MINIMUM_VERIFIERS, "Number of verifiers less than minimum");
        verifierCount = _verifiers.length;
        requiredVerifiers = _verifiers.length.mul(2).div(3);
        for (uint256 i = 0; i < _verifiers.length; i++) {
            verifiers.add(_verifiers[i]);
        }
    }

    modifier onlyVerifier() {
        require(isVerifier(msg.sender));
        _;
    }

    function isVerifier(address account) public view returns (bool) {
        return verifiers.has(account);
    }

    function calculateRequiredVerifiers() internal view returns(uint256) {
        return verifierCount.mul(2).div(3);
    }

    function _addVerifier(address account) public onlyVerifierManager {
        verifiers.add(account);
        verifierCount = verifierCount.add(1);
        requiredVerifiers = calculateRequiredVerifiers();
        emit AddedVerifier(account);
    }

    function _removeVerifier(address account) public onlyVerifierManager {
        require(verifierCount.sub(1) >= MINIMUM_VERIFIERS, "Removing verifier would put number of verifiers below minimum");
        verifiers.remove(account);
        verifierCount = verifierCount.sub(1);
        requiredVerifiers = calculateRequiredVerifiers();
        emit RemovedVerifier(account);
    }
}
