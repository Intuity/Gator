/*
 * SPDX-License-Identifier: MIT
 * Copyright (c) 2023-2024 Vypercore. All Rights Reserved
 */

import Tree, { TreeNode } from "../components/Dashboard/lib/tree";
import moment from "moment";

export type JobNode = TreeNode<ApiJob>;


export default class JobTree extends Tree<ApiJob> {
    static fromJobs(jobs: ApiJob[]): JobTree {
        // Record the tree and stack of current ancestors
        const tree: JobNode[] = [];

        for (const job of jobs) {
            let title = job.ident;
            if (job.details) {
                let date = moment(job.details.start * 1000);
                let mtc_wrn = 0;
                let mtc_err = 0;
                let mtc_crt = 0;
                job.details.metrics.forEach((metric) => {
                    if (metric.name == "msg_warning") mtc_wrn = metric.value;
                    else if (metric.name == "msg_error") mtc_err = metric.value;
                    else if (metric.name == "msg_critical") mtc_crt = metric.value;
                })
                title = `${job.uid}: ${job.ident} ${job.details.stop ? 'X' : 'O'}
                         ${job.owner} - ${date.format("DD/MM/YY @ HH:mm")} - ${mtc_wrn} | ${mtc_err} | ${mtc_crt}`;
            }

            const dataNode: JobNode = {
                title: title,
                key: job.uid,
                children: [],
                data: job
            }
            tree.push(dataNode)
        }
        return new JobTree(tree);
    }
}
