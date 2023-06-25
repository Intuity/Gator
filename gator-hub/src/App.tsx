import { ReactElement, useEffect, useState, useRef } from 'react'
import moment from 'moment'

import 'datatables.net-bs5/css/dataTables.bootstrap5.css'
import DataTable from 'datatables.net-bs5'
import 'datatables.net-scroller-bs5'

import 'react-complex-tree/lib/style-modern.css'
import { UncontrolledTreeEnvironment,
         Tree,
         TreeDataProvider,
         TreeItemIndex,
         TreeItem } from 'react-complex-tree'

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
                <small>&lt;OWNER&gt; - {date.format("DD/MM/YY @ HH:mm")}</small>
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
            scrollY       : ref.current!.parentElement!.offsetHeight - 39,
            scrollCollapse: true,
            info          : false,
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

class JobTreeItem implements TreeItem {

    public isFolder?: boolean | undefined

    public constructor (public index    : TreeItemIndex,
                        public data     : ApiJob,
                        public children : TreeItemIndex[]) {
        console.log("Created JobTreeItem", index, data, children);
        this.isFolder = children.length > 0;
    }

}

class JobTreeProvider implements TreeDataProvider {

    public constructor (public job : ApiJob) { }

    public getTreeItem (itemId : TreeItemIndex) {
        return new Promise<JobTreeItem>((resolve) => {
            console.log("Resolving itemId:", itemId);
            if (itemId == "root") {
                resolve(new JobTreeItem(itemId, this.job, [this.job.uid.toString()]));
                return;
            }
            let parts = (itemId as string).split(".");
            fetch(`/api/job/${this.job.uid}/layer/${parts.slice(1).join('/')}`)
                .then((response) => response.json())
                .then((data) => {
                    console.log("GOT DATA", data);
                    resolve(new JobTreeItem(itemId,
                                            data,
                                            data.children.map((child : any) => [...parts, child].join("."))));
                })
                .catch((err) => console.error(err));
        });
    }

}

function TreeViewer ({ job } : { job : ApiJob | undefined }) {
    if (job === undefined) return <></>;

    return (
        <UncontrolledTreeEnvironment dataProvider={new JobTreeProvider(job)}
                                     getItemTitle={item => item.data.id}
                                     viewState={{}}>
            <Tree treeId="jobtree" rootItem="root" treeLabel={job.id} />
        </UncontrolledTreeEnvironment>
    );
}

function JobViewer ({ job } : { job : ApiJob | undefined }) {
    return (
        <>
            <nav className="job_hierarchy">
                <TreeViewer job={job} />
            </nav>
            <div className="log">
                <MessageViewer job={job} />
            </div>
        </>
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
            <header className="navbar navbar-dark bg-dark shadow">
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
            <main>
                <nav className="job_tops">
                    <table className="table table-sm">
                        <tbody>{job_elems}</tbody>
                    </table>
                </nav>
                <JobViewer job={job_focus} />
            </main>
        </>
    );
}
