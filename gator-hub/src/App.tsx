import { ReactElement, useEffect, useState } from 'react'
import moment from 'moment'
// import * as bootstrap from "bootstrap"

import mascot from "./assets/mascot_white.svg?url"

interface ApiJob { db_uid    : number,
                   id        : string,
                   server_url: string,
                   timestamp : string }

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

function Job ({ job } : { job : ApiJob }) {
    let date = moment(job.timestamp);
    return (
        <tr>
            <td>
                <strong>{job.db_uid}: {job.id}</strong><br />
                <small>peterbirch - {date.format("DD/MM/YY @ HH:MM")}</small>
            </td>
        </tr>
    );
}

function Message ({ }) {
    return (
        <tr>
            <td>TIME</td>
            <td>SEVERITY</td>
            <td>TEXT</td>
        </tr>
    );
}

function fetch_jobs (setJobs : CallableFunction) {
    let inner = () => {
        console.log("FETCH JOBS");
        fetch("/api/jobs")
            .then((response) => response.json())
            .then((data) => setJobs(data))
            .catch((err) => console.error(err.message))
            .finally(() => setTimeout(inner, 1000));
    };
    inner();
}

export default function App() {
    const [jobs, setJobs] = useState([])

    useEffect(() => fetch_jobs(setJobs), []);

    let job_elems : ReactElement[] = [];
    jobs.forEach((job) => job_elems.push(<Job job={job} />))

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
                        <table className="table table-striped table-sm">
                            <thead>
                                <tr>
                                    <th className="col-1">Time</th>
                                    <th className="col-1">Severity</th>
                                    <th className="col-10">Message</th>
                                </tr>
                            </thead>
                            <tbody>
                                <Message />
                            </tbody>
                        </table>
                    </main>
                </div>
            </div>
        </>
    )
}
