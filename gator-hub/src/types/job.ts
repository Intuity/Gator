interface ApiCompletion {
    uid?: number,
    db_file?: string,
    timestamp?: number
}

interface ApiMetric {
    name: string,
    value: number
}

interface ApiJob {
    uid: number,
    ident: string,
    server_url: string,
    owner: string,
    timestamp: number,
    completion: ApiCompletion,
    metrics: ApiMetric[]
}
