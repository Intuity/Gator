/*
 * SPDX-License-Identifier: MIT
 * Copyright (c) 2023-2024 Vypercore. All Rights Reserved
 */

import Dashboard, { TreeSelectState } from "@/features/JobDashboard/components/Dashboard";
import { ReactNode, useEffect, useMemo, useRef, useState } from "react";
import JobTree, { splitJobKey } from "@/features/JobDashboard/lib/jobtree";
import { EventDataNode } from "antd/lib/tree";
import Tree, { TreeKey, TreeNode } from "@/features/JobDashboard/components/Dashboard/lib/tree";
import { CheckCircleFilled, ClockCircleFilled, CloseCircleFilled, QuestionCircleFilled, StopFilled, TableOutlined } from "@ant-design/icons";
import MessageTable from "@/features/JobDashboard/components/MessageTable";
import RegistrationTable from "@/features/JobDashboard/components/RegistrationTable";
import { ApiJob, JobResult, JobState } from "@/types/job";
import { HubReader, Reader } from "./lib/readers";
import { view } from "./components/Dashboard/theme";
import { Progress, ProgressProps } from "antd";

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

type liveFetchEffectProps = {
    interval: number;
    reader: Reader;
    tree: JobTree;
    setTree: (newTree: JobTree) => void;
    liveTreeKeys: TreeKey[]
}

function liveFetchEffect({ interval, reader, tree, setTree, liveTreeKeys }: liveFetchEffectProps) {
    const task = async () => {

        const apiJobs = await Promise.all(liveTreeKeys.map((k) => tree.getNodeByKey(k))
            .filter(node => node !== undefined)

            .map(node => reader.readLayer(node.data)));
        if (!apiJobs.length) return;

        const newTree = tree.updatedFromJobs(apiJobs);
        setTree(newTree);
    }
    const timeout = setInterval(task, interval);
    return () => clearInterval(timeout);
}

type urlPathEffectProps = {
    selectedTreeKeys: TreeKey[]
    tree: JobTree
}

function urlPathEffect({ selectedTreeKeys, tree }: urlPathEffectProps) {
    const url = new URL(document.location.href);
    url.searchParams.delete("path");
    let idents: string[] = []
    for (const treeKey of selectedTreeKeys) {
        const node = tree.getNodeByKey(treeKey);
        if (node) {
            const path = [node.data.root, ...node.data.path, node.data.ident]
            url.searchParams.append("path", path.join('.'));
            idents.push(node.data.ident);
        }

    }
    // Note if we want browser back button to navigate this history
    // we can use pushState here.
    history.replaceState(null, idents.join('|'), url);
    return () => { };
}


export default function JobDashboard() {
    const [reader, _setReader] = useState<Reader>(new HubReader())

    const [tree, setTree] = useState<JobTree>(JobTree.fromJobs([]));
    const [treeSelectState, setTreeSelectState] = useState<TreeSelectState>(() => {
        const url = new URL(document.location.href);
        const urlSelectedKeys = url.searchParams.getAll("path");

        Promise.allSettled(urlSelectedKeys.map(k => reader.readTunnel(splitJobKey(k)))).then(results => {
            const jobs = results.filter(r => r.status === "fulfilled").map(r => r.value);
            const newTree = tree.updatedFromJobs(jobs);

            setTree(newTree);
            setTreeSelectState(state => {
                const newExpandedKeys = new Set<TreeKey>(state.expandedKeys);
                for (const newSelectedKey of urlSelectedKeys) {
                    for (const ancestor of newTree.getAncestorsByKey(newSelectedKey as TreeKey)) {
                        newExpandedKeys.add(ancestor.key);
                    }
                }
                return {
                    ...state,
                    selectedKeys: urlSelectedKeys,
                    expandedKeys: Array.from(newExpandedKeys),
                    autoExpandParents: false
                }
            });
        })

        return {
            selectedKeys: [],
            expandedKeys: [],
            autoExpandParents: false,
        }
    });

    const [loadingTreeKeys, setLoadingTreeKeys] = useState<TreeKey[]>([]);

    const loadedTreeKeys: TreeKey[] = [];
    for (const [{ key, data, children }, _parent] of tree.walk()) {
        if (children?.length === data.expected_children || data.result === JobResult.ABORTED) {
            loadedTreeKeys.push(key);
        }
    }

    const liveTreeKeys = useRef<TreeKey[]>([]);
    useMemo(() => {
        // Take the 5 most recently selected non-complete items
        liveTreeKeys.current = [
            ...treeSelectState.selectedKeys,
            ...liveTreeKeys.current.filter(k => !treeSelectState.selectedKeys.includes(k))
        ].filter(k => tree.getNodeByKey(k)?.data.status !== JobState.COMPLETE).slice(0, 5);

    }, [tree, treeSelectState, loadedTreeKeys]);

    async function onLoadData(eventNode: EventDataNode<TreeNode<ApiJob>>) {
        const node = tree.getNodeByKey(eventNode.key);
        if (node === undefined) return;

        setLoadingTreeKeys(state => [...state, node.key]);
        const response = await reader.readLayer(node.data).catch(_e => {
            return null;
        });

        if (!response) return;
        const newTree = tree.updatedFromJobs([response])
        setLoadingTreeKeys(state => [...state, node.key].filter(k => k !== node.key));
        setTree(newTree);
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
            return [
                {
                    value: "message_table",
                    icon: <TableOutlined />,
                    factory: () => <MessageTable job={node.data} key={node.key} reader={reader} />
                },
            ];
        }
    }, [selectedRowKeys, reader]);

    function treeNodeFormatter(treeNode: TreeNode<ApiJob>, searchValue: string) {
        const { status, result, metrics, expected_children } = treeNode.data;
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
                const total = Math.max(metrics.sub_total ?? 1, expected_children);
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
                    if (result === JobResult.SUCCESS) {
                        // Job itself successfully started and completed
                        successRatio = 0.3
                    } else if (result === JobResult.ABORTED) {
                        // Job didn't successfully start
                        successRatio = 0;
                    } else {
                        // Job successfully started
                        successRatio = 0.2;
                    }
                    // Leave most of the bar to child jobs
                    successRatio += (0.7 * subSuccessRatio);
                }
        }

        let progressStatus: ProgressProps["status"];
        let icon: ReactNode;
        switch (result) {
            case JobResult.UNKNOWN:
                if (metrics.sub_failed) {
                    progressStatus = "exception";
                    icon = <CloseCircleFilled />
                } else if (liveTreeKeys.current.includes(treeNode.key)) {
                    progressStatus = "active";
                    icon = <ClockCircleFilled />
                } else {
                    progressStatus = "normal";
                    icon = <QuestionCircleFilled />
                }
                break;
            case JobResult.SUCCESS:
                progressStatus = "success";
                icon = <CheckCircleFilled />
                break;
            case JobResult.FAILURE:
                progressStatus = "exception";
                icon = <CloseCircleFilled />
                break;
            case JobResult.ABORTED:
                progressStatus = "exception";
                icon = <StopFilled />
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
                    format={() => icon}
                />
            </div>
        </span>
    }
    useEffect(() => urlPathEffect({ selectedTreeKeys: treeSelectState.selectedKeys, tree }), [treeSelectState.selectedKeys, tree])
    useEffect(() => liveFetchEffect({ interval: 3000, reader, tree, setTree, liveTreeKeys: liveTreeKeys.current }), [reader, tree, liveTreeKeys.current])

    return <Dashboard tree={tree} treeSelectState={treeSelectState} setTreeSelectState={setTreeSelectState} onLoadData={onLoadData} loadedKeys={[...loadingTreeKeys, ...loadedTreeKeys]} getViewsByKey={getViewsByKey} treeNodeFormatter={treeNodeFormatter} />
}
