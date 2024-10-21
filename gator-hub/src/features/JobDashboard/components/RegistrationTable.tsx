
import { Alert, Spin, Table, TableProps } from "antd";
import moment from "moment";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { TreeKey } from "./Dashboard/lib/tree";

enum Severity {
    CRITICAL = 50,
    FATAL = CRITICAL,
    ERROR = 40,
    WARNING = 30,
    WARN = WARNING,
    INFO = 20,
    DEBUG = 10,
    NOTSET = 0
}

enum Status {
    ERROR,
    LOADING,
    NONE
}

type TableStatus = {
    status: Status;
    detail: string;
}

export type JobNode = {
    data: ApiJob;
}

const columns: TableProps<JobNode>['columns'] = [
    {
        title: "Uid",
        dataIndex: ["data", "uid"],
        width: 100
    },
    {
        title: "Timestamp",
        dataIndex: ["data", "details", "start"],
        render: text => { console.log(text); return moment(text * 1000).format("HH:mm:ss") },
        width: 100
    },
    {
        title: "Owner",
        dataIndex: ["data", "owner"],
        width: 150
    },
    {
        title: "Ident",
        dataIndex: ["data", "ident"],
    },
]


class ResponseError extends Error { };
class ProcessingError extends Error { };

export type RegistrationTableProps = {
    key: TreeKey;
    selectedRowKeys: TreeKey[];
    setSelectedRows: (rows: ApiJob[]) => void
};

export default function RegistrationTable({ selectedRowKeys, setSelectedRows }: RegistrationTableProps) {

    const [status, setStatus] = useState<TableStatus>({ status: Status.LOADING, detail: "" });
    const [rows, setRows] = useState<JobNode[]>([]);
    const [tableHeight, setTableHeight] = useState(600);

    const getData = async () => {
        try {
            const response = await fetch(`/api/jobs`);
            if (response.ok) {
                try {
                    const registrations: ApiRegistration[] = await response.json();
                    if (registrations.length) {
                        setRows(registrations.map(reg => ({
                            key: String(reg.uid),
                            data: {
                                root: reg.uid,
                                uid: String(reg.uid),
                                ident: reg.ident,
                                path: [],
                                owner: reg.owner,
                                details: {
                                    server_url: reg.server_url,
                                    db_file: reg.completion?.db_file,
                                    start: reg.timestamp,
                                    stop: reg.completion?.timestamp,
                                    metrics: reg.metrics,
                                    live: reg.completion !== undefined,
                                }
                            }
                        })));
                    }
                    setStatus({
                        status: Status.NONE, detail: `Loaded: "Some Registrations"`
                    })
                } catch (e) {
                    throw new ProcessingError();
                }
            } else {
                throw new ResponseError();
            }
        } catch (e) {
            let detail = "Unknown Error";
            if (e instanceof ResponseError) {
                // Could connect to server, but didn't get a good response
                detail = "Server response error";
            } else if (e instanceof ProcessingError) {
                // Got a "good" response, but couldn't process it
                detail = "Response processing error";
            }
            setStatus({
                status: Status.ERROR,
                detail
            });
        }

    }

    useEffect(() => { getData() }, []);

    function getFooter(status: TableStatus) {
        return () => {
            if (status.status == Status.ERROR) {
                return <Alert type="error" message={status.detail} showIcon />
            }
            return <Spin spinning={status.status == Status.LOADING}>
                <Alert type="info" message={status.detail} />
            </Spin>
        }
    }

    const wrapperRef = useRef<HTMLDivElement>(null);
    useLayoutEffect(() => {
        const node = wrapperRef.current;
        if (node) {
            const { top } = node.getBoundingClientRect();
            // Estimate of the combined height of header and footer
            const headerFooterHeight = 104;
            setTableHeight(window.innerHeight - top - headerFooterHeight);
        }
    }, [wrapperRef]);

    return <div ref={wrapperRef}>
        <Table<JobNode>
            virtual
            columns={columns}
            dataSource={rows}
            pagination={false}
            size={"small"}
            scroll={{ y: tableHeight }}
            footer={getFooter(status)}
            rowSelection={{
                type: "checkbox",
                hideSelectAll: true,
                selectedRowKeys,
                columnWidth: 40,
                onSelect: (_record, _selected, selectedRows, _e) => {
                    setSelectedRows(selectedRows.map(row => row.data))
                }
            }}
        />
    </div>
}
