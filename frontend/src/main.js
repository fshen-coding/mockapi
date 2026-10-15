import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import 'element-plus/theme-chalk/dark/css-vars.css'
import '@fontsource-variable/geist'
import '@fontsource-variable/geist-mono'
import '@fontsource/instrument-serif'
import App from './App.vue'
import './style.css'
import './styles/taste.css'

createApp(App).use(ElementPlus).mount('#app')
