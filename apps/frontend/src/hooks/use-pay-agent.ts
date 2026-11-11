import { useCallback, useState } from "react";
import { useAccount, useConnect, useSignTypedData, useSwitchChain } from "wagmi";

import { GatewayError, sendMessage, type TaskView } from "@/lib/a2a";
import {
  buildAuthorization,
  chainIdOf,
  encodePayment,
  transferTypedData,
  type PaymentReceipt,
} from "@/lib/x402";

export type PayPhase = "idle" | "quoting" | "connecting" | "signing" | "paying" | "done" | "error";

export interface PaidTask {
  task: TaskView;
  receipt: PaymentReceipt | null;
}

const GATEWAY_MESSAGES: Record<string, string> = {
  agent_not_found: "Agent không còn hoạt động.",
  agent_has_no_wallet: "Agent chưa có ví nhận thanh toán.",
  payment_replayed: "Chữ ký thanh toán này đã được dùng. Hãy gửi lại.",
  settlement_failed:
    "Gateway không quyết toán được khoản thanh toán on-chain. Kiểm tra số dư token của ví rồi thử lại.",
  insufficient_value: "Số tiền ký thấp hơn giá của agent.",
  expired: "Chữ ký đã hết hạn. Hãy gửi lại.",
  not_yet_valid: "Đồng hồ máy bạn lệch so với gateway. Hãy kiểm tra giờ hệ thống.",
  bad_signature: "Chữ ký không hợp lệ. Ví có thể không hỗ trợ EIP-712.",
  wrong_network: "Ví ký trên sai mạng.",
  wrong_recipient: "Địa chỉ nhận không khớp với agent.",
  bad_encoding: "Header thanh toán không đọc được.",
  unsupported_scheme: "Agent không nhận thanh toán theo scheme x402 \"exact\".",
};

/** Readable message for anything the pay flow can throw (wallet or gateway). */
export function payErrorMessage(err: unknown): string {
  if (err instanceof GatewayError) {
    return GATEWAY_MESSAGES[err.code] ?? `Gateway trả lỗi ${err.status} (${err.code}).`;
  }
  const e = err as { name?: string; code?: number; shortMessage?: string; message?: string };
  if (e?.name === "UserRejectedRequestError" || e?.code === 4001) {
    return "Bạn đã từ chối yêu cầu trong ví.";
  }
  if (e?.name === "ProviderNotFoundError" || e?.name === "ConnectorNotFoundError") {
    return "Không tìm thấy ví. Hãy cài Core hoặc MetaMask.";
  }
  if (err instanceof TypeError) {
    return "Không kết nối được tới gateway của agent.";
  }
  return e?.shortMessage ?? e?.message ?? String(err);
}

/**
 * Pay-per-call flow against an agent's A2A endpoint:
 * ask for the x402 quote, sign an EIP-3009 authorization in the browser
 * wallet, and resend the message with it. The gateway relays the transfer,
 * so the payer needs the token but no AVAX for gas.
 */
export function usePayAgent(a2aUrl: string) {
  const account = useAccount();
  const { connectors, connectAsync } = useConnect();
  const { switchChainAsync } = useSwitchChain();
  const { signTypedDataAsync } = useSignTypedData();

  const [phase, setPhase] = useState<PayPhase>("idle");
  const [error, setError] = useState<string | null>(null);
  const [paid, setPaid] = useState<PaidTask | null>(null);

  const run = useCallback(
    async (text: string) => {
      setError(null);
      setPaid(null);
      try {
        setPhase("quoting");
        const quote = await sendMessage(a2aUrl, text);
        if (quote.kind === "task") {
          // The gateway did not ask for payment.
          setPaid({ task: quote.task, receipt: quote.receipt });
          setPhase("done");
          return;
        }
        const accept = quote.challenge.accepts.find((a) => a.scheme === "exact");
        if (!accept) throw new GatewayError(402, "unsupported_scheme");

        setPhase("connecting");
        let from = account.address;
        let chainId = account.chainId;
        if (!from) {
          const connector = connectors[0];
          if (!connector) throw Object.assign(new Error("no wallet"), { name: "ProviderNotFoundError" });
          const connected = await connectAsync({ connector });
          from = connected.accounts[0];
          chainId = connected.chainId;
        }
        const target = chainIdOf(accept.network);
        if (chainId !== target) await switchChainAsync({ chainId: target });

        setPhase("signing");
        const auth = buildAuthorization(accept, from, Date.now() / 1000);
        const signature = await signTypedDataAsync({ account: from, ...transferTypedData(accept, auth) });

        setPhase("paying");
        const result = await sendMessage(a2aUrl, text, encodePayment(accept, auth, signature));
        if (result.kind !== "task") throw new GatewayError(402, "payment_required");
        setPaid({ task: result.task, receipt: result.receipt });
        setPhase("done");
      } catch (err) {
        setError(payErrorMessage(err));
        setPhase("error");
      }
    },
    [a2aUrl, account.address, account.chainId, connectAsync, connectors, signTypedDataAsync, switchChainAsync],
  );

  const busy = phase === "quoting" || phase === "connecting" || phase === "signing" || phase === "paying";
  return { phase, busy, error, paid, run, address: account.address ?? null };
}
