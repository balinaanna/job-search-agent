import { AlertInbox } from "../AlertInbox";

export default function AddJobsPage(){
  return <main className="app-shell add-jobs-page-shell">
    <aside className="sidebar"><div className="brand"><span className="brand-mark">A</span><span>Anna&apos;s job search</span></div><nav aria-label="Main navigation"><a className="nav-item" href="/"><span>⌂</span> Overview</a><a className="nav-item" href="/#jobs"><span>◎</span> Jobs</a><a className="nav-item active" href="/add-jobs"><span>＋</span> Add jobs</a><a className="nav-item" href="/applications"><span>▤</span> Applications</a><a className="nav-item" href="/profile"><span>◇</span> Career profile</a></nav><div className="sidebar-note"><span className="status-dot"/><div><strong>One jobs workspace</strong><small>Every imported job appears in the unified Jobs list.</small></div></div></aside>
    <section className="workspace add-jobs-workspace"><header className="page-intro"><p className="eyebrow">JOB SOURCES</p><h1>Add jobs</h1><p>Bring jobs into your workspace automatically from Gmail alerts or manually from a saved alert email.</p></header><AlertInbox expanded/><footer>Imported jobs are deduplicated and added to the unified Jobs workspace.</footer></section>
  </main>;
}
