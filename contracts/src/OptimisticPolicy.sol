// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {IACP, IPolicy} from "./IACP.sol";

/// @title OptimisticPolicy — Dispute-window optimistic settlement policy for ERC-8183
contract OptimisticPolicy is IPolicy {
    bytes32 public constant REASON_APPROVED = keccak256("OPTIMISTIC_APPROVED");
    bytes32 public constant REASON_REJECTED = keccak256("DISPUTE_QUORUM_REJECTED");

    error AlreadyDisputed();
    error AlreadyInitialised();
    error AlreadyVoted();
    error NotAdmin();
    error NotClient();
    error NotDisputed();
    error NotPendingAdmin();
    error NotRouter();
    error NotSubmitted();
    error NotVoter();
    error OutsideDisputeWindow();
    error QuorumOutOfRange();
    error QuorumZero();
    error SubmissionTooLate();
    error UnknownVoter();
    error VoterAlreadyExists();
    error WouldBreakQuorum();
    error WrongJobStatus();
    error ZeroAddress();

    event AdminTransferStarted(address indexed previousAdmin, address indexed pendingAdmin);
    event AdminTransferred(address indexed previousAdmin, address indexed newAdmin);
    event JobInitialised(
        uint256 indexed jobId, bytes32 deliverable, uint64 submittedAt, bytes optParams
    );
    event Disputed(uint256 indexed jobId, address indexed client);
    event VoterAdded(address indexed voter, uint16 activeVoterCount);
    event VoterRemoved(address indexed voter, uint16 activeVoterCount);
    event QuorumUpdated(uint16 oldQuorum, uint16 newQuorum);
    event VoteCast(uint256 indexed jobId, address indexed voter, uint16 rejectVotes);
    event QuorumReached(uint256 indexed jobId, uint16 rejectVotes);

    IACP public immutable commerce;
    address public immutable router;
    uint64 public immutable disputeWindow;

    address public admin;
    address public pendingAdmin;
    uint16 public voteQuorum;
    uint16 public activeVoterCount;

    mapping(address => bool) public isVoter;
    mapping(uint256 => uint64) public submittedAt;
    mapping(uint256 => bool) public disputed;
    mapping(uint256 => uint16) public disputeQuorumSnapshot;
    mapping(uint256 => uint16) public rejectVotes;
    mapping(uint256 => mapping(address => bool)) public hasVoted;

    modifier onlyAdmin() {
        if (msg.sender != admin) revert NotAdmin();
        _;
    }

    constructor(
        address commerce_,
        address router_,
        address admin_,
        uint64 disputeWindow_,
        uint16 initialQuorum_
    ) {
        if (commerce_ == address(0) || router_ == address(0) || admin_ == address(0)) {
            revert ZeroAddress();
        }
        if (initialQuorum_ == 0) revert QuorumZero();
        commerce = IACP(commerce_);
        router = router_;
        admin = admin_;
        disputeWindow = disputeWindow_;
        voteQuorum = initialQuorum_;
    }

    function onSubmitted(uint256 jobId, bytes32 deliverable, bytes calldata optParams)
        external
        override
    {
        if (msg.sender != router) revert NotRouter();
        if (submittedAt[jobId] != 0) revert AlreadyInitialised();

        IACP.Job memory job = commerce.getJob(jobId);
        if (job.status != IACP.JobStatus.Submitted) revert WrongJobStatus();
        if (block.timestamp + disputeWindow > job.expiredAt) revert SubmissionTooLate();

        uint64 ts = uint64(block.timestamp);
        submittedAt[jobId] = ts;
        emit JobInitialised(jobId, deliverable, ts, optParams);
    }

    function dispute(uint256 jobId) external {
        uint64 sub = submittedAt[jobId];
        if (sub == 0) revert NotSubmitted();
        if (disputed[jobId]) revert AlreadyDisputed();
        if (block.timestamp > sub + disputeWindow) revert OutsideDisputeWindow();

        IACP.Job memory job = commerce.getJob(jobId);
        if (msg.sender != job.client) revert NotClient();

        disputed[jobId] = true;
        disputeQuorumSnapshot[jobId] = voteQuorum;
        emit Disputed(jobId, msg.sender);
    }

    function voteReject(uint256 jobId) external {
        if (!isVoter[msg.sender]) revert NotVoter();
        if (!disputed[jobId]) revert NotDisputed();
        if (hasVoted[jobId][msg.sender]) revert AlreadyVoted();

        hasVoted[jobId][msg.sender] = true;
        uint16 votes = rejectVotes[jobId] + 1;
        rejectVotes[jobId] = votes;
        emit VoteCast(jobId, msg.sender, votes);
        if (votes >= disputeQuorumSnapshot[jobId]) {
            emit QuorumReached(jobId, votes);
        }
    }

    function check(uint256 jobId, bytes calldata)
        external
        view
        override
        returns (uint8 verdict, bytes32 reason)
    {
        uint64 sub = submittedAt[jobId];
        if (sub == 0) return (0, bytes32(0));

        if (!disputed[jobId]) {
            if (block.timestamp >= sub + disputeWindow) {
                return (1, REASON_APPROVED);
            }
            return (0, bytes32(0));
        }

        if (rejectVotes[jobId] >= disputeQuorumSnapshot[jobId]) {
            return (2, REASON_REJECTED);
        }
        return (0, bytes32(0));
    }

    function addVoter(address voter) external onlyAdmin {
        if (voter == address(0)) revert ZeroAddress();
        if (isVoter[voter]) revert VoterAlreadyExists();
        isVoter[voter] = true;
        activeVoterCount += 1;
        emit VoterAdded(voter, activeVoterCount);
    }

    function removeVoter(address voter) external onlyAdmin {
        if (!isVoter[voter]) revert UnknownVoter();
        if (activeVoterCount - 1 < voteQuorum && activeVoterCount > 1) revert WouldBreakQuorum();
        isVoter[voter] = false;
        activeVoterCount -= 1;
        emit VoterRemoved(voter, activeVoterCount);
    }

    function setQuorum(uint16 newQuorum) external onlyAdmin {
        if (newQuorum == 0) revert QuorumZero();
        if (activeVoterCount > 0 && newQuorum > activeVoterCount) revert QuorumOutOfRange();
        uint16 old = voteQuorum;
        voteQuorum = newQuorum;
        emit QuorumUpdated(old, newQuorum);
    }

    function transferAdmin(address newAdmin) external onlyAdmin {
        if (newAdmin == address(0)) revert ZeroAddress();
        pendingAdmin = newAdmin;
        emit AdminTransferStarted(admin, newAdmin);
    }

    function acceptAdmin() external {
        if (msg.sender != pendingAdmin) revert NotPendingAdmin();
        address prev = admin;
        admin = pendingAdmin;
        pendingAdmin = address(0);
        emit AdminTransferred(prev, admin);
    }
}
