/*
Copyright 2024, Peter Birch, mailto:peter@lightlogic.co.uk

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
*/

// #!/usr/bin/env node --no-warnings=ExperimentalWarning
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";
// Plugin that synchronises vite's path searching with tsconfig settings.
import tsconfigPaths from "vite-tsconfig-paths";
import { viteSingleFile } from "vite-plugin-singlefile"
import { resolve } from 'path'
import { createRequire } from "module";

export default defineConfig(async () => {
    let cvgPathJSON = process.env["BUCKET_CVG_JSON"];
    if (cvgPathJSON === undefined) {
        throw new Error("`BUCKET_CVG_JSON` env not defined!")
    }
    cvgPathJSON = resolve(cvgPathJSON)

    let coverage = createRequire(import.meta.url)(cvgPathJSON);
    // Note modern but experimental syntax is:
    //  `await import(cvgPathJSON, { with: { type: 'json' }});`

    return {
        plugins: [react(), tsconfigPaths(), viteSingleFile()],
        define: {
            __BUCKET_CVG_JSON: coverage
        }
    }
});
