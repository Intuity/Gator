export type ApiCompletion = {
    uid?: number;
    db_file?: string;
    timestamp?: number;
}

export type Metrics = {
    [key: string]: number
}

export enum JobState {
    PENDING = "pending",
    LAUNCHED = "launched",
    STARTED = "started",
    COMPLETE = "complete"
}

type ApiBaseJob<State extends JobState> = {
    uidx: number;
    ident: string;
    owner: string | null;
    status: State;
    metrics: Metrics;
    server_url: string;
    db_file: string;
    start: number | null;
    stop: number | null;
}

type ApiPendingJob = ApiBaseJob<JobState.PENDING> & {
    start: null;
    stop: null;
}

type ApiLaunchedJob = ApiBaseJob<JobState.LAUNCHED> & {
    start: null;
    stop: null;
}

type ApiStartedJob = ApiBaseJob<JobState.STARTED> & {
    start: number;
    stop: null;
}


type ApiCompleteJob = ApiBaseJob<JobState.COMPLETE> & {
    start: number;
    stop: number;
}

export type ApiJob = ApiPendingJob | ApiLaunchedJob | ApiStartedJob | ApiCompleteJob;

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

export type ApiMessages = {
    total: number;
    messages: ApiMessage[];
    status: JobState;
}
