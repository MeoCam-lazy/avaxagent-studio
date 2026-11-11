"""Read-only Fuji checks: what the studio advertises must match the real chain.

These need no funds, so they run against the public Fuji RPC as well as a fork.
A mismatch here means every real x402 payment would fail at the relayer.
"""

from __future__ import annotations

import secrets
import time
from types import SimpleNamespace

from eth_abi import encode
from eth_account import Account
from web3 import Web3
from web3.exceptions import ContractLogicError

from app.chain import network as net
from app.chain.reader import Web3ChainReader
from app.data_plane.gateway.x402 import challenge
from tests.fuji.conftest import sign_authorization


def _accept() -> dict:
    """The 402 ``accepts[0]`` the gateway would send for a 0.1 USDC agent."""
    agent = SimpleNamespace(price_atomic=100_000)
    wallet = SimpleNamespace(address=Account.create().address)
    return challenge(agent, wallet)["accepts"][0].model_dump(by_alias=True)


def test_rpc_is_fuji_and_registry_is_deployed(w3: Web3):
    assert w3.eth.chain_id == 43113
    registry = Web3.to_checksum_address(net.identity_registry())
    assert len(w3.eth.get_code(registry)) > 0, "ERC-8004 identity registry has no code"


def test_challenge_eip712_domain_matches_the_token(w3: Web3, usdc):
    """The gateway hardcodes the EIP-712 domain it asks payers to sign for."""
    accept = _accept()
    assert Web3.to_checksum_address(accept["asset"]) == usdc.address
    assert accept["extra"]["name"] == usdc.functions.name().call()
    assert accept["extra"]["version"] == usdc.functions.version().call()

    type_hash = Web3.keccak(
        text="EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)"
    )
    separator = Web3.keccak(
        encode(
            ["bytes32", "bytes32", "bytes32", "uint256", "address"],
            [
                type_hash,
                Web3.keccak(text=accept["extra"]["name"]),
                Web3.keccak(text=accept["extra"]["version"]),
                43113,
                usdc.address,
            ],
        )
    )
    assert usdc.functions.DOMAIN_SEPARATOR().call() == separator


def _call_transfer(usdc, signed: dict, *, signature: str | None = None) -> None:
    auth = signed["authorization"]
    sig = bytes.fromhex((signature or signed["signature"]).removeprefix("0x"))
    usdc.functions.transferWithAuthorization(
        auth["from"],
        auth["to"],
        auth["value"],
        auth["validAfter"],
        auth["validBefore"],
        bytes.fromhex(auth["nonce"][2:]),
        sig[64] if sig[64] >= 27 else sig[64] + 27,
        sig[:32],
        sig[32:64],
    ).call({"from": Account.create().address})


def test_token_accepts_a_payment_signed_like_an_x402_client(usdc):
    """``eth_call`` the real ``transferWithAuthorization`` with our signature.

    Value 0 keeps it fundless: the token verifies the signature before moving
    funds, so success means the chain accepts what clients sign for the studio.
    """
    accept = _accept()
    payer = Account.create()
    signed = sign_authorization(payer, accept, value=0, now=int(time.time()))
    _call_transfer(usdc, signed)

    other = sign_authorization(Account.create(), accept, value=0, now=int(time.time()))
    try:
        _call_transfer(usdc, signed, signature=other["signature"])
    except ContractLogicError as exc:
        assert "signature" in str(exc).lower()
    else:  # pragma: no cover - a wrong signer must never move funds
        raise AssertionError("token accepted a signature from another account")


def test_chain_reader_reads_authorization_state():
    reader = Web3ChainReader(net.network().rpc_url)
    used = reader.authorization_used(
        net.payment_asset_address(), Account.create().address, secrets.token_bytes(32)
    )
    assert used is False
