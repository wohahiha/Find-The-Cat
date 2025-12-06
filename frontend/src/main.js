import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import './assets/tailwind.css'
import { useConfigStore } from '@/stores/config'

const app = createApp(App)
const pinia = createPinia()
app.use(pinia).use(router)

// 预取品牌配置，失败时回退默认值
const configStore = useConfigStore(pinia)
configStore.fetchBrand().catch(() => null)

app.mount('#app')
