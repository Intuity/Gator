/*
 * SPDX-License-Identifier: MIT
 * Copyright (c) 2023-2024 Vypercore. All Rights Reserved
 */

import { Alert, Spin, Table, TableProps } from "antd";
import moment from "moment";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { TreeKey } from "./Dashboard/lib/tree";
import { ApiJob } from "@/types/job";
import { Reader } from "../lib/readers";

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
    LIVE,
    NONE
}

type TableStatus = {
    status: Status;
    detail: string;
}

export type JobNode = {
    key: TreeKey,
    data: ApiJob;
}

const columns: TableProps<JobNode>['columns'] = [
    {
        title: "Uid",
        dataIndex: ["data", "uidx"],
        width: 100
    },
    {
        title: "Timestamp",
        dataIndex: ["data", "started"],
        render: text => moment(text * 1000).format("HH:mm:ss"),
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

type JobFetchEffectProps = {
    interval: number;
    reader: Reader;
    jobs: JobNode[]
    setJobs: (newJobs: JobNode[]) => void;
    status: TableStatus;
    setStatus: (status: TableStatus) => void;
}

function jobFetchEffect({ interval, reader, jobs, setJobs, status, setStatus }: JobFetchEffectProps) {
    const task = async () => {
        const before = Number(jobs[jobs.length - 1]?.key) || 0;
        const after = Number(jobs[0]?.key) || 0;
        const limit = 1000;
        const response = await reader.readJobs({ before, after, limit }).catch(e => {
            setStatus({
                status: Status.ERROR,
                detail: String(e)
            });
            return null;
        });
        if (!response) return;
        if (response.children.length) {
            const responseJobs: JobNode[] = response.children.map(job => ({
                key: [job.root, ...job.path, job.ident].join('.'),
                data: {
                    ...job
                }
            }))
            const byKey = responseJobs.reduce((acc, job) => {
                acc[job.key] = job; return acc;
            }, {} as { [key: string]: JobNode })

            // Add new jobs, replacing any existing jobs with newer copies
            const newJobs = jobs.filter(j => !(j.key in byKey))
                .concat(responseJobs)
                .sort((a, b) => Number(b.key) - Number(a.key));
            setJobs(newJobs);
            setStatus({
                status: Status.LIVE, detail: `Loaded: ${newJobs.length} / ${newJobs[0].key}`
            })
        }
    }
    if (status.status == Status.LOADING) {
        task();
    }
    const timeout = setInterval(task, interval);
    return () => clearInterval(timeout);
}

export type RegistrationTableProps = {
    key: TreeKey;
    selectedRowKeys: TreeKey[];
    setSelectedRows: (rows: ApiJob[]) => void,
    reader: Reader
};

export default function RegistrationTable({ selectedRowKeys, setSelectedRows, reader }: RegistrationTableProps) {

    const [status, setStatus] = useState<TableStatus>({ status: Status.LOADING, detail: "" });
    const [jobs, setJobs] = useState<JobNode[]>([]);
    const [tableHeight, setTableHeight] = useState(600);

    useEffect(() => jobFetchEffect({ interval: 5000, reader, jobs, setJobs, status, setStatus }), [reader, jobs, status]);

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
            dataSource={jobs}
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
