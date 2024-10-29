
import Dashboard from "@/features/JobDashboard/components/Dashboard";
import { ReactNode, useEffect, useMemo, useState } from "react";
import JobTree from "@/features/JobDashboard/lib/jobtree";
import { EventDataNode } from "antd/lib/tree";
import Tree, { TreeKey, TreeNode } from "@/features/JobDashboard/components/Dashboard/lib/tree";
import { TableOutlined } from "@ant-design/icons";
import MessageTable from "@/features/JobDashboard/components/MessageTable";
import RegistrationTable from "@/features/JobDashboard/components/RegistrationTable";
import { ApiLayerResponse, Job, JobResult, JobState } from "@/types/job";
import { HubReader, Reader } from "./lib/readers";
import { view } from "./components/Dashboard/theme";
import { Progress } from "antd";
import { l } from "node_modules/vite/dist/node/types.d-aGj9QkWt";

/**
 * Splits strings into alpha and numeric portions before comparison
 * and tries to treat the numeric portions as numbers.
 */
function naturalCompare(a: String | Number, b: String | Number) {
    const num_regex = /(\d+\.?\d*)/g
    const aParts = a.toString().split(num_regex);
    const bParts = b.toString().split(num_regex);
    while (true) {
        const aPart = aParts.shift();
        const bPart = bParts.shift();

        if (aPart === undefined || bPart === undefined) {
            if (aPart !== undefined) {
                return 1;
            }
            if (bPart !== undefined) {
                return -1;
            }
            return NaN;
        }

        const numCompare = Number.parseInt(aPart) - Number.parseInt(bPart);
        if (!Number.isNaN(numCompare) && numCompare != 0) {
            return numCompare;
        }
        const strCompare = aPart.localeCompare(bPart);
        if (strCompare != 0) {
            return strCompare;
        }
    }
}

type SearchedTextProps = {
    text: string;
    searchValue: string;
}

function SearchedText({ text, searchValue }: SearchedTextProps): ReactNode {
    const index = text.indexOf(searchValue);
    const beforeStr = text.substring(0, index);
    const afterStr = text.slice(index + searchValue.length);
    const title =
        index > -1 ? (
            <span>
                {beforeStr}
                <span {...view.sider.tree.searchlight.props}>
                    {searchValue}
                </span>
                {afterStr}
            </span>
        ) : (
            <span>{text}</span>
        );
    return title;
}

type liveFetchProps = {
    interval: number;
    reader: Reader;
    tree: JobTree;
    setTree: (newTree: JobTree) => void;
    liveTreeKeys: TreeKey[]
    setLiveTreeKeys: (newLiveTreeKeys: TreeKey[]) => void;
    setLoadedTreeKeys: React.Dispatch<React.SetStateAction<TreeKey[]>>
}

function liveFetchEffect({ interval, reader, tree, setTree, liveTreeKeys, setLiveTreeKeys, setLoadedTreeKeys }: liveFetchProps) {
    const task = async () => {
        const responses = await Promise.all(liveTreeKeys.map((k) => tree.getNodeByKey(k))
            .filter(node => node !== undefined)
            .map(node => {
                return new Promise<{ key: TreeKey, response: ApiLayerResponse }>(async (resolve) => {
                    resolve({ key: node.key, response: await reader.readLayer(node.data) } as const)
                })
            }));
        const newLiveTreeKeys: TreeKey[] = [];
        for (const { key, response } of responses) {
            if (response.status !== JobState.COMPLETE) newLiveTreeKeys.push(key);
        }
        const newTree = tree.updatedFromLayers(responses);
        setLiveTreeKeys(newLiveTreeKeys);
        setTree(newTree);
        updateLoadedTreeKeys(newTree, setLoadedTreeKeys);
    }
    const timeout = setInterval(task, interval);
    return () => clearInterval(timeout);
}

const updateLoadedTreeKeys = (tree: JobTree, setLoadedTreeKeys: (keys: TreeKey[]) => void) => {
    const newLoadedTreeKeys = [];
    for (const [{ key, data, children }, _parent] of tree.walk()) {
        if (children?.length === data.expected_children) {
            newLoadedTreeKeys.push(key);
        }
    }
    setLoadedTreeKeys(newLoadedTreeKeys);
}


export default function JobDashboard() {
    const [reader, _setReader] = useState<Reader>(new HubReader())

    const [tree, setTree] = useState<JobTree>(JobTree.fromJobs([]));

    const [selectedTreeKeys, setWrappedSelectedTreeKeys] = useState<TreeKey[]>([]);

    const [loadedTreeKeys, setLoadedTreeKeys] = useState<TreeKey[]>([]);

    const [liveTreeKeys, setLiveTreeKeys] = useState<TreeKey[]>([]);

    const setSelectedTreeKeys = (newSelectedKeys: TreeKey[]) => {
        setWrappedSelectedTreeKeys(newSelectedKeys);

        // Take the most recent 5 non-complete keys
        const newLiveTreeKeys = newSelectedKeys.filter(k => tree.getNodeByKey(k)?.data.status !== JobState.COMPLETE)
        setLiveTreeKeys(current => [
            ...newLiveTreeKeys,
            ...current.filter(el => !newLiveTreeKeys.includes(el))
        ].slice(0, 5))
    }

    async function onLoadData(eventNode: EventDataNode<TreeNode<Job>>) {
        const job = eventNode.data;
        const node = tree.getNodeByKey(eventNode.key);
        if (node === undefined) return;
        const response = await reader.readLayer({ root: job.root, path: job.path }).catch(_e => {
            return null;
        });

        // TODO display errors to user
        setLoadedTreeKeys(current => [...current, node.key]);
        if (!response) return;
        const newTree = tree.updatedFromLayers([{ key: node.key, response }]);
        updateLoadedTreeKeys(newTree, setLoadedTreeKeys);
        setTree(newTree);
        return;
    }

    function setSelectedRows(rows: Job[]) {
        const newTree = JobTree.fromJobs(rows);
        for (const root of tree.getRoots()) {
            const node = newTree.getNodeByKey(root.key);
            if (node !== undefined) {
                node.children = root.children
            }
        }
        setTree(new JobTree(newTree.getRoots()));
    }

    const selectedRowKeys = tree.getRoots().map(root => root.key)

    const getViewsByKey = useMemo(() => (key: TreeKey) => {
        const node = tree.getNodeByKey(key);
        if (key == Tree.ROOT || node === undefined) {
            return [
                {
                    value: "registration_table",
                    icon: <TableOutlined />,
                    factory: () => <RegistrationTable key={key} selectedRowKeys={selectedRowKeys} setSelectedRows={setSelectedRows} reader={reader} />
                }
            ]
        } else {
            const job = node.data;
            const path = job.path ?? [];
            const tableKey = [job.uidx, ...path].join('-');
            return [
                {
                    value: "message_table",
                    icon: <TableOutlined />,
                    factory: () => <MessageTable job={job} key={tableKey} reader={reader} />
                },
            ];
        }
    }, [selectedRowKeys, reader]);

    function treeNodeFormatter(treeNode: TreeNode<Job>, searchValue: string) {
        const { status, result, metrics } = treeNode.data;
        let successRatio: number;
        let progressRatio: number;
        switch (status) {
            case JobState.PENDING:
                successRatio = 0;
                progressRatio = 0.1;
                break;
            case JobState.LAUNCHED:
                successRatio = 0.1;
                progressRatio = 0.2;
                break;
            default:
                const total = metrics.sub_total ?? 1;
                const passed = metrics.sub_passed ?? (result === JobResult.SUCCESS ? 1 : 0);
                const active = metrics.sub_active ?? (result === JobResult.UNKNOWN ? 1 : 0);
                const failed = metrics.sub_failed ?? (result === JobResult.FAILURE ? 1 : 0);
                const subProgressRatio = (passed + failed + active) / total;
                const subSuccessRatio = passed / total;

                if (status === JobState.STARTED) {
                    progressRatio = 0.2 + (0.7 * subProgressRatio);
                    successRatio = 0.2 + (0.7 * subSuccessRatio);
                } else {
                    progressRatio = 1;
                    successRatio = (result === JobResult.SUCCESS ? 0.3 : 0.2) + (0.7 * subSuccessRatio);
                }
        }

        let progressStatus;
        switch (result) {
            case JobResult.UNKNOWN:
                progressStatus = (
                    metrics.sub_failed
                        ? "exception" as const
                        : liveTreeKeys.includes(treeNode.key)
                            ? "active" as const
                            : "normal" as const
                );
                break;
            case JobResult.SUCCESS:
                progressStatus = "success" as const;
                break;
            case JobResult.FAILURE:
                progressStatus = "exception" as const;
                break;
            default:
                throw new Error("Invalid Result")
        }

        return <span>
            <div><SearchedText text={(treeNode.title as string)} searchValue={searchValue} /></div>

            <div style={{ width: 100 }}>
                <Progress type="line"
                    percent={
                        Math.round(progressRatio * 100)
                    }
                    success={{
                        percent: Math.round(successRatio * 100)
                    }}
                    status={progressStatus}
                />
            </div>
        </span>
    }

    useEffect(() => liveFetchEffect({ interval: 3000, reader, tree, setTree, liveTreeKeys, setLiveTreeKeys, setLoadedTreeKeys }), [reader, tree, liveTreeKeys])

    return <Dashboard tree={tree} onLoadData={onLoadData} loadedTreeKeys={loadedTreeKeys} selectedTreeKeys={selectedTreeKeys} setSelectedTreeKeys={setSelectedTreeKeys} getViewsByKey={getViewsByKey} treeNodeFormatter={treeNodeFormatter} />
}
