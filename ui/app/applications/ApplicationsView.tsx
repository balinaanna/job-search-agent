"use client";

import { useCallback,useEffect,useState } from "react";

type Job={id:string;company:string;role:string;location:string|null;postingUrl:string;fitScore:number;recommendation:string;workflowStatus?:string;workflowUpdatedAt?:string|null};
const inactive=new Set(["not_started","analysis_requested","analysis_running","analysis_completed","analysis_failed","decide_later","pass"]);
function label(value:string|undefined){return(value||"not started").replaceAll("_"," ").replace(/\b\w/g,letter=>letter.toUpperCase());}
function date(value:string|null|undefined){return value?new Intl.DateTimeFormat("en-CA",{month:"short",day:"numeric",year:"numeric",timeZone:"UTC"}).format(new Date(value)):"Date unavailable";}

export function ApplicationsView(){
  const [jobs,setJobs]=useState<Job[]>([]),[error,setError]=useState("");
  const load=useCallback(()=>fetch("http://localhost:8787/api/jobs").then(async response=>{const value=await response.json();if(!response.ok)throw new Error(value.error);setJobs((value.analyzedJobs||[]).filter((job:Job)=>!inactive.has(job.workflowStatus||"analysis_completed")));}).catch(value=>setError(value instanceof Error?value.message:"Applications could not be loaded.")),[]);
  useEffect(()=>{void load();const changed=()=>void load();window.addEventListener("jobs-changed",changed);return()=>window.removeEventListener("jobs-changed",changed);},[load]);
  if(error)return <p className="applications-empty">{error}</p>;
  if(!jobs.length)return <section className="applications-empty"><span>NO ACTIVE APPLICATIONS</span><h2>Your application workspace is clear</h2><p>When you choose to pursue a job and begin preparing its strategy or materials, it will appear here.</p><a href="/#jobs">Review jobs</a></section>;
  return <div className="applications-list">{jobs.map(job=><article key={job.id}><div><span>{label(job.workflowStatus)}</span><h2>{job.role}</h2><p>{job.company} · {job.location||"Location not stated"}</p></div><div className="application-card-meta"><strong>{job.fitScore}%</strong><small>Updated {date(job.workflowUpdatedAt)}</small><a href={job.postingUrl} target="_blank" rel="noreferrer">View posting</a></div></article>)}</div>;
}
