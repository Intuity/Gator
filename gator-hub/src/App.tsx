import { ReactElement, useEffect, useState, useRef } from 'react'
import moment from 'moment'

import 'datatables.net-bs5/css/dataTables.bootstrap5.css'
import DataTable from 'datatables.net-bs5'
import 'datatables.net-scroller-bs5'

import 'react-complex-tree/lib/style-modern.css'
import {
    UncontrolledTreeEnvironment,
    Tree,
    TreeDataProvider,
    TreeItemIndex,
    TreeItem,
    InteractionMode
} from 'react-complex-tree'

import mascot from "./assets/mascot_white.svg?url"

interface ApiCompletion {
    uid?: number,
    db_file?: string,
    timestamp?: number
}

interface ApiMetric {
    name: string,
    value: number
}

interface ApiJob {
    uid: number,
    ident: string,
    server_url: string,
    owner: string,
    timestamp: number,
    completion: ApiCompletion,
    metrics: ApiMetric[]
}

interface Dimensions {
    height: number,
    width: number
};

const Severity: { [key: number]: string } = {
    10: "DEBUG",
    20: "INFO",
    30: "WARNING",
    40: "ERROR",
    50: "CRITICAL"
};

const Intervals: { [key: string]: number } = {
    REFRESH_JOBS: 5000,
    REFRESH_TREE: 5000,
    REFRESH_LOG: 2000,
    DT_FETCH_DELAY: 100
};

function Breadcrumb({ }) {
    return (
        <nav aria-label="breadcrumb">
            <ol className="breadcrumb">
                <li className="breadcrumb-item"><a href="#">Home</a></li>
                <li className="breadcrumb-item active" aria-current="page">Library</li>
            </ol>
        </nav>
    );
}

function Job({ job, focus, setJobFocus }: { job: ApiJob, focus: ApiJob | undefined, setJobFocus: (focus: ApiJob) => void }) {
    let date = moment(job.timestamp * 1000);
    let mtc_wrn = 0;
    let mtc_err = 0;
    let mtc_crt = 0;
    job.metrics.forEach((metric) => {
        if (metric.name == "msg_warning") mtc_wrn = metric.value;
        else if (metric.name == "msg_error") mtc_err = metric.value;
        else if (metric.name == "msg_critical") mtc_crt = metric.value;
    })
    return (
        <tr onClick={() => { setJobFocus(job); }} className={(focus && focus.uid == job.uid) ? "active" : ""}>
            <td>
                <strong>{job.uid}: {job.ident}</strong>{job.completion.uid ? 'X' : 'O'}<br />
                <small>{job.owner} - {date.format("DD/MM/YY @ HH:mm")} - {mtc_wrn} | {mtc_err} | {mtc_crt}</small>
            </td>
        </tr>
    );
}

function fetchJobs(setJobs: CallableFunction) {
    let inner = () => {
        let all_jobs: ApiJob[] = [];
        fetch("/api/jobs")
            .then((response) => response.json())
            .then((data) => {
                all_jobs = [...all_jobs, ...data];
                all_jobs.sort((a, b) => (b.uid - a.uid));
                setJobs(all_jobs)
            })
            .catch((err) => console.error(err.message))
            .finally(() => setTimeout(inner, Intervals.REFRESH_JOBS));
    };
    inner();
}

function MessageViewer(
    { job, path, dimensions }:
        { job: ApiJob | undefined, path: string[], dimensions: Dimensions }
) {
    // If no job provided, return an empty pane
    if (job === undefined) return <div className="log"></div>;

    const ref = useRef<HTMLDivElement>(null);

    useEffect(() => {
        const dt = new (DataTable as any)(ref.current!.children[0], {
            columns: [{ data: "timestamp" },
            { data: "severity" },
            { data: "message" }],
            searching: false,
            ordering: false,
            deferRender: true,
            scrollY: ref.current!.offsetHeight - 39,
            scrollCollapse: true,
            info: false,
            scroller: { serverWait: Intervals.DT_FETCH_DELAY },
            serverSide: true,
            ajax: (request: any, callback: any) => {
                let start = request.start;
                let limit = request.length;
                if (limit < 0) limit = 100;
                fetch(`/api/job/${job.uid}/messages/${path.join('/')}?after=${start}&limit=${limit}`)
                    .then((response) => response.json())
                    .then((data) => {
                        callback({
                            draw: request.draw,
                            data: data.messages.map((msg: any) => {
                                msg.timestamp = moment(msg.timestamp * 1000).format("HH:mm:ss");
                                msg.severity = Severity[msg.severity];
                                return msg;
                            }),
                            recordsTotal: data.total,
                            recordsFiltered: data.total
                        });
                    })
                    .catch((err) => console.error(err.message));
            }
        });
        let reload = setInterval(
            () => {
                dt.ajax.reload((data: any) => {
                    dt.scroller.toPosition(data.recordsTotal + 200);
                }, false);
            },
            Intervals.REFRESH_LOG
        );
        return () => {
            clearInterval(reload);
            dt.destroy();
        };
    }, [job, path, dimensions]);

    return (
        <div className="log">
            <div className="log_inner" ref={ref}>
                <table className="table table-striped table-sm">
                    <thead>
                        <tr>
                            <th>Time</th>
                            <th>Severity</th>
                            <th>Message</th>
                        </tr>
                    </thead>
                </table>
            </div>
        </div>
    );
}

class JobTreeItem implements TreeItem {

    public isFolder?: boolean | undefined

    public constructor(public index: TreeItemIndex,
        public data: ApiJob | undefined,
        public children: TreeItemIndex[],
        public data_url: string | undefined) {
        this.isFolder = children.length > 0;
    }

    public refresh() {
        if (this.data_url === undefined) return Promise.resolve(this);
        let job = this;
        return new Promise<JobTreeItem>((resolve) => {
            fetch(job.data_url!)
                .then((response) => response.json())
                .then((data) => {
                    job.data = data;
                    if (data.children) {
                        job.isFolder = true;
                        job.children = data.children.map((child: any) => [job.index, child].join("."));
                    }
                    resolve(job);
                });
        });
    }

}

class JobTreeProvider implements TreeDataProvider {

    public constructor(public job: ApiJob,
        public addTreeItems: CallableFunction) { }

    public getTreeItem(itemId: TreeItemIndex) {
        let tree = this;
        return new Promise<JobTreeItem>((resolve) => {
            tree.getTreeItems([itemId])
                .then((items) => resolve(items[0]));
        });
    }

    public getTreeItems(itemIds: TreeItemIndex[]) {
        let tree = this;
        return new Promise<JobTreeItem[]>((resolve) => {
            let items = itemIds.map((itemId) => {
                if (itemId == "root") {
                    return new JobTreeItem(itemId, this.job, [this.job.uid.toString()], undefined);
                } else {
                    let parts = (itemId as string).split(".");
                    return new JobTreeItem(
                        itemId,
                        undefined,
                        [],
                        `/api/job/${this.job.uid}/layer/${parts.slice(1).join('/')}`
                    );
                }
            });
            // Perform initial refresh, then register all tree items
            Promise.all(items.map((item) => item.refresh()))
                .then((items) => {
                    tree.addTreeItems(items);
                    resolve(items);
                });
        });
    }

}

function TreeViewer({ job, setJobPath }: { job: ApiJob | undefined, setJobPath: CallableFunction }) {
    if (job === undefined) return <></>;

    const [tree_items, setTreeItems] = useState<JobTreeItem[]>([]);

    let addTreeItems = (items: JobTreeItem[]) => setTreeItems([...tree_items, ...items]);

    useEffect(() => {
        let interval = setInterval(() => {
            tree_items.forEach((job) => job.refresh());
        }, Intervals.REFRESH_TREE);

        return () => {
            clearInterval(interval);
        };
    }, [job, tree_items]);

    return (
        <UncontrolledTreeEnvironment dataProvider={new JobTreeProvider(job, addTreeItems)}
            getItemTitle={item => {
                if (item.data !== undefined) {
                    let mtc: any = item.data.metrics;
                    if (mtc !== undefined) {
                        let ident = item.data.ident;
                        let warn = mtc.msg_warning;
                        let err = mtc.msg_error;
                        let crit = mtc.msg_critical;
                        return `${ident} - ${warn} | ${err} | ${crit}`;
                    } else if (item.data.ident !== undefined) {
                        return `${item.data.ident} - ⏳`;
                    } else {
                        return "PENDING";
                    }
                } else {
                    return "LOADING";
                }
            }}
            viewState={{}}
            defaultInteractionMode={InteractionMode.ClickArrowToExpand}
            onSelectItems={(items: TreeItemIndex[]) => {
                if (items.length == 0) return;
                setJobPath((items[0] as string).split(".").slice(1));
            }}>
            <Tree treeId="jobtree" rootItem="root" treeLabel={job.ident} />
        </UncontrolledTreeEnvironment>
    );
}

function JobViewer(
    { job, dimensions }:
        { job: ApiJob | undefined, dimensions: Dimensions }
) {
    const [job_path, setJobPath] = useState<string[]>(
        (job !== undefined) ? [job!.uid.toString()] : []
    );
    return (
        <>
            <nav className="job_hierarchy">
                <TreeViewer job={job} setJobPath={setJobPath} />
            </nav>
            <MessageViewer job={job} path={job_path} dimensions={dimensions} />
        </>
    );
}

export default function App() {
    const [jobs, setJobs] = useState<ApiJob[]>([]);
    const [job_focus, setJobFocus] = useState<ApiJob | undefined>(undefined);
    const [dimensions, setDimensions] = useState({
        height: window.innerHeight,
        width: window.innerWidth
    });

    useEffect(() => fetchJobs(setJobs), []);
    useEffect(() => {
        window.addEventListener("resize", () => {
            setDimensions({
                height: window.innerHeight,
                width: window.innerWidth
            });
        });
    }, []);

    let job_elems: ReactElement[] = jobs.map((job) =>
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
                <JobViewer job={job_focus} dimensions={dimensions} />
            </main>
        </>
    );
}
