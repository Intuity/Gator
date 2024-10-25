/*
 * SPDX-License-Identifier: MIT
 * Copyright (c) 2023-2024 Vypercore. All Rights Reserved
 */

import { Job, JobState } from "@/types/job";
import Tree, { TreeNode } from "../components/Dashboard/lib/tree";
import moment from "moment";


export type JobNode = TreeNode<Job>;



export default class JobTree extends Tree<Job> {
    static fromJobs(jobs: Job[]): JobTree {
        // Record the tree and stack of current ancestors
        const tree: JobNode[] = [];

        for (const job of jobs) {
            if (job.status === JobState.LAUNCHED || job.status === JobState.PENDING) {
                throw new Error("Unexpected job state")
            }

            let title = job.ident;
            let date = moment(job.started * 1000);
            let mtc_wrn = 0;
            let mtc_err = 0;
            let mtc_crt = 0;
            for (const [name, value] of Object.entries(job.metrics)) {
                if (name == "msg_warning") mtc_wrn = value;
                else if (name == "msg_error") mtc_err = value;
                else if (name == "msg_critical") mtc_crt = value;
            }
            title = `${job.uidx}: ${job.ident} ${job.status === JobState.COMPLETE ? 'X' : 'O'}
                     ${job.owner} - ${date.format("DD/MM/YY @ HH:mm")} - ${mtc_wrn} | ${mtc_err} | ${mtc_crt}`;

            const dataNode: JobNode = {
                title,
                key: job.uidx,
                children: [],
                data: job
            }
            tree.push(dataNode)
        }
        return new JobTree(tree);
    }
}
