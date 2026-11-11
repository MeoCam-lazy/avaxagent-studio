# Fuji end-to-end tests

`apps/backend/tests/fuji/` runs the studio's real flows against Avalanche Fuji (chain 43113).
The suite is opt-in: without `FUJI_E2E=1` every test is skipped, so `make test` stays offline.

## What it covers

`test_network.py` makes read-only checks.
It needs no funds and is safe against the public RPC.

- The RPC is Fuji, and the ERC-8004 identity registry has code.
- The EIP-712 domain in the gateway's 402 challenge (`name`, `version`, chain, token) matches the token on-chain, down to `DOMAIN_SEPARATOR`.
- The real USDC `transferWithAuthorization` accepts an authorization signed the way x402 clients sign it, and rejects one signed by another account.
  The check uses `eth_call` with value 0, so it costs nothing.
- `ChainReader.authorization_used` reads the token's authorization state.

`test_flow.py` walks the plan's definition of done as one story:

1. A creator signs in with SIWE.
2. The creator creates a public x402 agent.
3. The studio provisions the agent's wallet.
4. The agent registers on ERC-8004, and the test checks `ownerOf(agentId)` on-chain.
5. A client pays per call over x402.
   The relayer settles the transfer on-chain, the agent's USDC goes up by the price, and the payer spends no AVAX.
   Replaying the same payment is rejected.
6. The worker runs the job, and the client reads the output through A2A `tasks/get`.
7. Earnings are booked net of the 5% studio fee.
8. A withdrawal is sent on-chain to an external address.
9. The fee is swept to the treasury address.

Only custody is replaced.
The agent wallet and the relayer sign with local test keys instead of Turnkey.
The API, gateway, worker, settler, database and chain calls are the real code.
The LLM is a stub that echoes the prompt.

## Run it on a Fuji fork (recommended)

A fork runs the real Fuji contracts locally.
The tests create throwaway accounts and fund them with anvil cheatcodes, so you need no keys and no faucet.

```bash
make infra            # Postgres + Redis
make fuji-fork        # anvil in Docker on :8545, forking the public Fuji RPC
make test-fuji-fork
docker stop avaxagent-anvil
```

## Run it on live Fuji

These are real Fuji transactions.
They cost test tokens only, but they are irreversible and public.
Each run registers a new ERC-8004 identity and moves 0.1 USDC.

Create three accounts that you use only for this, and fund them from faucets:

| Variable | Role | Needs |
| --- | --- | --- |
| `FUJI_PAYER_KEY` | the client paying for the call | USDC (0.1 per run), no AVAX |
| `FUJI_RELAYER_KEY` | relays the x402 transfer | AVAX for gas |
| `FUJI_AGENT_KEY` | stands in for the agent's Turnkey wallet: registers, pays out, sweeps the fee | AVAX for gas |

Fuji USDC comes from the Circle faucet (faucet.circle.com, network Avalanche Fuji).
Fuji AVAX comes from the Core faucet (core.app/tools/testnet-faucet).

```bash
export FUJI_PAYER_KEY=... FUJI_RELAYER_KEY=... FUJI_AGENT_KEY=...
make test-fuji
```

The keys are read from the environment and never printed.
Never use a key that holds mainnet funds.

## Not covered

- Turnkey itself: sub-org creation, policies and enclave signing need Turnkey credentials.
- The browser wallet (MetaMask or Core) signing on the marketplace page.
  The x402 signature it produces is covered by the frontend unit tests and by the token check above.
- The ERC-8183 escrow flow.
  Its contracts are not deployed to Fuji yet (`COMMERCE_ADDRESS` and the others are unset), so there is nothing live to run it against.
