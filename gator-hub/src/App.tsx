import { ReactElement, useEffect, useState } from 'react'
import moment from 'moment'
// import * as bootstrap from "bootstrap"

import mascot from "./assets/mascot_white.svg?url"

interface ApiCompletion { uid       ?: number,
                          db_file   ?: string,
                          timestamp ?: number }

interface ApiJob { uid       : number,
                   id        : string,
                   server_url: string,
                   timestamp : number,
                   completion: ApiCompletion }

interface ApiMsg { uid       : number,
                   severity  : number,
                   message   : string,
                   timestamp : number }

const Severity : { [key: number]: string } = {
    10: "DEBUG",
    20: "INFO",
    30: "WARNING",
    40: "ERROR",
    50: "CRITICAL"
};

function Breadcrumb ({ }) {
    return (
        <nav aria-label="breadcrumb">
            <ol className="breadcrumb">
                <li className="breadcrumb-item"><a href="#">Home</a></li>
                <li className="breadcrumb-item active" aria-current="page">Library</li>
            </ol>
        </nav>
    );
}

function Job ({ job, focus, setJobFocus } : { job : ApiJob, focus : ApiJob | undefined, setJobFocus : (focus : ApiJob) => void }) {
    let date = moment(job.timestamp * 1000);
    return (
        <tr onClick={() => { setJobFocus(job); }} className={(focus && focus.uid == job.uid) ? "active" : ""}>
            <td>
                <strong>{job.uid}: {job.id}</strong>{job.completion.uid ? 'X' : 'O'}<br />
                <small>peterbirch - {date.format("DD/MM/YY @ HH:mm")}</small>
            </td>
        </tr>
    );
}

function Message ({ msg } : { msg : ApiMsg }) {
    let date = moment(msg.timestamp * 1000);
    let sevstr = Severity[msg.severity];
    return (
        <tr>
            <td>{date.format("HH:mm:ss")}</td>
            <td className={"msg_" + sevstr.toLowerCase()}>{sevstr}</td>
            <td>{msg.message}</td>
        </tr>
    );
}

function fetchJobs (setJobs : CallableFunction) {
    let inner = () => {
        let all_jobs : ApiJob[] = [];
        fetch("/api/jobs")
            .then((response) => response.json())
            .then((data) => {
                all_jobs = [...all_jobs, ...data];
                all_jobs.sort((a, b) => (b.uid - a.uid));
                setJobs(all_jobs)
            })
            .catch((err) => console.error(err.message))
            .finally(() => setTimeout(inner, 1000));
    };
    inner();
}

function MessageViewer ({ job } : { job : ApiJob | undefined }) {
    // If no job provided, return an empty table
    if (job === undefined) {
        return (
            <table className="table table-striped table-sm">
                <thead>
                    <tr>
                        <th className="col-1">Time</th>
                        <th className="col-1">Severity</th>
                        <th className="col-10">Message</th>
                    </tr>
                </thead>
                <tbody></tbody>
            </table>
        );
    }

    // Otherwise, fetch and draw messages
    const [messages, setMessages] = useState<ApiMsg[]>([]);

    // Periodically fetch new messages
    useEffect(() => {
        let   last_uid           = 0;
        let   all_msg : ApiMsg[] = [];
        const poll_id  = setInterval(() => {
            fetch(`/api/job/${job.uid}/messages?after=${last_uid}&limit=20`)
                .then((response) => response.json())
                .then((data) => {
                    all_msg = [...all_msg, ...data];
                    setMessages(all_msg);
                    last_uid = Math.max(...data.map((msg : ApiMsg) => msg.uid)) + 1;
                })
                .catch((err) => console.error(err.message));
        }, 1000);
        return () => {
            clearInterval(poll_id);
            setMessages([]);
        };
    }, [job]);

    // Render messages
    let msg_elems : ReactElement[] = messages.map((msg) => <Message msg={msg} />);

    return (
        <table className="table table-striped table-sm">
            <thead>
                <tr>
                    <th className="col-1">Time</th>
                    <th className="col-1">Severity</th>
                    <th className="col-10">Message</th>
                </tr>
            </thead>
            <tbody>{msg_elems}</tbody>
        </table>
    );
}

export default function App() {
    const [jobs, setJobs] = useState<ApiJob[]>([]);
    const [job_focus, setJobFocus] = useState<ApiJob | undefined>(undefined);

    useEffect(() => fetchJobs(setJobs), []);

    let job_elems : ReactElement[] = jobs.map((job) =>
        <Job job={job} focus={job_focus} setJobFocus={setJobFocus} />
    );

    return (
        <>
            <header className="navbar navbar-dark bg-dark sticky-top shadow">
                <div className="container-fluid">
                    <a className="navbar-brand" href="#">
                        <img src={mascot}
                            height="24"
                            className="d-inline-block align-text-top"
                            style={{ marginRight: "5px" }} />
                        Gator Hub
                    </a>
                    <div className="flex-fill"></div>
                    <div className="navbar-text"><Breadcrumb /></div>
                </div>
            </header>
            <div className="container-fluid">
                <div className="row">
                    <nav className="col-2 bg-light sidebar">
                        <table className="table table-sm">
                            <tbody>{job_elems}</tbody>
                        </table>
                    </nav>
                    <main className="col-10" style={{ marginLeft: "auto" }}>
                        <MessageViewer job={job_focus} />
                    </main>
                </div>
            </div>
        </>
    )
}
