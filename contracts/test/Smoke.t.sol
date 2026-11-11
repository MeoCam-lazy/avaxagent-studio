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

    function setUp() public {
        usdc = new MockUSDC();
        commerce = new AgenticCommerce();
        commerce.initialize(address(usdc), treasury, admin);

        router = new EvaluatorRouter();
        router.initialize(address(commerce), admin);

        policy = new OptimisticPolicy(address(commerce), address(router), admin, 600, 1);

        vm.prank(admin);
        router.setPolicyWhitelist(address(policy), true);

        usdc.mint(client, 10_000_000);
    }

    function testCreateFundSubmitSettleHappyPath() public {
        vm.warp(1_000);

        vm.prank(client);
        uint256 jobId = commerce.createJob(
            provider, address(router), block.timestamp + 7200, "Audit my vault", address(router)
        );

        vm.prank(client);
        router.registerJob(jobId, address(policy));

        vm.prank(client);
        commerce.setBudget(jobId, 250_000, "");

        vm.prank(client);
        usdc.approve(address(commerce), 250_000);

        vm.prank(client);
        commerce.fund(jobId, 250_000, "");

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
}
