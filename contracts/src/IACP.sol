// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

interface IERC20Minimal {
    function transfer(address to, uint256 amount) external returns (bool);
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
    function approve(address spender, uint256 amount) external returns (bool);
    function balanceOf(address account) external view returns (uint256);
}

interface IACPHook {
    function beforeAction(uint256 jobId, bytes4 selector, bytes calldata data) external view;
    function afterAction(uint256 jobId, bytes4 selector, bytes calldata data) external;
    function supportsInterface(bytes4 interfaceId) external view returns (bool);
}

interface IPolicy {
    function onSubmitted(uint256 jobId, bytes32 deliverable, bytes calldata optParams) external;
    function check(uint256 jobId, bytes calldata evidence)
        external
        view
        returns (uint8 verdict, bytes32 reason);
}

interface IACP {
    enum JobStatus {
        Open,
        Funded,
        Submitted,
        Completed,
        Rejected,
        Expired
    }

    struct Job {
        uint256 id;
        address client;
        address provider;
        address evaluator;
        string description;
        uint256 budget;
        uint256 expiredAt;
        JobStatus status;
        address hook;
        uint256 submittedAt;
        bytes32 deliverable;
    }

    function getJob(uint256 jobId) external view returns (Job memory);
    function complete(uint256 jobId, bytes32 reason, bytes calldata optParams) external;
    function reject(uint256 jobId, bytes32 reason, bytes calldata optParams) external;
}
