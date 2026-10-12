import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import { Analytics, api, ImportResult, Lead, Outcome, RankedLead, SegmentMetric, Target } from "./api";
import "./styles.css";


const objectives: Array<{ value: Target; label: string }> = [
  { value: "replied", label: "Replies" },
  { value: "interested", label: "Interested" },
  { value: "meeting_booked", label: "Meetings booked" }
];

const outcomes: Array<{ value: "" | Outcome; label: string }> = [
  { value: "", label: "No outcome" },
  { value: "replied", label: "Replied" },
  { value: "interested", label: "Interested" },
  { value: "meeting_booked", label: "Meeting booked" },
  { value: "disqualified", label: "Disqualified" }
];

const dimensionLabels: Record<string, string> = {
  industry: "Industry",
  employee_band: "Company size",
  message_variant: "Message"
};

const pluralize = (count: number, noun: string) => `${count} ${noun}${count === 1 ? "" : "s"}`;
const percent = (value: number) => `${Math.round(value * 100)}%`;
const signed = (value: number) => (value > 0 ? `+${value}` : String(value));


function EmptyState() {
  return (
    <section className="empty-state card">
      <span className="eyebrow">Ready for evidence</span>
      <h2>Import your first outcome file</h2>
      <p>Start with at least 30 labeled leads. We will show observed patterns without changing your source scores.</p>
    </section>
  );
}


function InsightCard({ metric }: { metric: SegmentMetric }) {
  const tone = metric.adjustment > 0 ? "positive" : metric.adjustment < 0 ? "negative" : "neutral";
  return (
    <article className={`insight ${tone}`}>
      <div className="insight-head">
        <span>{dimensionLabels[metric.dimension]}</span>
        <strong>{metric.lift.toFixed(1)}×</strong>
      </div>
      <h3>{metric.segment}</h3>
      <p>{metric.recommendation}</p>
      <small>{pluralize(metric.observations, "labeled lead")} · observed correlation</small>
    </article>
  );
}


function PerformanceTable({ title, metrics }: { title: string; metrics: SegmentMetric[] }) {
  return (
    <div className="performance-panel">
      <h3>{title}</h3>
      <div className="table-wrap compact-table">
        <table>
          <thead>
            <tr><th>Segment</th><th>Sample</th><th>Rate</th><th>Lift</th></tr>
          </thead>
          <tbody>
            {metrics.map((metric) => (
              <tr key={`${metric.dimension}-${metric.segment}`}>
                <td>{metric.segment}</td>
                <td>{metric.observations}</td>
                <td>{percent(metric.rate)}</td>
                <td><span className={metric.eligible ? "lift eligible" : "lift"}>{metric.eligible ? `${metric.lift.toFixed(1)}×` : "Learning"}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}


export default function App() {
  const [target, setTarget] = useState<Target>("replied");
  const [leads, setLeads] = useState<Lead[]>([]);
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [ranking, setRanking] = useState<RankedLead[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const [importResult, setImportResult] = useState<ImportResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async (objective: Target) => {
    setError(null);
    try {
      const [leadPage, analysis, ranked] = await Promise.all([
        api.leads(),
        api.analytics(objective),
        api.rankings(objective)
      ]);
      setLeads(leadPage.items);
      setAnalytics(analysis);
      setRanking(ranked.items);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not load the dashboard");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh(target);
  }, [refresh, target]);

  const insights = useMemo(
    () =>
      (analytics?.metrics || [])
        .filter((metric) => metric.eligible && (metric.dimension === "message_variant" || metric.adjustment !== 0))
        .sort((a, b) => Math.abs(b.lift - 1) - Math.abs(a.lift - 1))
        .slice(0, 4),
    [analytics]
  );

  const groupedMetrics = useMemo(
    () =>
      ["industry", "employee_band", "message_variant"].map((dimension) => ({
        dimension,
        metrics: (analytics?.metrics || []).filter((metric) => metric.dimension === dimension)
      })),
    [analytics]
  );

  async function handleImport(event: FormEvent) {
    event.preventDefault();
    if (!file) {
      setError("Choose a CSV file first");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const result = await api.importLeads(file);
      setImportResult(result);
      await refresh(target);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Import failed");
    } finally {
      setBusy(false);
    }
  }

  async function handleOutcome(leadId: number, outcome: string) {
    if (!outcome) return;
    setBusy(true);
    setError(null);
    try {
      await api.updateOutcome(leadId, outcome as Outcome);
      await refresh(target);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Outcome update failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <a className="brand" href="#top" aria-label="Signal Loop home">
          <span className="brand-mark" aria-hidden="true">S</span>
          <span><strong>Signal Loop</strong><small>for SaaSquatch exports</small></span>
        </a>
        <span className="status"><i /> Outcome learning active</span>
      </header>

      <main id="top">
        <section className="hero">
          <div>
            <span className="eyebrow">Outcome-calibrated ranking</span>
            <h1>Rank leads with evidence,<br />not assumptions.</h1>
            <p>Close the loop between who you target and what actually converts. Your source scores stay untouched.</p>
          </div>
          <form className="import-card" onSubmit={handleImport}>
            <div>
              <span className="step">01</span>
              <h2>Import outcomes</h2>
              <p>CSV · maximum 10,000 leads</p>
            </div>
            <label className="file-picker">
              <span>{file ? file.name : "Choose CSV file"}</span>
              <input
                aria-label="CSV file"
                type="file"
                accept=".csv,text/csv"
                onChange={(event) => setFile(event.target.files?.[0] || null)}
              />
            </label>
            <button className="primary-button" type="submit" disabled={busy}>{busy ? "Working…" : "Import leads"}</button>
            {importResult && <p className="success-message">Imported {pluralize(importResult.total_rows, "lead")}</p>}
          </form>
        </section>

        {error && <div className="error-banner" role="alert">{error}</div>}

        <section className="control-row">
          <div>
            <span className="eyebrow">Optimize for</span>
            <label className="select-label">
              <span className="sr-only">Ranking objective</span>
              <select aria-label="Ranking objective" value={target} onChange={(event) => setTarget(event.target.value as Target)}>
                {objectives.map((objective) => <option key={objective.value} value={objective.value}>{objective.label}</option>)}
              </select>
            </label>
          </div>
          <p>Recommendations unlock at 30 labeled leads overall and 10 per segment.</p>
        </section>

        {loading ? (
          <div className="loading-state">Reading your evidence…</div>
        ) : leads.length === 0 ? (
          <EmptyState />
        ) : (
          <>
            <section className="stats-grid" aria-label="Outcome summary">
              <article><span>Labeled outcomes</span><strong>{analytics?.labeled_count || 0}</strong><small>of {pluralize(leads.length, "lead")}</small></article>
              <article><span>Objective wins</span><strong>{analytics?.overall_successes || 0}</strong><small>{objectives.find((item) => item.value === target)?.label}</small></article>
              <article><span>Observed rate</span><strong>{percent(analytics?.overall_rate || 0)}</strong><small>Raw conversion</small></article>
              <article><span>Suggested moves</span><strong>{ranking.filter((item) => item.rank_delta !== 0).length}</strong><small>Preview only</small></article>
            </section>

            <section className="section-block">
              <div className="section-heading">
                <div><span className="step">02</span><h2>What the outcomes suggest</h2></div>
                <p>Observed correlations · never causal claims</p>
              </div>
              {insights.length ? (
                <div className="insight-grid">{insights.map((metric) => <InsightCard key={`${metric.dimension}-${metric.segment}`} metric={metric} />)}</div>
              ) : (
                <div className="learning-banner">Keep labeling outcomes. Recommendations appear when the sample guardrails are met.</div>
              )}
            </section>

            <section className="section-block">
              <div className="section-heading"><div><span className="step">03</span><h2>Performance by segment</h2></div></div>
              <div className="performance-grid">
                {groupedMetrics.map((group) => (
                  <PerformanceTable key={group.dimension} title={dimensionLabels[group.dimension]} metrics={group.metrics} />
                ))}
              </div>
            </section>

            <section className="section-block">
              <div className="section-heading">
                <div><span className="step">04</span><h2>Before versus after</h2></div>
                <p>Suggested scores never overwrite imported scores.</p>
              </div>
              <div className="table-wrap card-table">
                <table>
                  <thead><tr><th>Company</th><th>Rank movement</th><th>Score</th><th>Why</th></tr></thead>
                  <tbody>
                    {ranking.map((item) => (
                      <tr key={item.id}>
                        <td><strong>{item.company}</strong><small>{item.industry} · {item.employee_band}</small></td>
                        <td><span className={item.rank_delta > 0 ? "rank-up" : item.rank_delta < 0 ? "rank-down" : ""}>#{item.baseline_rank} → #{item.suggested_rank}</span></td>
                        <td><strong>{item.baseline_score}</strong> <span className="score-arrow">→</span> <strong>{item.suggested_score}</strong></td>
                        <td>{item.drivers.length ? item.drivers.join(" · ") : "No eligible adjustment"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>

            <section className="section-block">
              <div className="section-heading"><div><span className="step">05</span><h2>Lead outcomes</h2></div><p>Update results as conversations progress.</p></div>
              <div className="table-wrap card-table">
                <table>
                  <thead><tr><th>Company</th><th>Industry</th><th>Employees</th><th>Message</th><th>Outcome</th></tr></thead>
                  <tbody>
                    {leads.map((lead) => (
                      <tr key={lead.id}>
                        <td><strong>{lead.company}</strong><small>{lead.external_id}</small></td>
                        <td>{lead.industry}</td>
                        <td>{lead.employees}</td>
                        <td>{lead.message_variant}</td>
                        <td>
                          <select
                            aria-label={`Outcome for ${lead.company}`}
                            value={lead.outcome || ""}
                            disabled={busy}
                            onChange={(event) => void handleOutcome(lead.id, event.target.value)}
                          >
                            {outcomes.map((outcome) => <option key={outcome.value || "none"} value={outcome.value}>{outcome.label}</option>)}
                          </select>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          </>
        )}
      </main>

      <footer><span>Signal Loop</span><p>Outcome intelligence for better prospecting decisions.</p></footer>
    </div>
  );
}
