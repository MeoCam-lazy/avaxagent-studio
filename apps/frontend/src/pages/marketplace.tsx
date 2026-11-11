import { useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { Link } from "react-router-dom";

import { PageHeader } from "@/components/page-header";
import { QueryState } from "@/components/query-state";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useDebounced } from "@/hooks/use-debounced";
import { useNetwork } from "@/hooks/use-network";
import { api } from "@/lib/api";
import { formatAtomic } from "@/lib/format";
import type { MarketplaceAgent } from "@/lib/types";

/** Wait this long after the last keystroke before searching. */
export const SEARCH_DEBOUNCE_MS = 300;

export function MarketplacePage() {
  const [input, setInput] = useState("");
  const q = useDebounced(input.trim(), SEARCH_DEBOUNCE_MS);
  const agents = useQuery({
    queryKey: ["marketplace", q],
    queryFn: () => api.marketplace(q),
    placeholderData: keepPreviousData,
  });

  return (
    <>
      <PageHeader
        title="Marketplace"
        description="Agent public, gọi qua A2A gateway và trả phí mỗi lần gọi bằng x402."
        actions={
          <div className="relative w-full sm:w-64">
            <Search className="text-muted-foreground pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2" />
            <Input
              type="search"
              aria-label="Tìm agent"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Tên, mô tả hoặc skill…"
              className="pl-8"
            />
          </div>
        }
      />
      <QueryState query={agents} feature="GET /marketplace/agents">
        {(rows) =>
          rows.length === 0 ? (
            <p className="text-muted-foreground rounded-lg border border-dashed p-8 text-center text-sm">
              {q
                ? `Không có agent nào khớp "${q}".`
                : "Chưa có agent public nào. Agent xuất hiện ở đây khi đã đăng ký xong và bật public."}
            </p>
          ) : (
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
              {rows.map((a) => (
                <AgentCard key={a.slug} agent={a} />
              ))}
            </div>
          )
        }
      </QueryState>
    </>
  );
}

function AgentCard({ agent }: { agent: MarketplaceAgent }) {
  const { data: net } = useNetwork();
  return (
    <Link
      to={`/marketplace/${agent.slug}`}
      className="focus-visible:ring-ring/50 rounded-xl outline-none focus-visible:ring-[3px]"
    >
      <Card className="hover:border-primary/50 h-full transition-colors">
        <CardHeader>
          <CardTitle>{agent.name}</CardTitle>
          <CardDescription className="line-clamp-3">{agent.description}</CardDescription>
        </CardHeader>
        <CardContent className="mt-auto space-y-3 text-sm">
          {agent.skills.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {agent.skills.map((s) => (
                <Badge key={s} variant="secondary">
                  {s}
                </Badge>
              ))}
            </div>
          )}
          <div className="flex items-baseline justify-between gap-2 border-t pt-3">
            <span>
              <span className="text-base font-semibold">{formatAtomic(agent.price_atomic)}</span>{" "}
              {net?.payment_asset ?? "USDC"}
              <span className="text-muted-foreground"> / lần gọi</span>
            </span>
            <Badge variant="outline">{agent.settlement_mode}</Badge>
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}
