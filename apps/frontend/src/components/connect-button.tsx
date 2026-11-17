import { Wallet } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/use-auth";
import { shortAddress } from "@/lib/format";

interface ConnectButtonProps {
  label?: string;
  signingLabel?: string;
  logoutLabel?: string;
}

export function ConnectButton({
  label = "Kết nối ví",
  signingLabel = "Đang ký…",
  logoutLabel = "Đăng xuất",
}: ConnectButtonProps = {}) {
  const { address, status, error, login, logout } = useAuth();

  if (status === "authed") {
    return (
      <div className="flex items-center gap-2">
        <Badge variant="outline" className="font-mono">
          {shortAddress(address)}
        </Badge>
        <Button variant="outline" size="sm" onClick={logout}>
          {logoutLabel}
        </Button>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-end gap-1">
      <Button
        size="sm"
        disabled={status === "signing"}
        onClick={() => {
          void login().catch(() => {});
        }}
      >
        <Wallet className="size-4" />
        {status === "signing" ? signingLabel : label}
      </Button>
      {error && (
        <span className="text-destructive max-w-xs text-right text-xs" role="alert">
          {error}
        </span>
      )}
    </div>
  );
}
