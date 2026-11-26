import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
export default defineConfig({plugins:[vue()],build:{outDir:'../_runtime/frontend-dist',emptyOutDir:true},server:{proxy:{'/api':process.env.SHISHI_API_TARGET||'http://127.0.0.1:8000'}}})
