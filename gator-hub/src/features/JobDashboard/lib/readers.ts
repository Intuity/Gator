import { ApiJobsResponse, ApiMessagesResponse, ApiTreeResponse } from "@/types/job"

type JobsProps = {
    after?: number;
    before?: number;
    limit?: number;
}
type LayerProps = {
    root: number;
    path: string[];
}
type MessagesProps = {
    root: number;
    path: string[];
    after?: number;
    limit?: number;
}

export type Reader = {
    readJobs: (props: JobsProps) => Promise<ApiJobsResponse | never>;
    readLayer: (props: LayerProps) => Promise<ApiTreeResponse | never>;
    readMessages: (props: MessagesProps) => Promise<ApiMessagesResponse>;
}

class ResponseError extends Error { };
class ProcessingError extends Error { };

async function wrappedFetch(url: URL, logResponse: boolean = false, logError: boolean = true): Promise<any> {
    try {
        const response = await fetch(url);
        if (response.ok) {
            try {
                const result = await response.json();
                if (logResponse) console.log(url.href, result);
                return result;
            } catch (e) {
                throw new ProcessingError("Error processing response", { cause: e });
            }
        } else {
            throw new ResponseError("Bad Response");
        }
    } catch (e) {
        let detail = "Unknown Error";
        if (e instanceof ResponseError) {
            // Could connect to server, but didn't get a good response
            detail = "Server response error";
        } else if (e instanceof ProcessingError) {
            // Got a "good" response, but couldn't process it
            detail = "Response processing error";
        }
        const error = new Error(detail, { cause: e });
        if (logError) console.error(url.href, error)
        throw error;
    }
}

export class HubReader implements Reader {
    private baseURL: URL
    constructor(baseURL: string | URL = document.location.origin) {
        this.baseURL = new URL(baseURL)
    }

    async readJobs(params: JobsProps = {}) {
        const url = new URL("/api/jobs", this.baseURL);
        for (const [key, value] of Object.entries(params)) {
            if (value != null) {
                url.searchParams.set(key, String(value))
            }
        }
        return await wrappedFetch(url, true, true);
    }

    async readLayer({ root, path }: LayerProps) {
        const url = new URL(`/api/job/${root}/resolve/${path.join('/')}`, this.baseURL);
        url.searchParams.set("depth", "1")
        return await wrappedFetch(url, true, true);
    }

    async readMessages({ root, path, ...params }: MessagesProps) {
        const url = new URL(`/api/job/${root}/messages/${path.join('/')}`, this.baseURL);
        for (const [key, value] of Object.entries(params)) {
            if (value != null) {
                url.searchParams.set(key, String(value))
            }
        }
        return await wrappedFetch(url, true, true);
    }

}
