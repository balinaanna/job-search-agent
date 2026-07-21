import { ProfileManager } from "../ProfileManager";
import { MasterResume } from "./MasterResume";

export default function CareerProfilePage(){
  return <main className="app-shell profile-page-shell">
    <aside className="sidebar"><div className="brand"><span className="brand-mark">A</span><span>Anna&apos;s job search</span></div><nav aria-label="Main navigation"><a className="nav-item" href="/"><span>⌂</span> Overview</a><a className="nav-item" href="/#jobs"><span>◎</span> Jobs</a><a className="nav-item" href="/#applications"><span>▤</span> Applications</a><a className="nav-item active" href="/profile"><span>◇</span> Career profile</a></nav><div className="sidebar-note"><span className="status-dot"/><div><strong>Your master evidence</strong><small>Profile changes require review and approval.</small></div></div></aside>
    <section className="workspace profile-workspace"><MasterResume/><ProfileManager/><footer>Verified career evidence · Profile changes never apply without explicit approval.</footer></section>
  </main>;
}
