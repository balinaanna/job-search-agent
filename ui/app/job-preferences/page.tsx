import { JobPreferences } from "../JobPreferences";

export default function JobPreferencesPage(){
  return <main className="app-shell job-preferences-page-shell">
    <aside className="sidebar"><div className="brand"><span className="brand-mark">A</span><span>Anna&apos;s job search</span></div><nav aria-label="Main navigation"><a className="nav-item" href="/"><span>⌂</span> Overview</a><a className="nav-item" href="/#jobs"><span>◎</span> Jobs</a><a className="nav-item" href="/add-jobs"><span>＋</span> Add jobs</a><a className="nav-item" href="/applications"><span>▤</span> Applications</a><a className="nav-item" href="/profile"><span>◇</span> Career profile</a><a className="nav-item active" href="/job-preferences"><span>⚙</span> Job preferences</a></nav><div className="sidebar-note"><span className="status-dot"/><div><strong>Guides fit scoring</strong><small>Separate from your verified career evidence.</small></div></div></aside>
    <section className="workspace job-preferences-workspace"><header className="page-intro"><p className="eyebrow">FIT &amp; APPLICATION</p><h1>Job preferences</h1><p>Control the target roles, work arrangement, fit-scoring weights, and hard-reject rules used when analyzing a job.</p></header><JobPreferences/><footer>Changes apply to future job-fit analyses.</footer></section>
  </main>;
}
