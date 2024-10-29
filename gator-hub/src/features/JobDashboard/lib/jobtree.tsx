/*
 * SPDX-License-Identifier: MIT
 * Copyright (c) 2023-2024 Vypercore. All Rights Reserved
 */

import { ApiLayerResponse, Job, JobState } from "@/types/job";
import Tree, { TreeKey, TreeNode } from "../components/Dashboard/lib/tree";
import moment from "moment";


export type JobNode = TreeNode<Job>;

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

export default class JobTree extends Tree<Job> {
    static fromJobs(jobs: Job[]): JobTree {
        // Record the tree and stack of current ancestors
        const tree: JobNode[] = [];

        for (const job of jobs) {
            if (job.status === JobState.LAUNCHED || job.status === JobState.PENDING) {
                throw new Error("Unexpected job state")
            }
            const { ident, uidx, owner, started } = job;
            const dataNode: JobNode = {
                title: `#${uidx} ${ident} | ${owner} | ${moment(started * 1000).format("HH:mm:ss")}`,
                key: job.uidx,
                children: [],
                data: job
            }
            tree.push(dataNode)
        }
        return new JobTree(tree);
    }
    updatedFromLayers(layers: { key: TreeKey, response: ApiLayerResponse }[]): JobTree {
        for (const { key, response } of layers) {
            const node = this.getNodeByKey(key);
            if (node === undefined) continue;
            const job = node.data = {
                ...node.data,
                ...response
            };
            node.children = response.jobs.sort((a, b) => naturalCompare(a.ident, b.ident)).map(child => {
                const path = [...job.path, child.ident];
                const childKey = [job.root, ...path].join('-');
                const childNode = this.getNodeByKey(childKey);
                return {
                    key: childKey,
                    title: child.ident,
                    children: childNode?.children ?? [],
                    data: {
                        root: job.root,
                        path,
                        ...child
                    }
                }
            });
        }
        return new JobTree(this.getRoots());
    }
}
