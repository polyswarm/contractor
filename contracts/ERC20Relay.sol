pragma solidity ^0.5.0;

import "openzeppelin-solidity/contracts/ownership/Ownable.sol";
import "openzeppelin-solidity/contracts/math/SafeMath.sol";
import "openzeppelin-solidity/contracts/token/ERC20/ERC20.sol";
import "openzeppelin-solidity/contracts/token/ERC20/SafeERC20.sol";

contract ERC20Relay is Ownable {
    using SafeMath for uint256;
    using SafeERC20 for ERC20;

    string public constant VERSION = "1.2.0";

    /* Managers */
    address public verifierManager;
    address public feeManager;

    event NewVerifierManager(
        address indexed previousManager,
        address indexed newManager
    );
    event NewFeeManager(
        address indexed previousManager,
        address indexed newManager
    );
    event Flush(
        address indexed erc20Relay
    );

    /* Verifiers */
    uint256 constant MINIMUM_VERIFIERS = 3;
    uint256 public requiredVerifiers;
    address[] private verifiers;
    mapping (address => uint256) private verifierAddressToIndex;

    /* Withdrawals */
    uint256 constant GAS_PRICE = 20 * 10 ** 9;
    uint256 constant ESTIMATED_GAS_PER_VERIFIER = 54301;
    uint256 constant ESTIMATED_GAS_PER_WITHDRAWAL= 73458;
    uint256 public nctEthExchangeRate;
    uint256 public fees;
    address public feeWallet;
    uint256 public flushBlock;

    struct Withdrawal {
        address destination;
        uint256 amount;
        bool processed;
    }

    mapping (bytes32 => Withdrawal) public withdrawals;
    mapping (bytes32 => address[]) public withdrawalApprovals;

    event WithdrawalProcessed(
        address indexed destination,
        uint256 amount,
        bytes32 txHash,
        bytes32 blockHash,
        uint256 blockNumber
    );

    event FeesChanged(
        uint256 newFees
    );

    /* Sidechain anchoring */
    struct Anchor {
        bytes32 blockHash;
        uint256 blockNumber;
        bool processed;
    }

    Anchor[] public anchors;
    mapping (bytes32 => address[]) public anchorApprovals;

    event AnchoredBlock(
        bytes32 indexed blockHash,
        uint256 indexed blockNumber
    );

    event ContestedBlock(
        bytes32 indexed blockHash,
        uint256 indexed blockNumber
    );

    ERC20 private token;

    constructor(address _token, uint256 _nctEthExchangeRate, address _feeWallet, address[] memory _verifiers) public {
        require(_token != address(0), "Invalid token address");
        require(_verifiers.length >= MINIMUM_VERIFIERS, "Number of verifiers less than minimum");

        // If set to address(0), onlyVerifierManager and onlyFeeManager are equivalent to onlyOwner
        verifierManager = address(0);
        feeManager = address(0);

        // Dummy verifier at index 0
        verifiers.push(address(0));

        for (uint256 i = 0; i < _verifiers.length; i++) {
            verifiers.push(_verifiers[i]);
            verifierAddressToIndex[_verifiers[i]] = i.add(1);
        }

        requiredVerifiers = calculateRequiredVerifiers();

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

    modifier onlyVerifierManager() {
        if (verifierManager == address(0)) {
            require(msg.sender == owner(), "Not a verifier manager");
        } else {
            require(msg.sender == verifierManager, "Not a verifier manager");
        }
        _;
    }

    function setVerifierManager(address newVerifierManager) external onlyOwner {
        emit NewVerifierManager(verifierManager, newVerifierManager);
        verifierManager = newVerifierManager;
    }

    modifier onlyFeeManager() {
        if (feeManager == address(0)) {
            require(msg.sender == owner(), "Not a fee manager");
        } else {
            require(msg.sender == feeManager, "Not a fee manager");
        }
        _;
    }

    function setFeeManager(address newFeeManager) external onlyOwner {
        emit NewFeeManager(feeManager, newFeeManager);
        feeManager = newFeeManager;
    }

    /**
     * Triggers a Flush event.
     * If called on a sidechain, this will trigger relay to withdrawal all funds out of the homechain contract
     */
    function flush() external onlyOwner {
        require(flushBlock == 0, "Contract already flushed");
        flushBlock = block.number;
        emit Flush(address(this));
    }

    function addVerifier(address addr) external onlyVerifierManager {
        require(addr != address(0), "Invalid verifier address");
        require(verifierAddressToIndex[addr] == 0, "Address is already a verifier");

        uint256 index = verifiers.push(addr);
        verifierAddressToIndex[addr] = index.sub(1);

        requiredVerifiers = calculateRequiredVerifiers();
        fees = calculateFees();
    }

    function removeVerifier(address addr) external onlyVerifierManager {
        require(addr != address(0), "Invalid verifier address");
        require(verifierAddressToIndex[addr] != 0, "Address is not a verifier");
        require(verifiers.length.sub(1) > MINIMUM_VERIFIERS, "Removing verifier would put number of verifiers below minimum");

        uint256 index = verifierAddressToIndex[addr];
        require(verifiers[index] == addr, "Verifier address not present in verifiers array");
        verifiers[index] = verifiers[verifiers.length.sub(1)];
        verifierAddressToIndex[verifiers[verifiers.length.sub(1)]] = index;
        delete verifierAddressToIndex[addr];
        verifiers.length = verifiers.length.sub(1);

        requiredVerifiers = calculateRequiredVerifiers();
        fees = calculateFees();
    }

    function activeVerifiers() public view returns (address[] memory) {
        require(verifiers.length > 0, "Invalid number of verifiers");

        address[] memory ret = new address[](verifiers.length.sub(1));

        // Skip dummy verifier at index 0
        for (uint256 i = 1; i < verifiers.length; i++) {
            ret[i.sub(1)] = verifiers[i];
        }

        return ret;
    }

    function numberOfVerifiers() public view returns (uint256) {
        require(verifiers.length > 0, "Invalid number of verifiers");
        return verifiers.length.sub(1);
    }

    function calculateRequiredVerifiers() internal view returns(uint256) {
        return numberOfVerifiers().mul(2).div(3);
    }

    function isVerifier(address addr) public view returns (bool) {
        return verifierAddressToIndex[addr] != 0 && verifiers[verifierAddressToIndex[addr]] == addr;
    }

    modifier onlyVerifier() {
        require(isVerifier(msg.sender), "msg.sender is not verifier");
        _;
    }

    function setNctEthExchangeRate(uint256 _nctEthExchangeRate) external onlyFeeManager {
        nctEthExchangeRate = _nctEthExchangeRate;
        fees = calculateFees();

        emit FeesChanged(fees);
    }

    function calculateFees() internal view returns (uint256) {
        uint256 estimatedGas = ESTIMATED_GAS_PER_VERIFIER.mul(numberOfVerifiers())
            .add(ESTIMATED_GAS_PER_WITHDRAWAL);
        return estimatedGas.mul(GAS_PRICE).mul(nctEthExchangeRate);
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
        require(amount > fees, "Withdrawal amount is less than or equal to fees");
        require(destination != address(0), "Invalid destination address");
        require(flushBlock == 0, "Contract is flushed, cannot withdraw");

        bytes32 hash = keccak256(abi.encodePacked(txHash, blockHash, blockNumber));
        uint256 net = amount.sub(fees);

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
            if (fees != 0 && feeWallet != address(0)) {
                token.safeTransfer(feeWallet, fees);
            }

            // We require that amount > fees therefore net > 0
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
