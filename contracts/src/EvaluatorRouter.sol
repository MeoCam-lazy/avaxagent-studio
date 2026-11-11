// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {IACP, IACPHook, IPolicy} from "./IACP.sol";

/// @title EvaluatorRouter — ERC-8183 hook & permissionless settlement router
contract EvaluatorRouter is IACPHook {
    string public constant UPGRADE_INTERFACE_VERSION = "5.0.0";
    bytes4 private constant _SUBMIT_SELECTOR = bytes4(keccak256("submit(uint256,bytes32,bytes)"));

    error EnforcedPause();
    error ExpectedPause();
    error HasInflightJobs();
    error InvalidInitialization();
    error JobNotOpen();
    error NotCommerce();
    error NotDecided();
    error NotExpired();
    error NotJobClient();
    error NotPaused();
    error OwnableUnauthorizedAccount(address account);
    error PolicyAlreadySet();
    error PolicyNotSet();
    error PolicyNotWhitelisted();
    error RouterNotEvaluator();
    error RouterNotHook();
    error UnknownVerdict(uint8 verdict);
    error ZeroAddress();

    event Initialized(uint64 version);
    event OwnershipTransferStarted(address indexed previousOwner, address indexed newOwner);
    event OwnershipTransferred(address indexed previousOwner, address indexed newOwner);
    event Paused(address account);
    event Unpaused(address account);
    event CommerceSet(address indexed oldCommerce, address indexed newCommerce);
    event PolicyWhitelisted(address indexed policy, bool indexed status);
    event JobRegistered(uint256 indexed jobId, address indexed policy, address indexed client);
    event JobSettled(
        uint256 indexed jobId, address indexed policy, uint8 indexed verdict, bytes32 reason
    );
    event JobFinalised(uint256 indexed jobId, IACP.JobStatus indexed status);

    bool private _initialized;
    bool public paused;
    address public owner;
    address public pendingOwner;
    address public commerce;
    uint256 public inflightJobCount;

    mapping(address => bool) public policyWhitelist;
    mapping(uint256 => address) public jobPolicy;
    mapping(uint256 => bool) private _settled;

    modifier onlyOwner() {
        if (msg.sender != owner) revert OwnableUnauthorizedAccount(msg.sender);
        _;
    }

    modifier whenNotPaused() {
        if (paused) revert EnforcedPause();
        _;
    }

    function initialize(address commerce_, address owner_) external {
        if (_initialized) revert InvalidInitialization();
        if (commerce_ == address(0) || owner_ == address(0)) revert ZeroAddress();
        _initialized = true;
        commerce = commerce_;
        owner = owner_;
        emit CommerceSet(address(0), commerce_);
        emit OwnershipTransferred(address(0), owner_);
        emit Initialized(1);
    }

    function setCommerce(address newCommerce) external onlyOwner {
        if (!paused) revert NotPaused();
        if (inflightJobCount > 0) revert HasInflightJobs();
        if (newCommerce == address(0)) revert ZeroAddress();
        address old = commerce;
        commerce = newCommerce;
        emit CommerceSet(old, newCommerce);
    }

    function setPolicyWhitelist(address policy, bool status) external onlyOwner {
        if (policy == address(0)) revert ZeroAddress();
        policyWhitelist[policy] = status;
        emit PolicyWhitelisted(policy, status);
    }

    function registerJob(uint256 jobId, address policy) external whenNotPaused {
        if (!policyWhitelist[policy]) revert PolicyNotWhitelisted();
        if (jobPolicy[jobId] != address(0)) revert PolicyAlreadySet();

        IACP.Job memory job = IACP(commerce).getJob(jobId);
        if (msg.sender != job.client) revert NotJobClient();
        if (job.status != IACP.JobStatus.Open) revert JobNotOpen();
        if (job.evaluator != address(this)) revert RouterNotEvaluator();
        if (job.hook != address(this)) revert RouterNotHook();

        jobPolicy[jobId] = policy;
        inflightJobCount += 1;
        emit JobRegistered(jobId, policy, msg.sender);
    }

    function beforeAction(uint256 jobId, bytes4, bytes calldata) external view override {
        if (jobPolicy[jobId] == address(0)) revert PolicyNotSet();
    }

    function afterAction(uint256 jobId, bytes4 selector, bytes calldata data) external override {
        if (msg.sender != commerce) revert NotCommerce();
        address policy = jobPolicy[jobId];
        if (policy == address(0)) revert PolicyNotSet();

        if (selector == _SUBMIT_SELECTOR) {
            (bytes32 deliverable, bytes memory optParams) = abi.decode(data, (bytes32, bytes));
            IPolicy(policy).onSubmitted(jobId, deliverable, optParams);
        }
    }

    function settle(uint256 jobId, bytes calldata evidence) external whenNotPaused {
        address policy = jobPolicy[jobId];
        if (policy == address(0) || _settled[jobId]) revert PolicyNotSet();

        (uint8 verdict, bytes32 reason) = IPolicy(policy).check(jobId, evidence);
        if (verdict == 0) revert NotDecided();

        _settled[jobId] = true;
        inflightJobCount -= 1;

        if (verdict == 1) {
            IACP(commerce).complete(jobId, reason, "");
            emit JobSettled(jobId, policy, verdict, reason);
            emit JobFinalised(jobId, IACP.JobStatus.Completed);
        } else if (verdict == 2) {
            IACP(commerce).reject(jobId, reason, "");
            emit JobSettled(jobId, policy, verdict, reason);
            emit JobFinalised(jobId, IACP.JobStatus.Rejected);
        } else {
            revert UnknownVerdict(verdict);
        }
    }

    function markExpired(uint256 jobId) external {
        if (jobPolicy[jobId] == address(0) || _settled[jobId]) revert PolicyNotSet();
        IACP.Job memory job = IACP(commerce).getJob(jobId);
        if (job.status != IACP.JobStatus.Expired) revert NotExpired();
        _settled[jobId] = true;
        inflightJobCount -= 1;
        emit JobFinalised(jobId, IACP.JobStatus.Expired);
    }

    function supportsInterface(bytes4 interfaceId) external pure override returns (bool) {
        return interfaceId == type(IACPHook).interfaceId || interfaceId == 0x01ffc9a7;
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
}
