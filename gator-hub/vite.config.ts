import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react-swc'
import * as path from 'path';

// https://vitejs.dev/config/
export default defineConfig({
    root: path.resolve(__dirname, "src"),
    resolve: {
        alias: {
            "~bootstrap": path.resolve(__dirname, "node_modules/bootstrap")
        }
    },
    plugins: [react()]
})
