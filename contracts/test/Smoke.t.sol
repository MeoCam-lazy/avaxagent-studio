// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {IACP} from "../src/IACP.sol";
import {AgenticCommerce} from "../src/AgenticCommerce.sol";
import {EvaluatorRouter} from "../src/EvaluatorRouter.sol";
import {OptimisticPolicy} from "../src/OptimisticPolicy.sol";

contract MockUSDC {
    mapping(address => uint256) public balanceOf;
    mapping(address => mapping(address => uint256)) public allowance;

    function mint(address to, uint256 amount) external {
        balanceOf[to] += amount;
    }

    function approve(address spender, uint256 amount) external returns (bool) {
        allowance[msg.sender][spender] = amount;
        return true;
    }

    function transfer(address to, uint256 amount) external returns (bool) {
        require(balanceOf[msg.sender] >= amount, "insufficient");
        balanceOf[msg.sender] -= amount;
        balanceOf[to] += amount;
        return true;
    }

    function transferFrom(address from, address to, uint256 amount) external returns (bool) {
        require(allowance[from][msg.sender] >= amount, "allowance");
        require(balanceOf[from] >= amount, "insufficient");
        allowance[from][msg.sender] -= amount;
        balanceOf[from] -= amount;
        balanceOf[to] += amount;
        return true;
    }
}

interface Vm {
    function prank(address msgSender) external;
    function warp(uint256 newTimestamp) external;
    function expectRevert(bytes4 revertData) external;
}

contract SmokeTest {
    Vm private constant vm = Vm(address(uint160(uint256(keccak256("hevm cheat code")))));

    MockUSDC private usdc;
    AgenticCommerce private commerce;
    EvaluatorRouter private router;
    OptimisticPolicy private policy;

    address private admin = address(0xA11CE);
    address private treasury = address(0xFEE);
    address private client = address(0xC11E);
    address private provider = address(0xB0B);
    address private voter = address(0xDA01);

    function setUp() public {
        usdc = new MockUSDC();
        commerce = new AgenticCommerce();
        commerce.initialize(address(usdc), treasury, admin);

        router = new EvaluatorRouter();
        router.initialize(address(commerce), admin);

        policy = new OptimisticPolicy(address(commerce), address(router), admin, 600, 1);

        vm.prank(admin);
        router.setPolicyWhitelist(address(policy), true);

        vm.prank(admin);
        policy.addVoter(voter);

        usdc.mint(client, 10_000_000);
    }

    function _openAndFundJob(uint256 budget, uint256 ttl) internal returns (uint256 jobId) {
        vm.prank(client);
        jobId = commerce.createJob(
            provider, address(router), block.timestamp + ttl, "Audit my vault", address(router)
        );
        vm.prank(client);
        router.registerJob(jobId, address(policy));
        vm.prank(client);
        commerce.setBudget(jobId, budget, "");
        vm.prank(client);
        usdc.approve(address(commerce), budget);
        vm.prank(client);
        commerce.fund(jobId, budget, "");
    }

    function testCreateFundSubmitSettleHappyPath() public {
        vm.warp(1_000);
        uint256 jobId = _openAndFundJob(250_000, 7200);

        bytes32 hash = keccak256("deliverable-json");
        vm.prank(provider);
        commerce.submit(jobId, hash, bytes("ipfs://QmDeliverable"));

        vm.expectRevert(EvaluatorRouter.NotDecided.selector);
        router.settle(jobId, "");

        vm.warp(1_601);
        router.settle(jobId, "");

        IACP.Job memory job = commerce.getJob(jobId);
        require(job.status == IACP.JobStatus.Completed, "expected Completed");
        require(usdc.balanceOf(provider) == 250_000, "provider should receive budget");
    }

    function testDisputeAndVoteRejectRefundsClient() public {
        vm.warp(1_000);
        uint256 beforeBal = usdc.balanceOf(client);
        uint256 jobId = _openAndFundJob(400_000, 7200);

        vm.prank(provider);
        commerce.submit(jobId, keccak256("bad-output"), bytes("ipfs://QmBad"));

        vm.prank(client);
        policy.dispute(jobId);

        vm.prank(voter);
        policy.voteReject(jobId);

        router.settle(jobId, "");

        IACP.Job memory job = commerce.getJob(jobId);
        require(job.status == IACP.JobStatus.Rejected, "expected Rejected");
        require(usdc.balanceOf(client) == beforeBal, "client should be refunded");
        require(usdc.balanceOf(provider) == 0, "provider should receive nothing");
    }

    function testDisputeAndVoteApprovePaysProvider() public {
        vm.warp(1_000);
        uint256 jobId = _openAndFundJob(500_000, 7200);

        vm.prank(provider);
        commerce.submit(jobId, keccak256("valid-audit"), bytes("ipfs://QmGood"));

        vm.prank(client);
        policy.dispute(jobId);

        vm.expectRevert(EvaluatorRouter.NotDecided.selector);
        router.settle(jobId, "");

        vm.prank(voter);
        policy.voteApprove(jobId);

        router.settle(jobId, "");

        IACP.Job memory job = commerce.getJob(jobId);
        require(job.status == IACP.JobStatus.Completed, "expected Completed after approve quorum");
        require(usdc.balanceOf(provider) == 500_000, "provider should be paid");
    }

    function testRemoveSoleVoterRevertsWouldBreakQuorum() public {
        vm.prank(admin);
        vm.expectRevert(OptimisticPolicy.WouldBreakQuorum.selector);
        policy.removeVoter(voter);
    }

    function testExpiredJobClaimRefundAndMarkExpired() public {
        vm.warp(1_000);
        uint256 beforeBal = usdc.balanceOf(client);
        uint256 jobId = _openAndFundJob(300_000, 1800);

        vm.warp(2_801);
        commerce.claimRefund(jobId);
        router.markExpired(jobId);

        IACP.Job memory job = commerce.getJob(jobId);
        require(job.status == IACP.JobStatus.Expired, "expected Expired");
        require(usdc.balanceOf(client) == beforeBal, "client refunded after expiry");
        require(router.inflightJobCount() == 0, "inflight count decremented");
    }

    function testPlatformFeeSplitToTreasury() public {
        vm.warp(1_000);
        vm.prank(admin);
        commerce.setPlatformFee(500, treasury); // 5%

        uint256 jobId = _openAndFundJob(1_000_000, 7200);

        vm.prank(provider);
        commerce.submit(jobId, keccak256("report"), bytes("ipfs://QmReport"));

        vm.warp(1_601);
        router.settle(jobId, "");

        require(usdc.balanceOf(treasury) == 50_000, "treasury receives 5%");
        require(usdc.balanceOf(provider) == 950_000, "provider receives 95%");
    }
}
