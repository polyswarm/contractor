pragma solidity ^0.5.0;

import "openzeppelin-solidity/contracts/ownership/Ownable.sol";
import "openzeppelin-solidity/contracts/math/SafeMath.sol";
import "openzeppelin-solidity/contracts/token/ERC20/ERC20.sol";
import "openzeppelin-solidity/contracts/token/ERC20/SafeERC20.sol";
import "external/polyswarm/access/roles/FeeManagerRole.sol";
import "external/polyswarm/access/roles/VerifierRole.sol";

contract ERC20Relay is FeeManagerRole, VerifierRole, Ownable {
    using SafeMath for uint256;
    using SafeERC20 for ERC20;

    string public constant VERSION = "1.2.0";

    event AnchoredBlock(
        bytes32 indexed blockHash,
        uint256 indexed blockNumber
    );
    event ContestedBlock(
        bytes32 indexed blockHash,
        uint256 indexed blockNumber
    );
    event Flush();
    event FeesChanged(
        uint256 newFees
    );
    event WithdrawalProcessed(
        address indexed destination,
        uint256 amount,
        bytes32 txHash,
        bytes32 blockHash,
        uint256 blockNumber
    );

    struct Withdrawal {
        address destination;
        uint256 amount;
        bool processed;
    }

    /* Sidechain anchoring */
    struct Anchor {
        bytes32 blockHash;
        uint256 blockNumber;
        bool processed;
    }

    /* Withdrawals */
    uint256 constant GAS_PRICE = 20 * 10 ** 9;
    uint256 constant ESTIMATED_GAS_PER_VERIFIER = 54301;
    uint256 constant ESTIMATED_GAS_PER_WITHDRAWAL= 73458;
    uint256 public nctEthExchangeRate;
    uint256 public fees;
    address public feeWallet;
    uint256 public flushBlock;
    mapping (bytes32 => Withdrawal) public withdrawals;
    mapping (bytes32 => address[]) public withdrawalApprovals;

    /* Anchors */
    Anchor[] public anchors;
    mapping (bytes32 => address[]) public anchorApprovals;

    ERC20 private token;

    constructor(address _token, uint256 _nctEthExchangeRate, address _feeWallet, address[] memory _verifiers) VerifierRole(_verifiers) Ownable() public {
        require(_token != address(0), "Invalid token address");
        nctEthExchangeRate = _nctEthExchangeRate;
        fees = calculateFees();

        token = ERC20(_token);
        feeWallet = _feeWallet;
        flushBlock = 0;
    }

    /** Disable usage of the fallback function */
    function () external payable {
        revert("Do not allow sending Eth to this contract");
    }

    /**
     * Triggers a Flush event.
     * If called on a sidechain, this will trigger relay to withdrawal all funds out of the homechain contract
     */
    function flush() external onlyOwner {
        require(flushBlock == 0, "Contract already flushed");
        flushBlock = block.number;
        emit Flush();
    }

    function setNctEthExchangeRate(uint256 _nctEthExchangeRate) external onlyFeeManager {
        nctEthExchangeRate = _nctEthExchangeRate;
        fees = calculateFees();

        emit FeesChanged(fees);
    }

    function calculateFees() private view returns (uint256) {
        uint256 estimatedGas = ESTIMATED_GAS_PER_VERIFIER.mul(verifierCount)
            .add(ESTIMATED_GAS_PER_WITHDRAWAL);
        return estimatedGas.mul(GAS_PRICE).mul(nctEthExchangeRate);
    }

    function addVerifier(address account) public onlyVerifierManager {
        _addVerifier(account);
        fees = calculateFees();
    }

    function removeVerifier(address account) public onlyVerifierManager {
        _removeVerifier(account);
        fees = calculateFees();
    }

    function approveWithdrawal(
        address destination,
        uint256 amount,
        bytes32 txHash,
        bytes32 blockHash,
        uint256 blockNumber
    )
        external
        onlyVerifier
    {
        require(destination != address(0), "Invalid destination address");
        require((destination == feeWallet && amount > 0) || amount > fees, "Withdrawal amount is less than or equal to fees");
        require(flushBlock == 0, "Contract is flushed, cannot withdraw");

        bytes32 hash = keccak256(abi.encodePacked(txHash, blockHash, blockNumber));
        uint256 net = destination != feeWallet ? amount.sub(fees) : amount;

        if (withdrawals[hash].destination == address(0)) {
            withdrawals[hash] = Withdrawal(destination, net, false);
        }

        Withdrawal storage w = withdrawals[hash];
        address[] storage approvals = withdrawalApprovals[hash];
        require(w.destination == destination, "Destination mismatch");
        require(w.amount == net, "Amount mismatch");


        for (uint256 i = 0; i < approvals.length; i++) {
            require(approvals[i] != msg.sender, "Already approved withdrawal");
        }

        approvals.push(msg.sender);

        if (approvals.length >= requiredVerifiers && !w.processed) {
            if (fees != 0 && feeWallet != address(0) && destination != feeWallet) {
                token.safeTransfer(feeWallet, fees);
            }

            // Two cases here
            // First We require that amount > fees therefore net > 0
            // Second if destination is feeWallet, then we required amount > 0, therefore net > 0
            token.safeTransfer(destination, net);

            w.processed = true;
            emit WithdrawalProcessed(destination, net, txHash, blockHash, blockNumber);
        }
    }

    // Allow verifiers to retract their withdrawals in the case of a chain
    // reorganization. This shouldn't happen but is possible.
    function unapproveWithdrawal(
        bytes32 txHash,
        bytes32 blockHash,
        uint256 blockNumber
    )
        external
        onlyVerifier
    {
        bytes32 hash = keccak256(abi.encodePacked(txHash, blockHash, blockNumber));
        require(withdrawals[hash].destination != address(0), "No such withdrawal");

        Withdrawal storage w = withdrawals[hash];
        address[] storage approvals = withdrawalApprovals[hash];
        require(!w.processed, "Withdrawal already processed");

        uint256 length = approvals.length;
        for (uint256 i = 0; i < length; i++) {
            if (approvals[i] == msg.sender) {
                approvals[i] = approvals[length.sub(1)];
                delete approvals[length.sub(1)];
                approvals.length = approvals.length.sub(1);
                break;
            }
        }
    }

    function anchor(bytes32 blockHash, uint256 blockNumber) external onlyVerifier {
        // solium-disable-next-line operator-whitespace
        if (anchors.length == 0 ||
            anchors[anchors.length.sub(1)].blockHash != blockHash ||
            anchors[anchors.length.sub(1)].blockNumber != blockNumber) {
            // Emit event to alert the last anchor was never confirmed

            if (anchors.length > 0 && !anchors[anchors.length.sub(1)].processed) {
                Anchor storage last = anchors[anchors.length.sub(1)];
                emit ContestedBlock(last.blockHash, last.blockNumber);
            }
            anchors.push(Anchor(blockHash, blockNumber, false));
        }

        bytes32 hash = keccak256(abi.encodePacked(blockHash, blockNumber));
        Anchor storage a = anchors[anchors.length.sub(1)];
        address[] storage approvals = anchorApprovals[hash];
        require(a.blockHash == blockHash, "Block hash mismatch");
        require(a.blockNumber == blockNumber, "Block number mismatch");

        for (uint256 i = 0; i < approvals.length; i++) {
            require(approvals[i] != msg.sender, "Already approved anchor block");
        }

        approvals.push(msg.sender);
        if (approvals.length >= requiredVerifiers && !a.processed) {
            a.processed = true;
            emit AnchoredBlock(blockHash, blockNumber);
        }
    }

    function unanchor() external onlyVerifier {
        Anchor storage a = anchors[anchors.length.sub(1)];
        require(!a.processed, "Block anchor already processed");

        bytes32 hash = keccak256(abi.encodePacked(a.blockHash, a.blockNumber));
        address[] storage approvals = anchorApprovals[hash];

        uint256 length = approvals.length;
        for (uint256 i = 0; i < length; i++) {
            if (approvals[i] == msg.sender) {
                approvals[i] = approvals[length.sub(1)];
                delete approvals[length.sub(1)];
                approvals.length = approvals.length.sub(1);
                break;
            }
        }
    }
}
