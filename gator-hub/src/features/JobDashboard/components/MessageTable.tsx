
import { Alert, Spin, Table, TableProps } from "antd";
import moment from "moment";
import { useEffect, useLayoutEffect, useRef, useState } from "react";

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

class ResponseError extends Error { };
class ProcessingError extends Error { };

export type MessageTableProps = {
    job: ApiJob
    key: string
};

export default function MessageTable({ job }: MessageTableProps) {

    const [status, setStatus] = useState<TableStatus>({ status: Status.LOADING, detail: "" });
    const [after, setAfter] = useState<number>(0);
    const [messages, setMessages] = useState<ApiMessage[]>([]);
    const [tableHeight, setTableHeight] = useState(600);

    const getData = async () => {
        const params = new URLSearchParams({ after: String(after), limit: "1000" }).toString();
        const path = job.path ?? []

        try {
            const response = await fetch(`/api/job/${job.root}/messages/${path.join('/')}?${params}`);
            if (response.ok) {
                try {
                    const data: ApiMessages = await response.json();
                    const loadedCount = data.messages.length;
                    const totalMessagesLoaded = after + loadedCount;
                    if (loadedCount) {
                        setMessages(messages.concat(data.messages));
                        setAfter(totalMessagesLoaded);
                    }
                    const newStatus = ((totalMessagesLoaded < data.total)
                        ? Status.LOADING
                        : (data.live
                            ? Status.LIVE
                            : Status.NONE
                        )
                    );
                    setStatus({
                        status: newStatus, detail: `Loaded: ${totalMessagesLoaded} / ${data.total}${data.live ? ' (live)' : ''}`
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
    useEffect(() => {
        let timeout: NodeJS.Timeout;
        if (status.status != Status.NONE) {
            const timeoutMs = {
                [Status.LIVE]: 3000,
                [Status.ERROR]: 10000,
                [Status.LOADING]: 0,
            }[status.status]
            timeout = setTimeout(getData, timeoutMs)
        }
        return () => {
            clearTimeout(timeout);
        }
    }, [after]);

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
