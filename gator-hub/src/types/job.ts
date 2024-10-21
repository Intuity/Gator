type ApiCompletion = {
    uid?: number;
    db_file?: string;
    timestamp?: number;
}

type ApiMetric = {
    name: string;
    value: number;
}

type ApiRegistration = {
    uid: number;
    ident: string;
    server_url: string;
    owner: string;
    timestamp: number;
    completion: ApiCompletion;
    metrics: ApiMetric[];
}



type ApiJob = {
    root: number;
    uid: string;
    ident: string;
    path: string[];
    owner?: string;
    details?: {
        start: number;
        stop?: number;
        server_url?: string;
        db_file?: string;
        metrics: ApiMetric[];
        live: boolean;
    }
}

type ApiMessage = {
    uid: number;
    timestamp: number;
    severity: number;
    message: string;
}

type ApiMessages = {
    total: number;
    messages: ApiMessage[];
    live: boolean;
}
