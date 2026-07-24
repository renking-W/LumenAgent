import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import './styles.css'
import RootApp from './RootApp.vue'
import { initializeAuth, installAuthenticatedFetch } from './services/auth'

installAuthenticatedFetch()
void initializeAuth()

createApp(RootApp).use(ElementPlus).mount('#app')
