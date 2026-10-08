import { days, duration, int, money, num, pct, ratio, signedMoney } from "@/lib/format";
import type { Metrics } from "@/lib/types";
import { KpiCard, KpiGrid, signTone } from "./KpiCard";

/** The full 27-metric dashboard grid. All figures are NET of fees and slippage unless labelled gross. */
export function KpiSection({ m }: { m: Metrics }) {
  const wl = m.win_loss_ratio;
  return (
    <div className="space-y-2">
      <KpiGrid>
        <KpiCard label="Net Profit" value={signedMoney(m.net_profit)} tone={signTone(m.net_profit)} sub={`${pct(m.return_pct)} on start balance`} />
        <KpiCard label="Gross Profit" value={money(m.gross_profit)} tone="up" hint="Sum of winning trades, net of costs" />
        <KpiCard label="Gross Loss" value={money(m.gross_loss)} tone="down" hint="Sum of losing trades, net of costs" />
        <KpiCard label="Total Trades" value={int(m.total_trades)} sub={`${int(m.trading_days)} trading days`} />
        <KpiCard label="Winning Trades" value={int(m.winning_trades)} />
        <KpiCard label="Losing Trades" value={int(m.losing_trades)} />
      </KpiGrid>
      <KpiGrid>
        <KpiCard label="Win Rate" value={pct(m.win_rate)} />
        <KpiCard label="Profit Factor" value={ratio(m.profit_factor)} tone={(m.profit_factor ?? 0) >= 1 ? "up" : "down"} hint="Gross profit / gross loss. Below 1.0 loses money." />
        <KpiCard label="Expectancy" value={signedMoney(m.expectancy, 2)} tone={signTone(m.expectancy)} sub="per trade, after costs" />
        <KpiCard label="Average Winner" value={money(m.average_winner, 2)} tone="up" />
        <KpiCard label="Average Loser" value={money(m.average_loser, 2)} tone="down" />
        <KpiCard label="Win / Loss Ratio" value={wl === null || wl === undefined ? "–" : num(wl)} />
      </KpiGrid>
      <KpiGrid>
        <KpiCard label="Sharpe Ratio" value={ratio(m.sharpe)} tone={signTone(m.sharpe)} hint="Daily returns, annualised √252, risk-free 0" />
        <KpiCard label="Sortino Ratio" value={m.sortino === null || (m.sortino ?? 0) > 999 ? "–" : ratio(m.sortino)} tone={signTone(m.sortino)} />
        <KpiCard label="Calmar Ratio" value={ratio(m.calmar)} tone={signTone(m.calmar)} hint="CAGR / max drawdown %" />
        <KpiCard label="Recovery Factor" value={ratio(m.recovery_factor)} hint="Net profit / max drawdown" />
        <KpiCard label="Max Drawdown" value={money(m.max_drawdown)} tone="down" sub="after every closed trade" />
        <KpiCard label="Max Drawdown %" value={pct(m.max_drawdown_pct)} tone="down" />
      </KpiGrid>
      <KpiGrid>
        <KpiCard label="Average Drawdown" value={money(m.average_drawdown)} />
        <KpiCard label="Longest Drawdown" value={days(m.longest_drawdown_days)} />
        <KpiCard label="Max Consec. Wins" value={int(m.max_consecutive_wins)} />
        <KpiCard label="Max Consec. Losses" value={int(m.max_consecutive_losses)} />
        <KpiCard label="Largest Winner" value={money(m.largest_winner)} tone="up" />
        <KpiCard label="Largest Loser" value={money(m.largest_loser)} tone="down" />
      </KpiGrid>
      <KpiGrid>
        <KpiCard label="Avg Holding Time" value={duration(m.average_holding_minutes)} />
        <KpiCard label="Total Fees" value={money(m.total_fees)} tone="warn" hint="Commission + exchange fees" />
        <KpiCard label="Slippage Cost" value={money(m.slippage_cost)} tone="warn" hint="Slippage + half-spread on market fills" />
        <KpiCard label="Gross P&L (pre-cost)" value={signedMoney(m.gross_pnl_total)} tone={signTone(m.gross_pnl_total)} hint="Before fees and slippage" />
        <KpiCard label="Edge p-value" value={m.expectancy_pvalue === null || m.expectancy_pvalue === undefined ? "–" : num(m.expectancy_pvalue, 3)} hint="t-test of average trade vs 0. Above 0.05 = can't rule out luck." tone={(m.expectancy_pvalue ?? 1) <= 0.05 && (m.expectancy ?? 0) > 0 ? "up" : "warn"} />
        <KpiCard label="Avg R" value={num(m.avg_r, 3)} tone={signTone(m.avg_r)} hint="Average net P&L as a multiple of initial risk" />
      </KpiGrid>
    </div>
  );
}
