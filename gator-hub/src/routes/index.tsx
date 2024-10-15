/*
 * SPDX-License-Identifier: MIT
 * Copyright (c) 2023-2024 Vypercore. All Rights Reserved
 */

import { useRoutes } from "react-router-dom";
import Dashboard from "@/features/Dashboard";
import { useEffect, useState } from "react";
import JobTree from "@/features/Dashboard/lib/jobtree";
import { EventDataNode } from "antd/lib/tree";
import { TreeKey, TreeNode } from "@/features/Dashboard/lib/tree";
import { TableOutlined } from "@ant-design/icons";


const Intervals: { [key: string]: number } = {
    REFRESH_JOBS: 999999,
    REFRESH_TREE: 5000,
    REFRESH_LOG: 2000,
    DT_FETCH_DELAY: 100
};




function JobDashboard() {

    const [tree, setTree] = useState<JobTree>(JobTree.fromJobs([]))
    const [selectedTreeKeys, setSelectedTreeKeys] = useState<TreeKey[]>([]);

    function onLoadData(treeNode: EventDataNode<TreeNode<ApiJob>>) {
        console.log(treeNode)

        return new Promise<void>(async (resolve, reject) => {
            if (treeNode.data.completion.uid) {
                resolve()
            } else {
                const path = treeNode.data.path ?? []
                const stream = (await fetch(`/api/job/${treeNode.data.uid}/layer/${path.join('/')}`))
                const data: { children: string[] } = await stream.json()

                const node = tree.getNodeByKey(treeNode.key);

                node.children = data.children?.map(child => {
                    const child_path = [...path, child];
                    return {
                        title: child,
                        key: `${treeNode.data.uid}-${child_path.join('-')}`,
                        children: [],
                        data: {
                            uid: treeNode.data.uid,
                            ident: child,
                            path: child_path,
                            completion: { uid: null }
                        }
                    }
                }) ?? []

                resolve();
                setTree(new JobTree(tree.getRoots()));
            }
        })
    }

    function fetchJobs() {
        let inner = () => {
            let all_jobs: ApiJob[] = [];
            fetch("/api/jobs")
                .then((response) => response.json())
                .then((data) => {
                    all_jobs = [...all_jobs, ...data];
                    all_jobs.sort((a, b) => (b.uid - a.uid));
                    setTree(JobTree.fromJobs(all_jobs))
                })
                .catch((err) => console.error(err.message))
                .finally(() => setTimeout(inner, Intervals.REFRESH_JOBS));
        };
        inner();
    }

    useEffect(() => fetchJobs(), []);

    function getViewsByKey(key: TreeKey) {
        return [
            {
                value: "None",
                icon: <TableOutlined />,
                factory: () => <TableOutlined />
            },
        ];
    }


    return <Dashboard tree={tree} onLoadData={onLoadData} selectedTreeKeys={selectedTreeKeys} setSelectedTreeKeys={setSelectedTreeKeys} getViewsByKey={getViewsByKey} />
}


export const AppRoutes = () => {
    const element = useRoutes([{ path: "*", element: <JobDashboard /> }]);
    return <>{element}</>;
};
