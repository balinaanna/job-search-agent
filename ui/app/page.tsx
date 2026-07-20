import data from "./dashboard-data.json";
import { JobsView } from "./JobsView";
import { FindJobsButton } from "./FindJobsButton";

export default function Home() {
  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">A</span>
          <span>Anna&apos;s job search</span>
        </div>
        <nav aria-label="Main navigation">
          <a className="nav-item active" href="#overview"><span>⌂</span> Overview</a>
          <a className="nav-item" href="#jobs"><span>◎</span> Jobs <b>{data.summary.awaitingAnalysis + data.analyzedJobs.length}</b></a>
          <a className="nav-item" href="#applications"><span>▤</span> Applications</a>
          <a className="nav-item" href="#profile"><span>◇</span> Career profile</a>
        </nav>
        <div className="sidebar-note">
          <span className="status-dot" />
          <div><strong>Your evidence is protected</strong><small>Every claim stays tied to verified experience.</small></div>
        </div>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div><p className="eyebrow">JOB SEARCH WORKSPACE</p><h1 id="overview">Good afternoon, Anna</h1></div>
          <FindJobsButton />
        </header>

        <section className="attention-card">
          <div className="attention-copy">
            <span className="kicker">NEXT BEST ACTION</span>
            <h2>{data.summary.awaitingAnalysis} promising jobs need a closer look</h2>
            <p>We found roles that match your search, but they need evidence-based analysis before you spend time applying.</p>
            <a className="primary-action" href="#analysis-queue">Review analysis queue <span>→</span></a>
          </div>
          <div className="progress-ring" aria-label={`${data.summary.awaitingAnalysis} jobs awaiting analysis`}>
            <strong>{data.summary.awaitingAnalysis}</strong><span>to analyze</span>
          </div>
        </section>

        <section className="stats" aria-label="Search summary">
          <article><span>Discovered</span><strong>{data.summary.discovered}</strong><small>active job leads</small></article>
          <article><span>Fully analyzed</span><strong>{data.analyzedJobs.length}</strong><small>checked against evidence</small></article>
          <article><span>Ready to pursue</span><strong>{data.summary.readyToPursue}</strong><small>strong or solid matches</small></article>
          <article><span>In progress</span><strong>{data.summary.applicationsInProgress}</strong><small>application packages</small></article>
        </section>

        <section className="content-grid" id="jobs">
          <JobsView analyzedJobs={data.analyzedJobs} awaitingAnalysis={data.awaitingAnalysis} />

          <aside className="pipeline" id="applications">
            <div className="section-heading"><div><p className="eyebrow">YOUR PIPELINE</p><h2>Application progress</h2></div></div>
            <ol>
              <li className="current"><span>1</span><div><strong>Discover & analyze</strong><small>{data.summary.awaitingAnalysis} waiting · {data.analyzedJobs.length} complete</small></div></li>
              <li><span>2</span><div><strong>Choose jobs</strong><small>{data.summary.readyToPursue} ready for your decision</small></div></li>
              <li><span>3</span><div><strong>Build application</strong><small>Strategy, resume and letter</small></div></li>
              <li><span>4</span><div><strong>Review & approve</strong><small>Nothing submits without you</small></div></li>
              <li><span>5</span><div><strong>Apply & track</strong><small>Final submission and follow-up</small></div></li>
            </ol>
          </aside>
        </section>

        <footer id="profile">Updated from your local job-search data · No application can be submitted without explicit approval.</footer>
      </section>
    </main>
  );
}
