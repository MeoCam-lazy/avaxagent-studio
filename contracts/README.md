# ERC-8183 Contracts on Avalanche (`contracts/`)

Bộ hợp đồng ký quỹ on-chain chuẩn **ERC-8183** đã được chuyển đổi sang **Avalanche C-Chain** (loại bỏ hoàn toàn phụ thuộc MegaFuel/paymaster của BNB Chain và dùng trực tiếp USDC gốc trên Avalanche):

- `src/AgenticCommerce.sol` — Kernel quản lý vòng đời Job (`Open -> Funded -> Submitted -> Completed / Rejected / Expired`).
- `src/EvaluatorRouter.sol` — Hook & Router định tuyến quyết toán phi tập trung (`registerJob`, `settle`).
- `src/OptimisticPolicy.sol` — Chính sách quyết toán lạc quan theo cửa sổ khiếu nại (`disputeWindow`, `dispute`, `voteReject`, `check`).
- `script/Deploy.s.sol` — Script triển khai trọn bộ 3 hợp đồng lên Fuji (`43113`) hoặc Mainnet (`43114`).
- `test/Smoke.t.sol` — Bài kiểm thử Foundry luồng `createJob -> registerJob -> setBudget -> fund -> submit -> settle`.

## Token thanh toán mặc định
- **Avalanche Fuji (`43113`)**: USDC `0x5425890298aed601595a70AB815c96711a31Bc65`
- **Avalanche C-Chain Mainnet (`43114`)**: USDC `0xB97EF9Ef8734C71904D8002F8b6Bc66Dd9c48a6E`

## Kiểm thử & Triển khai bằng Foundry

```bash
# Chạy smoke test local
make contracts-test

# Deploy lên Avalanche Fuji & verify Snowtrace
DEPLOYER_PRIVATE_KEY=0x... RPC_URL=https://api.avax-test.network/ext/bc/C/rpc make contracts-deploy-fuji
```

Sau khi deploy lên Fuji/Mainnet, điền 3 địa chỉ in ra vào `.env` của backend để mở khóa chế độ `SettlementMode.ERC8183` (`settings.commerce_enabled == True`):

```env
COMMERCE_ADDRESS=0x...
ROUTER_ADDRESS=0x...
POLICY_ADDRESS=0x...
INDEXER_START_BLOCK=<block_deploy>
```
