"use client";

import { useEffect, useState } from "react";

type Summary = {
  files_processed:string[]; files_skipped:string[]; changes:string[]; warnings:string[];
  review_items?:Array<{category:string;action:"Added"|"Updated"|"Removed";fact:string;reason:string}>;
  changed_sections?:string[]; profile_version?:string; backup?:string;
};
type ProfileRun = { id:string; status:string; files:string[]; after_version?:string|null; error?:string|null; summary?:Summary|null };
type ProfileStatus = { profile_version:string; latest_run?:ProfileRun|null };

function profileRequestError(response:Response, value:{error?:string}) {
  return response.status===404
    ? "The running workflow service is an older version. Stop it and restart the app, then try again."
    : value.error||"Profile request failed.";
}

export function ProfileManager() {
  const [status,setStatus]=useState<ProfileStatus|null>(null), [files,setFiles]=useState<File[]>([]), [instructions,setInstructions]=useState(""), [run,setRun]=useState<ProfileRun|null>(null), [message,setMessage]=useState(""), [reviewing,setReviewing]=useState(false), [inputKey,setInputKey]=useState(0), [selectedItems,setSelectedItems]=useState<number[]>([]);
  const working=Boolean(run&&["requested","running","approval_running"].includes(run.status));
  const awaitingReview=run?.status==="proposal_ready";
  useEffect(()=>{fetch("http://localhost:8787/api/profile").then(response=>response.ok?response.json():null).then(value=>{if(value){setStatus(value);if(value.latest_run){setRun(value.latest_run);if(value.latest_run.status==="proposal_ready")setSelectedItems((value.latest_run.summary?.review_items||[]).map((_:unknown,index:number)=>index));}}}).catch(()=>undefined);},[]);
  useEffect(()=>{
    if(!working||!run)return;
    const timer=window.setInterval(async()=>{
      const response=await fetch(`http://localhost:8787/api/profile/runs/${run.id}`); if(!response.ok)return;
      const next=await response.json(); setRun(next);
      if(next.status==="proposal_ready"){if(!next.error)setSelectedItems((next.summary?.review_items||[]).map((_:unknown,index:number)=>index));setMessage(next.error||"Proposal ready. Review every change before applying it.");}
      if(next.status==="completed"){setMessage("Selected changes applied. Existing fit analyses are now marked for review.");setFiles([]);setInstructions("");setInputKey(key=>key+1);setStatus(current=>current?{...current,profile_version:next.after_version,latest_run:next}:current);window.dispatchEvent(new Event("jobs-changed"));}
      if(next.status==="failed")setMessage(next.error||"Profile proposal failed.");
    },1500);
    return()=>window.clearInterval(timer);
  },[working,run]);

  async function rebuild(){
    const body=new FormData(); files.forEach(file=>body.append("resumes",file)); body.append("instructions",instructions);
    setMessage("Uploading resumes and preparing a verified proposal…");
    try{const response=await fetch("http://localhost:8787/api/profile/rebuild",{method:"POST",body});const value=await response.json();if(!response.ok)throw new Error(profileRequestError(response,value));setRun(value);setMessage("Profile proposal queued. Nothing will change without your approval.");}
    catch(error){setMessage(error instanceof TypeError?"Profile service is offline.":error instanceof Error?error.message:"Profile proposal could not start.");}
  }

  async function review(action:"approve"|"reject"){
    if(!run)return; setReviewing(true);
    try{const response=await fetch(`http://localhost:8787/api/profile/runs/${run.id}/${action}`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({selected_items:selectedItems})});const value=await response.json();if(!response.ok)throw new Error(profileRequestError(response,value));setRun(value);
      if(action==="approve")setMessage("Validating and applying your selected changes…");
      else setMessage("Proposal rejected. Your career profile was not changed.");
    }catch(error){setMessage(error instanceof Error?error.message:"Profile review could not be saved.");}finally{setReviewing(false);}
  }

  const latest=run||status?.latest_run, proposal=latest?.status==="proposal_ready"?latest.summary:null;
  return <section className="profile-manager" id="profile">
    <div className="section-heading"><div><p className="eyebrow">VERIFIED CAREER PROFILE</p><h2>Rebuild profile from resumes</h2></div><span>Version {status?.profile_version||"loading"}</span></div>
    <p>Upload up to 10 PDF resumes. The agent prepares a reconciled proposal for career, evidence, skills, and technologies. Your protected contacts and current profile remain unchanged until you approve.</p>
    <input key={inputKey} aria-label="Resume PDFs" type="file" accept="application/pdf,.pdf" multiple onChange={event=>setFiles(Array.from(event.target.files||[]))}/>
    <textarea aria-label="Profile rebuild instructions" rows={3} value={instructions} onChange={event=>setInstructions(event.target.value)} placeholder="Optional rules, e.g. omit a role, preserve a title, or consolidate older work."/>
    <div className="profile-rebuild-actions"><span>{files.length?`${files.length} PDF${files.length===1?"":"s"} selected`:"No resumes selected"}</span><button disabled={working||awaitingReview||files.length<1||files.length>10} onClick={rebuild}>{working?"Preparing proposal…":awaitingReview?"Review proposal below":"Upload and prepare proposal"}</button></div>
    {message&&<small role="status">{message}</small>}
    {proposal&&<section className="profile-proposal" aria-label="Profile change proposal">
      <header><div><strong>Review proposed profile</strong><span>{proposal.files_processed.length} resume(s) processed · {(proposal.changed_sections||[]).join(", ")||"No sections changed"}</span></div><span>Not applied</span></header>
      {proposal.warnings.length>0&&<div className="profile-proposal-warnings"><strong>Warnings to review</strong><ul>{proposal.warnings.map(item=><li key={item}>{item}</li>)}</ul></div>}
      <div className="profile-fact-review">{proposal.review_items?.length?proposal.review_items.map((item,index)=><label className={selectedItems.includes(index)?"selected":"rejected"} key={`${item.category}-${item.fact}-${index}`}><input type="checkbox" checked={selectedItems.includes(index)} onChange={()=>setSelectedItems(current=>current.includes(index)?current.filter(value=>value!==index):[...current,index])}/><span className={`fact-action ${item.action.toLowerCase()}`}>{item.action}</span><div><small>{item.category}</small><strong>{item.fact}</strong><p>{item.reason}</p><em>{selectedItems.includes(index)?"Included in rebuild":"Rejected — will not be applied"}</em></div></label>):proposal.changes.map(item=><article key={item}><span className="fact-action updated">Updated</span><div><small>Career profile</small><strong>{item}</strong></div></article>)}</div>
      <div className="profile-review-actions"><span>{proposal.review_items?.length?`${selectedItems.length} of ${proposal.review_items.length} changes selected`:`${proposal.changes.length} changes in proposal`}</span><button className="reject" disabled={reviewing} onClick={()=>review("reject")}>Reject entire proposal</button><button disabled={reviewing||Boolean(proposal.review_items?.length&&selectedItems.length===0)} onClick={()=>review("approve")}>{reviewing?"Saving decision…":"Approve selected and rebuild"}</button></div>
    </section>}
    {latest?.status==="completed"&&latest.summary&&<details className="profile-rebuild-summary"><summary>Latest approved rebuild</summary><strong>{latest.summary.files_processed.length} resume(s) processed</strong><ul>{latest.summary.changes.map(item=><li key={item}>{item}</li>)}</ul></details>}
  </section>;
}
