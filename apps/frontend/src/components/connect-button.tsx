import { Wallet } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/use-auth";
import { shortAddress } from "@/lib/format";

export function ConnectButton() {
  const { address, status, login, logout } = useAuth();

  if (status === "authed") {
    return (
      <div className="flex items-center gap-2">
        <Badge variant="outline" className="font-mono">
          {shortAddress(address)}
        </Badge>
        <Button variant="outline" size="sm" onClick={logout}>
          Đăng xuất
        </Button>
      </div>
    );
  }

  return (
    <Button
      size="sm"
      disabled={status === "signing"}
      onClick={() => {
        void login();
      }}
    >
      <Wallet className="size-4" />
      {status === "signing" ? "Đang ký…" : "Kết nối ví"}
    </Button>
  );
}
