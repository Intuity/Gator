
import Dashboard from "@/features/JobDashboard/components/Dashboard";
import { useMemo, useState } from "react";
import JobTree from "@/features/JobDashboard/lib/jobtree";
import { EventDataNode } from "antd/lib/tree";
import Tree, { TreeKey, TreeNode } from "@/features/JobDashboard/components/Dashboard/lib/tree";
import { TableOutlined } from "@ant-design/icons";
import MessageTable from "@/features/JobDashboard/components/MessageTable";
import RegistrationTable from "@/features/JobDashboard/components/RegistrationTable";
import { Job } from "@/types/job";
import { HubReader, Reader } from "./lib/readers";

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

export default function JobDashboard() {
    const [reader, _setReader] = useState<Reader>(new HubReader())

    const [tree, setTree] = useState<JobTree>(JobTree.fromJobs([]));

    const [selectedTreeKeys, setSelectedTreeKeys] = useState<TreeKey[]>([]);

    const [loadedTreeKeys, setLoadedTreeKeys] = useState<TreeKey[]>([]);

    async function onLoadData(eventNode: EventDataNode<TreeNode<Job>>) {
        const job = eventNode.data;
        const node = tree.getNodeByKey(eventNode.key);
        if (node === undefined) return;
        const response = await reader.readLayer({ root: job.root, path: job.path }).catch(_e => {
            return null;
        });
        // TODO display errors to user
        setLoadedTreeKeys(loadedTreeKeys.concat([node.key]));
        if (!response) return;
        node.children = response.jobs.sort((a, b) => naturalCompare(a.ident, b.ident)).map(child => {
            const path = [...job.path, child.ident];
            const key = [job.root, ...path].join('-');
            return {
                key,
                title: child.ident,
                data: {
                    root: job.root,
                    path,
                    ...child,
                }
            }
        })
        setTree(new JobTree(tree.getRoots()));
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
    }, [selectedRowKeys, setSelectedRows, reader]);

    return <Dashboard tree={tree} onLoadData={onLoadData} loadedTreeKeys={loadedTreeKeys} selectedTreeKeys={selectedTreeKeys} setSelectedTreeKeys={setSelectedTreeKeys} getViewsByKey={getViewsByKey} />
}
