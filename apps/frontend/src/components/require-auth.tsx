import type { ReactNode } from "react";
import { Outlet } from "react-router-dom";

import { ConnectButton } from "@/components/connect-button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useAuth } from "@/hooks/use-auth";

export function RequireAuth({ children }: { children?: ReactNode }) {
  const { status } = useAuth();

  if (status !== "authed") {
    return (
      <Card className="mx-auto max-w-md">
        <CardHeader>
          <CardTitle>Yêu cầu đăng nhập</CardTitle>
          <CardDescription>
            Kết nối ví Avalanche và ký bản tin SIWE để quản lý agent, ví và thu nhập của bạn.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <ConnectButton />
        </CardContent>
      </Card>
    );
  }

  return children ? <>{children}</> : <Outlet />;
}
