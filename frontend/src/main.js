import { createApp } from 'vue'
import { setConfig, frappeRequest } from 'frappe-ui'
import App from './App.vue'
import router from './router'
import './index.css'

// Configure frappe-ui
setConfig('resourceFetcher', frappeRequest)

const app = createApp(App)
app.use(router)
app.mount('#app')

