/**
 * Navigation catalog + role-filtered sidebar items.
 */

import type { LucideIcon } from "lucide-react";
import {
  BarChart3,
  Bot,
  FileSearch,
  History,
  KeyRound,
  LayoutDashboard,
  MessageSquare,
  Scale,
  ScrollText,
  Settings,
  Shield,
  Sparkles,
  Swords,
  Users,
} from "lucide-react";

import {
  hasFeature,
  SIDEBAR_HIDDEN_FEATURES,
  type FeatureKey,
} from "@/lib/permissions";
import { normalizeRole, type Role } from "@/lib/roles";

export type NavItem = {
  href: string;
  label: string;
  icon: LucideIcon;
  feature: FeatureKey;
};

export const MAIN_NAV: NavItem[] = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard, feature: "dashboard" },
  { href: "/playground", label: "Playground", icon: MessageSquare, feature: "playground" },
  { href: "/arena", label: "Arena", icon: Swords, feature: "arena" },
  { href: "/history", label: "Prompt History", icon: History, feature: "history" },
  { href: "/router", label: "Task Router", icon: Sparkles, feature: "router" },
  { href: "/evaluation", label: "Evaluation", icon: Scale, feature: "evaluation" },
  { href: "/rag", label: "Enterprise RAG", icon: FileSearch, feature: "rag" },
  { href: "/agents", label: "AI Agents", icon: Bot, feature: "agents" },
  { href: "/analytics", label: "Analytics", icon: BarChart3, feature: "analytics" },
  { href: "/governance", label: "Governance", icon: Shield, feature: "governance" },
  { href: "/audit", label: "Audit Logs", icon: ScrollText, feature: "audit" },
  { href: "/users", label: "Users & RBAC", icon: Users, feature: "users" },
  { href: "/api-keys", label: "API Keys", icon: KeyRound, feature: "api_keys" },
  { href: "/settings", label: "Settings", icon: Settings, feature: "settings" },
];

export function getNavigationForRole(role: string | null | undefined): NavItem[] {
  const normalized = normalizeRole(role);
  const hidden = new Set(SIDEBAR_HIDDEN_FEATURES[normalized as Role] ?? []);
  return MAIN_NAV.filter(
    (item) => hasFeature(normalized, item.feature) && !hidden.has(item.feature),
  );
}
