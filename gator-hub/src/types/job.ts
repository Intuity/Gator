/*
 * SPDX-License-Identifier: MIT
 * Copyright (c) 2023-2024 Vypercore. All Rights Reserved
 */

export type ApiCompletion = {
    uid?: number;
    db_file?: string;
    timestamp?: number;
}

export type Metrics = {
    [key: string]: number
}

export enum JobState {
    PENDING = 0,
    LAUNCHED = 1,
    STARTED = 2,
    COMPLETE = 3
}

export enum JobResult {
    UNKNOWN = 0,
    SUCCESS = 1,
    FAILURE = 2,
    ABORTED = 3
}

type ApiBaseJob<State extends JobState> = {
    root: number;
    uidx: number;
    path: string[];
    ident: string;
    owner: string | null;
    status: State;
    metrics: Metrics;
    server_url: string;
    db_file: string;
    started: number | null;
    updated: number | null;
    stopped: number | null;
    result: JobResult | null;
    children: ApiJob[];
    expected_children: number;
}

type ApiPendingJob = ApiBaseJob<JobState.PENDING> & {
    started: null;
    updated: null;
    stopped: null;
    result: null
}

type ApiLaunchedJob = ApiBaseJob<JobState.LAUNCHED> & {
    started: null;
    updated: null;
    stopped: null;
    result: null
}

type ApiStartedJob = ApiBaseJob<JobState.STARTED> & {
    started: number;
    updated: number;
    stopped: null;
    result: null
}


type ApiCompleteJob = ApiBaseJob<JobState.COMPLETE> & {
    started: number;
    updated: number;
    stopped: number;
    result: JobResult;
}

export type ApiJob = ApiPendingJob | ApiLaunchedJob | ApiStartedJob | ApiCompleteJob;

export type ApiChildren = {
    status: JobState
    children: ApiJob[]
}

export type ApiMessage = {
    uid: number;
    timestamp: number;
    severity: number;
    message: string;
}

export type ApiMessagesResponse = {
    total: number;
    messages: ApiMessage[];
    status: JobState;
}

export type Job = Omit<ApiJob, "children">;
