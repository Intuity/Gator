/*
 * SPDX-License-Identifier: MIT
 * Copyright (c) 2023-2024 Vypercore. All Rights Reserved
 */

import { ApiJob, Job, JobState } from "@/types/job";
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

export function splitJobKey(key: string) {
    const path = key.split('.');
    const root = Number(path.shift());
    const ident = path.pop() as string;
    return { root, path, ident }
}

export function getJobKey(job: { root: number, path: string[], ident: string }) {
    return [job.root, ...job.path, job.ident].join('.');
}

export function getJobParentKey(job: { root: number, path: string[] }) {
    return [job.root, ...job.path].join('.');
}

function toJobNode(job: ApiJob): JobNode {
    let title: string;
    const { children, ...data } = job;
    const key = getJobKey(data);
    if (data.path.length) {
        title = data.ident;
    } else {
        if (data.status === JobState.LAUNCHED || data.status === JobState.PENDING) {
            throw new Error("Unexpected job state")
        }
        title = `#${data.root} ${data.ident} | ${data.owner} | ${moment(data.started * 1000).format("HH:mm:ss")}`;
    }
    const nodeChildren = children.map(toJobNode).sort((a, b) => naturalCompare(a.key, b.key));
    const jobNode = {
        title,
        key,
        data
    }
    updateNodeChildren(jobNode, nodeChildren);
    return jobNode;
}

function updateNodeChildren(node: JobNode, children: JobNode[]) {
    if (node.children?.length) {
        const mergedChildren = [];
        const byKey: { [key: string]: JobNode } = {}
        for (const child of node.children) {
            if (String(child.key).endsWith("#expander")) {
                continue;
            }
            mergedChildren.push(child);
            byKey[child.key] = child;
        }
        for (const child of children) {
            if (String(child.key).endsWith("#expander")) {
                continue;
            }
            const oldChild = byKey[child.key];
            if (oldChild) {
                oldChild.data = child.data;
                if (child.children?.length) {
                    updateNodeChildren(oldChild, child.children);
                }
            } else {
                mergedChildren.push(child);
            }
        }
        node.children = mergedChildren;
    } else {
        node.children = children;
    }
    node.children.sort((a, b) => naturalCompare(a.key, b.key));
    const nChildenLeftToLoad = node.data.expected_children - node.children.length;
    if (node.children.length > 0 && nChildenLeftToLoad > 0) {
        node.children.push({
            title: `...Load ${nChildenLeftToLoad} more`,
            key: node.key + '#expander',
            data: node.data,
        });
    }
}

export default class JobTree extends Tree<Job> {
    static fromJobs(jobs: ApiJob[]): JobTree {
        return new JobTree(jobs.map(toJobNode));
    }
    updatedFromJobs(jobs: ApiJob[]): JobTree {
        const newRoots: JobNode[] = [];
        for (const jobNode of jobs.map(toJobNode)) {
            // If node exists in tree update it
            const oldNode = this.getNodeByKey(jobNode.key);
            if (oldNode) {
                oldNode.data = jobNode.data;
                if (jobNode.children?.length) {
                    updateNodeChildren(oldNode, jobNode.children);
                }
                continue;
            }

            // If node is root node, add to tree
            if (!jobNode.data.path.length) {
                newRoots.push(jobNode);
                continue
            }

            // If node parent exists in the tree, add under parent
            const parentKey = getJobParentKey(jobNode.data)
            const oldParent = this.getNodeByKey(parentKey);
            if (oldParent) {
                updateNodeChildren(oldParent, [jobNode]);
            }
        }
        return new JobTree([...this.getRoots(), ...newRoots]);
    }
}
