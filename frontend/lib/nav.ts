import {
  Activity,
  BarChart3,
  Bookmark,
  Briefcase,
  Calculator,
  CalendarDays,
  Clock,
  Code2,
  Dices,
  FileText,
  FlaskConical,
  GitCompare,
  Grid3x3,
  Layers,
  LayoutDashboard,
  LineChart,
  Percent,
  ShieldAlert,
  SlidersHorizontal,
  Table,
  Target,
  TrendingDown,
  Trophy,
  Wallet,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  label: string;
  href: string;
  icon: LucideIcon;
}
export interface NavGroup {
  title: string | null;
  items: NavItem[];
}

export const NAV: NavGroup[] = [
  { title: null, items: [{ label: "Dashboard", href: "/", icon: LayoutDashboard }] },
  {
    title: "Backtest",
    items: [
      { label: "Configuration", href: "/backtest/configuration", icon: SlidersHorizontal },
      { label: "Trade Explorer", href: "/backtest/trades", icon: Table },
      { label: "Equity Curve", href: "/backtest/equity", icon: LineChart },
      { label: "Drawdowns", href: "/backtest/drawdowns", icon: TrendingDown },
    ],
  },
  {
    title: "Analysis",
    items: [
      { label: "Performance", href: "/analysis/performance", icon: CalendarDays },
      { label: "Time Analysis", href: "/analysis/time", icon: Clock },
      { label: "MFE / MAE", href: "/analysis/mfe-mae", icon: Target },
      { label: "Regimes", href: "/analysis/regimes", icon: Layers },
      { label: "Distributions", href: "/analysis/distributions", icon: BarChart3 },
    ],
  },
  {
    title: "Robustness",
    items: [
      { label: "Monte Carlo", href: "/robustness/monte-carlo", icon: Dices },
      { label: "Walk Forward", href: "/robustness/walk-forward", icon: Activity },
      { label: "Parameter Sensitivity", href: "/robustness/sensitivity", icon: Grid3x3 },
      { label: "Stress Tests", href: "/robustness/stress-tests", icon: ShieldAlert },
      { label: "Overfitting", href: "/robustness/overfitting", icon: FlaskConical },
    ],
  },
  {
    title: "Risk",
    items: [
      { label: "Position Sizing", href: "/risk/position-sizing", icon: Calculator },
      { label: "Risk of Ruin", href: "/risk/risk-of-ruin", icon: ShieldAlert },
      { label: "Losing Streaks", href: "/risk/losing-streaks", icon: TrendingDown },
      { label: "Risk Optimization", href: "/risk/optimization", icon: Percent },
    ],
  },
  {
    title: "Prop Firms",
    items: [
      { label: "Challenge Simulator", href: "/prop/challenge", icon: Briefcase },
      { label: "Pass Probability", href: "/prop/pass-probability", icon: Percent },
      { label: "Account Survival", href: "/prop/survival", icon: Activity },
      { label: "Payout Simulator", href: "/prop/payouts", icon: Wallet },
      { label: "Risk Optimizer", href: "/prop/optimizer", icon: Trophy },
    ],
  },
  {
    title: "Research",
    items: [
      { label: "Strategy Comparison", href: "/research/comparison", icon: GitCompare },
      { label: "Strategy Lab (your code)", href: "/research/strategy-lab", icon: Code2 },
      { label: "Experiments", href: "/research/experiments", icon: FlaskConical },
      { label: "Saved Strategies", href: "/research/saved", icon: Bookmark },
      { label: "Reports", href: "/research/reports", icon: FileText },
    ],
  },
];
