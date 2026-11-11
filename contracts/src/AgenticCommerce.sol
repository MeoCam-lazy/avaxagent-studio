// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {IACP, IACPHook, IERC20Minimal} from "./IACP.sol";

/// @title AgenticCommerce — ERC-8183 escrow kernel ported to Avalanche C-Chain (no paymaster hooks)
contract AgenticCommerce is IACP {
    uint256 public constant BP_DENOMINATOR = 10_000;
    uint256 public constant HOOK_GAS_LIMIT = 500_000;
    uint256 public constant MAX_EXPIRY_DURATION = 365 days;
    uint256 public constant MAX_PLATFORM_FEE_BP = 2_500;
    string public constant UPGRADE_INTERFACE_VERSION = "5.0.0";
    bytes4 private constant _HOOK_INTERFACE_ID = type(IACPHook).interfaceId;

    error AddressEmptyCode(address target);
    error BudgetMismatch();
    error EnforcedPause();
    error ExpectedPause();
    error ExpiryTooLong();
    error ExpiryTooShort();
    error FeeTooHigh();
    error HookMissingInterface();
    error InvalidInitialization();
    error InvalidJob();
    error OwnableUnauthorizedAccount(address account);
    error ProviderAlreadySet();
    error ProviderNotSet();
    error ReentrancyGuardReentrantCall();
    error SafeERC20FailedOperation(address token);
    error TokenHasNoCode();
    error Unauthorized();
    error UnsupportedPaymentToken();
    error WrongStatus();
    error ZeroAddress();
    error ZeroBudget();

    event Initialized(uint64 version);
    event OwnershipTransferStarted(address indexed previousOwner, address indexed newOwner);
    event OwnershipTransferred(address indexed previousOwner, address indexed newOwner);
    event Paused(address account);
    event Unpaused(address account);
    event PlatformFeeUpdated(uint256 feeBP, address indexed treasury);
    event PaymentTokenSupportUpdated(address indexed token, bool supported);
    event JobCreated(
        uint256 indexed jobId,
        address indexed client,
        address indexed provider,
        address evaluator,
        uint256 expiredAt,
        address hook
    );
    event JobPaymentTokenBound(uint256 indexed jobId, address indexed token);
    event ProviderSet(uint256 indexed jobId, address indexed provider);
    event BudgetSet(uint256 indexed jobId, uint256 amount);
    event JobFunded(
        uint256 indexed jobId, address indexed client, address indexed provider, uint256 amount
    );
    event JobSubmitted(uint256 indexed jobId, address indexed provider, bytes32 deliverable);
    event JobCompleted(uint256 indexed jobId, address indexed evaluator, bytes32 reason);
    event PaymentReleased(uint256 indexed jobId, address indexed provider, uint256 amount);
    event JobRejected(uint256 indexed jobId, address indexed rejector, bytes32 reason);
    event JobExpired(uint256 indexed jobId);
    event Refunded(uint256 indexed jobId, address indexed client, uint256 amount);

    bool private _initialized;
    bool private _entered;
    bool public paused;
    address public owner;
    address public pendingOwner;

    address public paymentToken;
    address public platformTreasury;
    uint256 public platformFeeBP;
    uint256 public jobCounter;

    mapping(uint256 => Job) public jobs;
    mapping(uint256 => address) public jobPaymentToken;
    mapping(uint256 => bool) public jobHasBudget;
    mapping(address => bool) public isPaymentTokenSupported;

    modifier onlyOwner() {
        if (msg.sender != owner) revert OwnableUnauthorizedAccount(msg.sender);
        _;
    }

    modifier whenNotPaused() {
        if (paused) revert EnforcedPause();
        _;
    }

    modifier nonReentrant() {
        if (_entered) revert ReentrancyGuardReentrantCall();
        _entered = true;
        _;
        _entered = false;
    }

    function initialize(address paymentToken_, address treasury_, address owner_) external {
        if (_initialized) revert InvalidInitialization();
        if (paymentToken_ == address(0) || treasury_ == address(0) || owner_ == address(0)) {
            revert ZeroAddress();
        }
        if (paymentToken_.code.length == 0) revert TokenHasNoCode();
        _initialized = true;
        paymentToken = paymentToken_;
        platformTreasury = treasury_;
        owner = owner_;
        isPaymentTokenSupported[paymentToken_] = true;
        emit OwnershipTransferred(address(0), owner_);
        emit PaymentTokenSupportUpdated(paymentToken_, true);
        emit Initialized(1);
    }

    function initializeMultiToken(address[] calldata tokens) external onlyOwner {
        for (uint256 i = 0; i < tokens.length; i++) {
            if (tokens[i] == address(0)) revert ZeroAddress();
            isPaymentTokenSupported[tokens[i]] = true;
            emit PaymentTokenSupportUpdated(tokens[i], true);
        }
    }

    function setPaymentTokenSupported(address token, bool supported) external onlyOwner {
        if (token == address(0)) revert ZeroAddress();
        isPaymentTokenSupported[token] = supported;
        emit PaymentTokenSupportUpdated(token, supported);
    }

    function setPlatformFee(uint256 feeBP_, address treasury_) external onlyOwner {
        if (feeBP_ > MAX_PLATFORM_FEE_BP) revert FeeTooHigh();
        if (treasury_ == address(0)) revert ZeroAddress();
        platformFeeBP = feeBP_;
        platformTreasury = treasury_;
        emit PlatformFeeUpdated(feeBP_, treasury_);
    }

    function transferOwnership(address newOwner) external onlyOwner {
        if (newOwner == address(0)) revert ZeroAddress();
        pendingOwner = newOwner;
        emit OwnershipTransferStarted(owner, newOwner);
    }

    function acceptOwnership() external {
        if (msg.sender != pendingOwner) revert OwnableUnauthorizedAccount(msg.sender);
        address prev = owner;
        owner = pendingOwner;
        pendingOwner = address(0);
        emit OwnershipTransferred(prev, owner);
    }

    function renounceOwnership() external onlyOwner {
        address prev = owner;
        owner = address(0);
        pendingOwner = address(0);
        emit OwnershipTransferred(prev, address(0));
    }

    function pause() external onlyOwner {
        if (paused) revert EnforcedPause();
        paused = true;
        emit Paused(msg.sender);
    }

    function unpause() external onlyOwner {
        if (!paused) revert ExpectedPause();
        paused = false;
        emit Unpaused(msg.sender);
    }

    function createJob(
        address provider,
        address evaluator,
        uint256 expiredAt,
        string calldata description,
        address hook
    ) external whenNotPaused returns (uint256 jobId) {
        return _createJob(provider, evaluator, expiredAt, description, hook, paymentToken);
    }

    function createJobWithToken(
        address provider,
        address evaluator,
        uint256 expiredAt,
        string calldata description,
        address hook,
        address token
    ) external whenNotPaused returns (uint256 jobId) {
        return _createJob(provider, evaluator, expiredAt, description, hook, token);
    }

    function _createJob(
        address provider,
        address evaluator,
        uint256 expiredAt,
        string calldata description,
        address hook,
        address token
    ) internal returns (uint256 jobId) {
        if (evaluator == address(0) || token == address(0)) revert ZeroAddress();
        if (!isPaymentTokenSupported[token]) revert UnsupportedPaymentToken();
        if (expiredAt <= block.timestamp) revert ExpiryTooShort();
        if (expiredAt > block.timestamp + MAX_EXPIRY_DURATION) revert ExpiryTooLong();
        if (hook != address(0) && !IACPHook(hook).supportsInterface(_HOOK_INTERFACE_ID)) {
            revert HookMissingInterface();
        }

        jobId = ++jobCounter;
        jobs[jobId] = Job({
            id: jobId,
            client: msg.sender,
            provider: provider,
            evaluator: evaluator,
            description: description,
            budget: 0,
            expiredAt: expiredAt,
            status: JobStatus.Open,
            hook: hook,
            submittedAt: 0,
            deliverable: bytes32(0)
        });
        jobPaymentToken[jobId] = token;
        emit JobCreated(jobId, msg.sender, provider, evaluator, expiredAt, hook);
        emit JobPaymentTokenBound(jobId, token);
    }

    function setProvider(uint256 jobId, address provider_, bytes calldata optParams)
        external
        whenNotPaused
    {
        Job storage job = _requireJob(jobId);
        if (msg.sender != job.client) revert Unauthorized();
        if (job.status != JobStatus.Open) revert WrongStatus();
        if (job.provider != address(0)) revert ProviderAlreadySet();
        if (provider_ == address(0)) revert ZeroAddress();
        _beforeHook(job, this.setProvider.selector, optParams);
        job.provider = provider_;
        emit ProviderSet(jobId, provider_);
        _afterHook(job, this.setProvider.selector, optParams);
    }

    function setBudget(uint256 jobId, uint256 amount, bytes calldata optParams)
        external
        whenNotPaused
    {
        Job storage job = _requireJob(jobId);
        if (msg.sender != job.client) revert Unauthorized();
        if (job.status != JobStatus.Open) revert WrongStatus();
        if (amount == 0) revert ZeroBudget();
        _beforeHook(job, this.setBudget.selector, optParams);
        job.budget = amount;
        jobHasBudget[jobId] = true;
        emit BudgetSet(jobId, amount);
        _afterHook(job, this.setBudget.selector, optParams);
    }

    function fund(uint256 jobId, uint256 expectedBudget, bytes calldata optParams)
        external
        whenNotPaused
        nonReentrant
    {
        Job storage job = _requireJob(jobId);
        if (msg.sender != job.client) revert Unauthorized();
        if (job.status != JobStatus.Open) revert WrongStatus();
        if (job.provider == address(0)) revert ProviderNotSet();
        if (!jobHasBudget[jobId] || job.budget == 0) revert ZeroBudget();
        if (job.budget != expectedBudget) revert BudgetMismatch();

        _beforeHook(job, this.fund.selector, optParams);
        address token = jobPaymentToken[jobId];
        if (!IERC20Minimal(token).transferFrom(msg.sender, address(this), job.budget)) {
            revert SafeERC20FailedOperation(token);
        }
        job.status = JobStatus.Funded;
        emit JobFunded(jobId, job.client, job.provider, job.budget);
        _afterHook(job, this.fund.selector, optParams);
    }

    function submit(uint256 jobId, bytes32 deliverable, bytes calldata optParams)
        external
        whenNotPaused
    {
        Job storage job = _requireJob(jobId);
        if (msg.sender != job.provider) revert Unauthorized();
        if (job.status != JobStatus.Funded) revert WrongStatus();
        _beforeHook(job, this.submit.selector, abi.encode(deliverable, optParams));
        job.deliverable = deliverable;
        job.submittedAt = block.timestamp;
        job.status = JobStatus.Submitted;
        emit JobSubmitted(jobId, msg.sender, deliverable);
        _afterHook(job, this.submit.selector, abi.encode(deliverable, optParams));
    }

    function complete(uint256 jobId, bytes32 reason, bytes calldata optParams)
        external
        override
        whenNotPaused
        nonReentrant
    {
        Job storage job = _requireJob(jobId);
        if (msg.sender != job.evaluator) revert Unauthorized();
        if (job.status != JobStatus.Submitted && job.status != JobStatus.Funded) revert WrongStatus();

        _beforeHook(job, this.complete.selector, optParams);
        job.status = JobStatus.Completed;

        address token = jobPaymentToken[jobId];
        uint256 fee = (job.budget * platformFeeBP) / BP_DENOMINATOR;
        uint256 payout = job.budget - fee;
        if (fee > 0) {
            if (!IERC20Minimal(token).transfer(platformTreasury, fee)) {
                revert SafeERC20FailedOperation(token);
            }
        }
        if (!IERC20Minimal(token).transfer(job.provider, payout)) {
            revert SafeERC20FailedOperation(token);
        }

        emit JobCompleted(jobId, msg.sender, reason);
        emit PaymentReleased(jobId, job.provider, payout);
        _afterHook(job, this.complete.selector, optParams);
    }

    function reject(uint256 jobId, bytes32 reason, bytes calldata optParams)
        external
        override
        whenNotPaused
        nonReentrant
    {
        Job storage job = _requireJob(jobId);
        if (msg.sender != job.evaluator) revert Unauthorized();
        if (job.status != JobStatus.Submitted && job.status != JobStatus.Funded) revert WrongStatus();

        _beforeHook(job, this.reject.selector, optParams);
        job.status = JobStatus.Rejected;
        address token = jobPaymentToken[jobId];
        if (!IERC20Minimal(token).transfer(job.client, job.budget)) {
            revert SafeERC20FailedOperation(token);
        }
        emit JobRejected(jobId, msg.sender, reason);
        emit Refunded(jobId, job.client, job.budget);
        _afterHook(job, this.reject.selector, optParams);
    }

    function claimRefund(uint256 jobId) external whenNotPaused nonReentrant {
        Job storage job = _requireJob(jobId);
        if (block.timestamp < job.expiredAt) revert ExpiryTooShort();
        if (job.status != JobStatus.Funded && job.status != JobStatus.Submitted) revert WrongStatus();

        job.status = JobStatus.Expired;
        address token = jobPaymentToken[jobId];
        if (!IERC20Minimal(token).transfer(job.client, job.budget)) {
            revert SafeERC20FailedOperation(token);
        }
        emit JobExpired(jobId);
        emit Refunded(jobId, job.client, job.budget);
    }

    function getJob(uint256 jobId) external view override returns (Job memory) {
        if (jobs[jobId].id == 0) revert InvalidJob();
        return jobs[jobId];
    }

    function _requireJob(uint256 jobId) internal view returns (Job storage job) {
        job = jobs[jobId];
        if (job.id == 0) revert InvalidJob();
    }

    function _beforeHook(Job storage job, bytes4 selector, bytes memory data) internal view {
        if (job.hook != address(0)) {
            IACPHook(job.hook).beforeAction{gas: HOOK_GAS_LIMIT}(job.id, selector, data);
        }
    }

    function _afterHook(Job storage job, bytes4 selector, bytes memory data) internal {
        if (job.hook != address(0)) {
            IACPHook(job.hook).afterAction{gas: HOOK_GAS_LIMIT}(job.id, selector, data);
        }
    }
}
