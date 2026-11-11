import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { PageHeader } from "@/components/page-header";
import { QueryState } from "@/components/query-state";
import { StatusBadge } from "@/components/status-badge";
import { Card, CardContent } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { api } from "@/lib/api";
import { useNetwork } from "@/hooks/use-network";
import { assetLabel, formatAtomic, shortAddress } from "@/lib/format";

export function JobsPage() {
  const jobs = useQuery({ queryKey: ["jobs"], queryFn: api.jobs.list });
  const { data: net } = useNetwork();

  return (
    <>
      <PageHeader
        title="Log job"
        description="Job từ A2A gateway (x402) hoặc indexer (ERC-8183 JobFunded)."
      />
      <Card>
        <CardContent>
          <QueryState query={jobs} feature="GET /jobs">
            {(rows) =>
              rows.length === 0 ? (
                <p className="text-muted-foreground p-6 text-center text-sm">
                  Chưa có job nào. Job xuất hiện khi client gọi agent qua A2A và trả phí x402.
                </p>
              ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Thời gian</TableHead>
                    <TableHead>Trạng thái</TableHead>
                    <TableHead>Settlement</TableHead>
                    <TableHead>Client</TableHead>
                    <TableHead>Số tiền</TableHead>
                    <TableHead>Deliverable</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {rows.map((j) => (
                    <TableRow key={j.id}>
                      <TableCell>
                        <Link to={`/jobs/${j.id}`} className="font-medium hover:underline">
                          {new Date(j.created_at).toLocaleString()}
                        </Link>
                      </TableCell>
                      <TableCell>
                        <StatusBadge status={j.status} />
                      </TableCell>
                      <TableCell>{j.settlement_mode}</TableCell>
                      <TableCell className="font-mono text-xs">{shortAddress(j.client_address)}</TableCell>
                      <TableCell>
                        {formatAtomic(j.amount_atomic)} {assetLabel(j.asset, net)}
                      </TableCell>
                      <TableCell className="max-w-48 truncate font-mono text-xs">
                        {j.deliverable_uri ?? "—"}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
              )
            }
          </QueryState>
        </CardContent>
      </Card>
    </>
  );
}
