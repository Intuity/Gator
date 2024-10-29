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
    uidx: number;
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

export type ApiJobsResponse = {
    status: JobState
    jobs: ApiJob[]
}

export type ApiChildrenResponse = {
    status: JobState
    jobs: ApiJob[]
}

export type ApiLayerResponse = ApiJob & ApiChildrenResponse;

export type Job = ApiJob & {
    root: number
    path: string[],
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
