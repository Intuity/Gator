
import { ApiMessage, ApiJob, JobState, Job } from "@/types/job";
import { Alert, Spin, Table, TableProps } from "antd";
import moment from "moment";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { Reader } from "../lib/readers";
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
    LIVE,
    NONE
}

type TableStatus = {
    status: Status;
    detail: string;
}

const columns: TableProps['columns'] = [
    {
        title: "Uid",
        dataIndex: "uid",
        width: 100
    },
    {
        title: "Timestamp",
        dataIndex: "timestamp",
        render: text => moment(text * 1000).format("HH:mm:ss"),
        width: 100
    },
    {
        title: "Severity",
        dataIndex: "severity",
        render: text => Severity[text],
        width: 80
    },
    {
        title: "Message",
        dataIndex: "message"
    },
]

type messageFetchEffectProps = {
    interval: number;
    reader: Reader;
    job: Job;
    messages: ApiMessage[]
    setMessages: (messages: ApiMessage[]) => void;
    status: TableStatus;
    setStatus: (status: TableStatus) => void;
}

function messageFetchEffect({ interval, reader, job, messages, setMessages, status, setStatus }: messageFetchEffectProps) {
    const task = async () => {
        const { root, path, ident } = job;
        const after = messages[messages.length - 1]?.uid ?? 0;
        const limit = 1000;
        const response = await reader.readMessages({ root, path, ident, after, limit }).catch(e => {
            setStatus({
                status: Status.ERROR,
                detail: String(e)
            });
            return null;
        });
        if (!response) return;
        if (response.messages.length) {
            setMessages(messages.concat(response.messages));
        }
        const loadedCount = messages.length + response.messages.length;
        const availableCount = response.total;
        let newStatus: Status;
        if (response.status === JobState.COMPLETE && loadedCount === availableCount) {
            newStatus = Status.NONE
        } else if (response.status === JobState.STARTED) {
            newStatus = Status.LIVE;
        } else {
            newStatus = Status.ERROR;
        }
        setStatus({
            status: newStatus, detail: `Loaded: ${loadedCount} / ${availableCount}${newStatus === Status.LIVE ? ' (live)' : ''}`
        })
    }
    if (status.status == Status.LOADING) {
        task();
    }
    let timeout = undefined;
    if (status.status !== Status.NONE) {
        timeout = setInterval(task, interval);
    }
    return () => clearInterval(timeout);
}

export type MessageTableProps = {
    job: Job,
    key: TreeKey,
    reader: Reader
};

export default function MessageTable({ job, reader }: MessageTableProps) {

    const [status, setStatus] = useState<TableStatus>({ status: Status.LOADING, detail: "" });
    const [messages, setMessages] = useState<ApiMessage[]>([]);
    const [tableHeight, setTableHeight] = useState(600);

    useEffect(() => messageFetchEffect({ interval: 3000, reader, job, messages, setMessages, status, setStatus }), [reader, job, messages, status]);

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
        <Table
            virtual
            columns={columns}
            dataSource={messages}
            pagination={false}
            size={"small"}
            rowKey="uid"
            scroll={{ y: tableHeight }}
            footer={getFooter(status)}
        />
    </div>
}
