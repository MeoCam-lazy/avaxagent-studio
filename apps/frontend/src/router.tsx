import { createBrowserRouter, type RouteObject } from "react-router-dom";

import { AppShell } from "@/components/layout/app-shell";
import { RequireAuth } from "@/components/require-auth";
import { AgentDetailPage } from "@/pages/agents/detail";
import { AgentsListPage } from "@/pages/agents/list";
import { NewAgentPage } from "@/pages/agents/new";
import { DashboardPage } from "@/pages/dashboard";
import { JobsPage } from "@/pages/jobs";
import { MarketplacePage } from "@/pages/marketplace";
import { NotFoundPage } from "@/pages/not-found";
import { WalletPage } from "@/pages/wallet";

export const routes: RouteObject[] = [
  {
    element: <AppShell />,
    children: [
      {
        element: <RequireAuth />,
        children: [
          { index: true, element: <DashboardPage /> },
          { path: "agents", element: <AgentsListPage /> },
          { path: "agents/new", element: <NewAgentPage /> },
          { path: "agents/:id", element: <AgentDetailPage /> },
          { path: "wallet", element: <WalletPage /> },
          { path: "jobs", element: <JobsPage /> },
        ],
      },
      { path: "marketplace", element: <MarketplacePage /> },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
];

export const router = createBrowserRouter(routes);
