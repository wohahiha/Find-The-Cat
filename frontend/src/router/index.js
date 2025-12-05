import { createRouter, createWebHistory } from 'vue-router'
import Home from '@/pages/Home.vue'
import Login from '@/pages/Login.vue'
import Register from '@/pages/Register.vue'
import ForgotPassword from '@/pages/ForgotPassword.vue'
import ChangePassword from '@/pages/ChangePassword.vue'
import Profile from '@/pages/Profile.vue'

const routes = [
  { path: '/', component: Home },
  { path: '/login', component: Login },
  { path: '/register', component: Register },
  { path: '/forgot-password', component: ForgotPassword },
  { path: '/change-password', component: ChangePassword, meta: { requiresAuth: true } },
  { path: '/profile', component: Profile, meta: { requiresAuth: true } },
  // TODO: add more pages as they are ported from static HTML
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

const hasToken = () => {
  if (typeof window === 'undefined') return false
  return !!(localStorage.getItem('ftc_access') || sessionStorage.getItem('ftc_access'))
}

router.beforeEach((to, from, next) => {
  if (to.meta.requiresAuth && !hasToken()) {
    next({ path: '/login', query: { redirect: to.fullPath } })
    return
  }
  if (to.path === '/login' && hasToken()) {
    next(to.query.redirect || '/')
    return
  }
  next()
})

export default router
