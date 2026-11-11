import {defineConfig} from 'vite';
import react from '@vitejs/plugin-react';
import tailwind from '@tailwindcss/vite';
const backendTarget=(globalThis as any).process?.env?.REFHEALTH_BACKEND_URL||(globalThis as any).process?.env?.COECARE_BACKEND_URL||'http://127.0.0.1:3000';
export default defineConfig({plugins:[react(),tailwind()],build:{rollupOptions:{output:{manualChunks:{charts:['recharts'],react:['react','react-dom','react-router-dom'],forms:['react-hook-form','zod','@hookform/resolvers/zod']}}}},server:{proxy:{'/api':{target:backendTarget,changeOrigin:true,rewrite:path=>path.replace(/^\/api/,'')}}}});
