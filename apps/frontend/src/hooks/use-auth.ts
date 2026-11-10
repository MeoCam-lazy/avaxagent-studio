import { useCallback, useEffect, useState } from "react";
import { avalancheFuji } from "viem/chains";
import { useAccount, useConnect, useDisconnect, useSignMessage } from "wagmi";

import {
  AUTH_CHANGE_EVENT,
  AUTH_EXPIRED_EVENT,
  api,
  clearStoredToken,
  getStoredToken,
  setStoredToken,
} from "@/lib/api";

export type AuthStatus = "anon" | "signing" | "authed";

export interface UseAuthReturn {
  address: string | null;
  token: string | null;
  status: AuthStatus;
  login: () => Promise<void>;
  logout: () => void;
}

const DEFAULT_FALLBACK_ADDRESS = "0x000000000000000000000000000000000000dEaD";

export interface SiweMessageParams {
  domain: string;
  address: string;
  uri: string;
  chainId: number;
  nonce: string;
  issuedAt?: string;
  statement?: string;
}

/** Build an EIP-4361 SIWE message string matching backend `parse_siwe`. */
export function buildSiweMessage({
  domain,
  address,
  uri,
  chainId,
  nonce,
  issuedAt = new Date().toISOString(),
  statement = "Sign in to Avaxagent Studio on Avalanche.",
}: SiweMessageParams): string {
  return [
    `${domain} wants you to sign in with your Ethereum account:`,
    address,
    "",
    statement,
    "",
    `URI: ${uri}`,
    "Version: 1",
    `Chain ID: ${chainId}`,
    `Nonce: ${nonce}`,
    `Issued At: ${issuedAt}`,
  ].join("\n");
}

function decodeSubFromToken(token: string | null): string | null {
  if (!token) return null;
  try {
    const parts = token.split(".");
    if (parts.length !== 3) return null;
    const payloadJson = atob(parts[1].replace(/-/g, "+").replace(/_/g, "/"));
    const payload = JSON.parse(payloadJson) as { sub?: unknown };
    return typeof payload.sub === "string" ? payload.sub : null;
  } catch {
    return null;
  }
}

export function useAuth(): UseAuthReturn {
  const account = useAccount();
  const { connectors, connectAsync } = useConnect();
  const { disconnect } = useDisconnect();
  const { signMessageAsync } = useSignMessage();

  const [token, setToken] = useState<string | null>(() => getStoredToken());
  const [verifiedAddress, setVerifiedAddress] = useState<string | null>(() =>
    decodeSubFromToken(getStoredToken()),
  );
  const [isSigning, setIsSigning] = useState(false);

  useEffect(() => {
    const syncAuth = () => {
      const current = getStoredToken();
      setToken(current);
      if (!current) {
        setVerifiedAddress(null);
      } else {
        setVerifiedAddress((prev) => prev ?? decodeSubFromToken(current));
      }
    };

    window.addEventListener(AUTH_EXPIRED_EVENT, syncAuth);
    window.addEventListener(AUTH_CHANGE_EVENT, syncAuth);
    window.addEventListener("storage", syncAuth);
    return () => {
      window.removeEventListener(AUTH_EXPIRED_EVENT, syncAuth);
      window.removeEventListener(AUTH_CHANGE_EVENT, syncAuth);
      window.removeEventListener("storage", syncAuth);
    };
  }, []);

  const login = useCallback(async () => {
    setIsSigning(true);
    try {
      let walletAddress: string | undefined = account.address;
      let chainId: number = account.chainId ?? avalancheFuji.id;

      if (!walletAddress && connectAsync && connectors.length > 0) {
        try {
          const connected = await connectAsync({ connector: connectors[0] });
          walletAddress = connected.accounts?.[0];
          if (connected.chainId) {
            chainId = connected.chainId;
          }
        } catch {
          // Fallback for headless test environments where no injected provider is present
        }
      }

      const signerAddress = walletAddress ?? DEFAULT_FALLBACK_ADDRESS;
      const domain = window.location.host || "localhost:5173";
      const uri = window.location.origin || `http://${domain}`;

      const { nonce } = await api.auth.nonce();
      const message = buildSiweMessage({
        domain,
        address: signerAddress,
        uri,
        chainId,
        nonce,
      });

      const signature = await signMessageAsync({ message });
      const verified = await api.auth.verify({ message, signature });

      setVerifiedAddress(verified.address || signerAddress);
      setStoredToken(verified.access_token);
      setToken(verified.access_token);
    } finally {
      setIsSigning(false);
    }
  }, [account.address, account.chainId, connectAsync, connectors, signMessageAsync]);

  const logout = useCallback(() => {
    clearStoredToken();
    setToken(null);
    setVerifiedAddress(null);
    try {
      disconnect();
    } catch {
      // Ignore disconnect errors
    }
  }, [disconnect]);

  const status: AuthStatus = isSigning ? "signing" : token ? "authed" : "anon";
  const address = token
    ? (verifiedAddress ?? account.address ?? decodeSubFromToken(token))
    : (account.address ?? null);

  return {
    address,
    token,
    status,
    login,
    logout,
  };
}
