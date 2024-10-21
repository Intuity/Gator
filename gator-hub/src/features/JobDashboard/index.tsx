
import Dashboard from "@/features/JobDashboard/components/Dashboard";
import { useMemo, useState } from "react";
import JobTree from "@/features/JobDashboard/lib/jobtree";
import { EventDataNode } from "antd/lib/tree";
import Tree, { TreeKey, TreeNode } from "@/features/JobDashboard/components/Dashboard/lib/tree";
import { TableOutlined } from "@ant-design/icons";
import MessageTable from "@/features/JobDashboard/components/MessageTable";
import RegistrationTable from "@/features/JobDashboard/components/RegistrationTable";


export default function JobDashboard() {

    const [tree, setTree] = useState<JobTree>(JobTree.fromJobs([]));

    const [selectedTreeKeys, setSelectedTreeKeys] = useState<TreeKey[]>([]);

    function onLoadData(eventNode: EventDataNode<TreeNode<ApiJob>>) {
        console.log(eventNode)

        return new Promise<void>(async (resolve, reject) => {
            const job = eventNode.data;
            const stream = (await fetch(`/api/job/${job.root}/layer/${job.path.join('/')}`))
            const data: {
                children: {
                    [key: string]: { db_file?: string, server_url?: string }
                }
            } = await stream.json()

            const node = tree.getNodeByKey(eventNode.key);
            if (node) {
                node.children = Object.keys(data.children).map(child => {
                    const child_path = [...job.path, child];
                    const child_uid = [job.root, ...child_path].join('-');
                    return {
                        key: child_uid,
                        title: child,
                        data: {
                            root: job.root,
                            uid: child_uid,
                            ident: child,
                            path: child_path,
                            owner: job.owner
                        }
                    }
                })
            }
            node.loaded = true;

            resolve();
            setTree(new JobTree(tree.getRoots()));
        })
    }

    function setSelectedRows(rows: ApiJob[]) {
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
    let loadedTreeKeys = []
    for (const [node, _parent] of tree.walk()) {
        if (node.loaded) {
            loadedTreeKeys.push(node.key);
        }
    }

    const getViewsByKey = useMemo(() => (key: TreeKey) => {
        if (key == Tree.ROOT) {
            return [
                {
                    value: "registration_table",
                    icon: <TableOutlined />,
                    factory: () => <RegistrationTable key={key} selectedRowKeys={selectedRowKeys} setSelectedRows={setSelectedRows} />
                }
            ]
        } else {
            const node = tree.getNodeByKey(key);
            const job = node.data;
            const path = job.path ?? [];
            const tableKey = [job.uid, ...path].join('-');
            return [
                {
                    value: "message_table",
                    icon: <TableOutlined />,
                    factory: () => <MessageTable job={job} key={tableKey} />
                },
            ];
        }
    }, [selectedRowKeys, setSelectedRows]);

    return <Dashboard tree={tree} onLoadData={onLoadData} loadedTreeKeys={loadedTreeKeys} selectedTreeKeys={selectedTreeKeys} setSelectedTreeKeys={setSelectedTreeKeys} getViewsByKey={getViewsByKey} />
}
