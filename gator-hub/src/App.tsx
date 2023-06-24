import { ReactElement, useEffect, useState, useRef } from 'react'
import moment from 'moment'

import 'datatables.net-bs5/css/dataTables.bootstrap5.css'
import DataTable from 'datatables.net-bs5'
import 'datatables.net-scroller-bs5'

import mascot from "./assets/mascot_white.svg?url"

interface ApiCompletion { uid       ?: number,
                          db_file   ?: string,
                          timestamp ?: number }

interface ApiJob { uid       : number,
                   id        : string,
                   server_url: string,
                   timestamp : number,
                   completion: ApiCompletion }

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
    // If no job provided, return an empty pane
    if (job === undefined) return <></>;

    const ref = useRef<HTMLTableElement>(null);

    useEffect(() => {
        const dt = new (DataTable as any)(ref.current!, {
            columns       : [{ data: "timestamp" },
                             { data: "severity"  },
                             { data: "message"   }],
            searching     : false,
            ordering      : false,
            deferRender   : true,
            scrollY       : 600,
            scrollCollapse: true,
            scroller      : { serverWait: 10 },
            serverSide    : true,
            ajax          : (request : any, callback : any) => {
                let start = request.start;
                let limit = request.length;
                if (limit < 0) limit = 100;
                fetch(`/api/job/${job.uid}/messages?after=${start}&limit=${limit}`)
                    .then((response) => response.json())
                    .then((data) => {
                        callback({ draw: request.draw,
                                   data: data.messages.map((msg : any) => {
                                       msg.timestamp = moment(msg.timestamp * 1000).format("HH:mm:ss");
                                       msg.severity  = Severity[msg.severity];
                                       return msg;
                                   }),
                                   recordsTotal: data.total,
                                   recordsFiltered: data.total });
                    })
                    .catch((err) => console.error(err.message));
            }
        });
        let reload = setInterval(
            () => {
                dt.ajax.reload((data : any) => {
                    dt.scroller.toPosition(data.recordsTotal + 200);
                }, false);
            },
            2000
        );
        return () => {
            clearInterval(reload);
            dt.destroy()
        };
    }, [job]);

    return <table className="table table-striped table-sm" ref={ref}>
        <thead>
            <tr>
                <th>Time</th>
                <th>Severity</th>
                <th>Message</th>
            </tr>
        </thead>
    </table>;
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
