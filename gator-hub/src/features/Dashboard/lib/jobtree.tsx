/*
 * SPDX-License-Identifier: MIT
 * Copyright (c) 2023-2024 Vypercore. All Rights Reserved
 */

import { TableOutlined } from "@ant-design/icons";
import Tree, { TreeKey, TreeNode, View } from "./tree";
import moment from "moment";

export type JobNode = TreeNode<ApiJob>;


export default class JobTree extends Tree<ApiJob> {
    static fromJobs(jobs: ApiJob[]): JobTree {
        // Record the tree and stack of current ancestors
        const tree: JobNode[] = [];

        for (const job of jobs) {
            let date = moment(job.timestamp * 1000);
            let mtc_wrn = 0;
            let mtc_err = 0;
            let mtc_crt = 0;
            job.metrics.forEach((metric) => {
                if (metric.name == "msg_warning") mtc_wrn = metric.value;
                else if (metric.name == "msg_error") mtc_err = metric.value;
                else if (metric.name == "msg_critical") mtc_crt = metric.value;
            })
            const dataNode: JobNode = {
                title: `${job.uid}: ${job.ident} ${job.completion.uid ? 'X' : 'O'}
                        ${job.owner} - ${date.format("DD/MM/YY @ HH:mm")} - ${mtc_wrn} | ${mtc_err} | ${mtc_crt}`,
                key: job.uid,
                children: [],
                data: job
            }
            tree.push(dataNode)
        }
        return new JobTree(tree);
    }

    // onLoadData(treeNode: EventDataNode<TreeNode<ApiJob>>) {
    //     console.log(treeNode)

    //     return new Promise<void>(async (resolve, reject) => {
    //         if (treeNode.data.completion.uid) {
    //             resolve()
    //         } else {
    //             const stream = (await fetch(`/api/job/${treeNode.data.uid}/layer`))
    //             const data: { children: string[] } = await stream.json()

    //             treeNode.children = data.children.map(child => ({
    //                 title: child,
    //                 key: `${treeNode.data.uid}-${child}`,
    //                 children: [],
    //                 data: {}
    //             }))

    //             treeNode.title = 'VASDA'

    //             console.log(treeNode)
    //             resolve()
    //         }
    //     })
    // }

    // getViewsByKey(key: TreeKey): View[] {
    //     const _node = this.getNodeByKey(key);
    //     return [
    //         {
    //             value: "None",
    //             icon: <TableOutlined />,
    //         },
    //     ];
    // }
}
