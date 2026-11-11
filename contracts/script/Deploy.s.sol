// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {AgenticCommerce} from "../src/AgenticCommerce.sol";
import {EvaluatorRouter} from "../src/EvaluatorRouter.sol";
import {OptimisticPolicy} from "../src/OptimisticPolicy.sol";

interface Vm {
    function envUint(string calldata name) external view returns (uint256);
    function envOr(string calldata name, address defaultValue) external view returns (address);
    function envOr(string calldata name, uint256 defaultValue) external view returns (uint256);
    function addr(uint256 privateKey) external pure returns (address);
    function startBroadcast(uint256 privateKey) external;
    function stopBroadcast() external;
}

/// @notice Deploy AgenticCommerce, EvaluatorRouter, and OptimisticPolicy to Avalanche Fuji / Mainnet.
contract Deploy {
    Vm private constant vm = Vm(address(uint160(uint256(keccak256("hevm cheat code")))));

    address public constant FUJI_USDC = 0x5425890298aed601595a70AB815c96711a31Bc65;
    address public constant MAINNET_USDC = 0xB97EF9Ef8734C71904D8002F8b6Bc66Dd9c48a6E;

    event StackDeployed(
        address commerce, address router, address policy, address paymentToken, uint256 deployBlock
    );

    function run()
        external
        returns (address commerceAddr, address routerAddr, address policyAddr)
    {
        uint256 deployerKey = vm.envUint("DEPLOYER_PRIVATE_KEY");
        address deployer = vm.addr(deployerKey);
        address defaultToken = block.chainid == 43114 ? MAINNET_USDC : FUJI_USDC;
        address paymentToken = vm.envOr("PAYMENT_TOKEN_ADDRESS", defaultToken);
        address treasury = vm.envOr("STUDIO_TREASURY_ADDRESS", deployer);
        uint64 disputeWindow = uint64(vm.envOr("OPTIMISTIC_DISPUTE_WINDOW_S", uint256(3600)));
        uint16 quorum = uint16(vm.envOr("OPTIMISTIC_INITIAL_QUORUM", uint256(1)));

        vm.startBroadcast(deployerKey);

        AgenticCommerce commerce = new AgenticCommerce();
        commerce.initialize(paymentToken, treasury, deployer);

        EvaluatorRouter router = new EvaluatorRouter();
        router.initialize(address(commerce), deployer);

        OptimisticPolicy policy =
            new OptimisticPolicy(address(commerce), address(router), deployer, disputeWindow, quorum);
        router.setPolicyWhitelist(address(policy), true);

        vm.stopBroadcast();

        commerceAddr = address(commerce);
        routerAddr = address(router);
        policyAddr = address(policy);
        emit StackDeployed(commerceAddr, routerAddr, policyAddr, paymentToken, block.number);
    }
}
