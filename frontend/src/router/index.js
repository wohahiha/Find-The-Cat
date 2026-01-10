import { createRouter, createWebHistory } from 'vue-router'
import PublicLayout from '@/layouts/PublicLayout.vue'
import AuthLayout from '@/layouts/AuthLayout.vue'
import AppLayout from '@/layouts/AppLayout.vue'
import Home from '@/pages/Home.vue'
import Login from '@/pages/Login.vue'
import Register from '@/pages/Register.vue'
import ForgotPassword from '@/pages/ForgotPassword.vue'
import ChangePassword from '@/pages/ChangePassword.vue'
import Profile from '@/pages/Profile.vue'
import AnnouncementList from '@/pages/announcements/AnnouncementList.vue'
import AnnouncementDetail from '@/pages/announcements/AnnouncementDetail.vue'
import ContestList from '@/pages/contests/ContestList.vue'
import ContestDetail from '@/pages/contests/ContestDetail.vue'
import ContestAnnouncements from '@/pages/contests/ContestAnnouncements.vue'
import ContestAnnouncementDetail from '@/pages/contests/ContestAnnouncementDetail.vue'
import ContestChallenges from '@/pages/contests/ContestChallenges.vue'
import ContestScoreboard from '@/pages/contests/ContestScoreboard.vue'
import SubmissionHistory from '@/pages/contests/SubmissionHistory.vue'
import ProblemBankList from '@/pages/problems/ProblemBankList.vue'
import ProblemBankChallengeList from '@/pages/problems/ProblemBankChallengeList.vue'
import ProblemBankChallengeDetail from '@/pages/problems/ProblemBankChallengeDetail.vue'
import TeamPage from '@/pages/teams/TeamPage.vue'
import TeamManagement from '@/pages/teams/TeamManagement.vue'
import TeamDetail from '@/pages/teams/TeamDetail.vue'
import MachineManagement from '@/pages/machines/MachineManagement.vue'
import AccountDeactivation from '@/pages/account/AccountDeactivation.vue'
import NotificationList from '@/pages/notifications/NotificationList.vue'
import NotFound from '@/pages/NotFound.vue'
import { useToastStore } from '@/stores/toast'

const routes = [
  {
    path: '/',
    component: PublicLayout,
    children: [
      { path: '', name: 'home', component: Home },
      { path: 'announcements', name: 'announcement-list', component: AnnouncementList },
      { path: 'announcements/:id', name: 'announcement-detail', component: AnnouncementDetail },
    ],
  },
  {
    path: '/',
    component: AuthLayout,
    children: [
      { path: 'login', name: 'login', component: Login, meta: { guestOnly: true } },
      { path: 'register', name: 'register', component: Register, meta: { guestOnly: true } },
      { path: 'forgot-password', name: 'forgot-password', component: ForgotPassword, meta: { guestOnly: true } },
    ],
  },
  {
    path: '/',
    component: AppLayout,
    children: [
      { path: 'profile', name: 'profile', component: Profile, meta: { requiresAuth: true } },
      { path: 'change-password', name: 'change-password', component: ChangePassword, meta: { requiresAuth: true } },
      // 比赛列表允许未登录浏览（首页和列表共用），详情等需登录
      { path: 'contests', name: 'contest-list', component: ContestList, meta: { theme: 'green' } },
      { path: 'contests/:contestSlug', name: 'contest-detail', component: ContestDetail, meta: { requiresAuth: true, theme: 'green' } },
      {
        path: 'contests/:contestSlug/announcements',
        name: 'contest-announcements',
        component: ContestAnnouncements,
        meta: { theme: 'blue' },
      },
      {
        path: 'contests/:contestSlug/announcements/:announcementId',
        name: 'contest-announcement-detail',
        component: ContestAnnouncementDetail,
        meta: { requiresAuth: true, theme: 'blue' },
      },
      {
        path: 'contests/:contestSlug/challenges',
        name: 'contest-challenges',
        component: ContestChallenges,
        meta: { requiresAuth: true, theme: 'green' },
      },
      {
        path: 'contests/:contestSlug/scoreboard',
        name: 'contest-scoreboard',
        component: ContestScoreboard,
        meta: { requiresAuth: true, theme: 'green' },
      },
      {
        path: 'contests/:contestSlug/submissions',
        name: 'contest-submissions',
        component: SubmissionHistory,
        meta: { requiresAuth: true, theme: 'green' },
      },
      { path: 'problems', name: 'problem-bank-list', component: ProblemBankList, meta: { requiresAuth: true, theme: 'green' } },
      {
        path: 'problems/:bankSlug/challenges',
        name: 'problem-bank-challenges',
        component: ProblemBankChallengeList,
        meta: { requiresAuth: true, theme: 'green' },
      },
      {
        path: 'problems/:bankSlug/challenges/:challengeSlug',
        name: 'problem-bank-challenge-detail',
        component: ProblemBankChallengeDetail,
        meta: { requiresAuth: true, theme: 'green' },
      },
      { path: 'teams', name: 'teams', component: TeamPage, meta: { requiresAuth: true, theme: 'green' } },
      {
        path: 'teams/:contestSlug/detail',
        name: 'team-detail',
        component: TeamDetail,
        meta: { requiresAuth: true, theme: 'green' },
      },
      { path: 'teams/manage', name: 'team-manage', component: TeamManagement, meta: { requiresAuth: true, theme: 'green' } },
      { path: 'machines', name: 'machines', component: MachineManagement, meta: { requiresAuth: true, theme: 'green' } },
      { path: 'account/deactivate', name: 'account-deactivate', component: AccountDeactivation, meta: { requiresAuth: true } },
      { path: 'notifications', name: 'notifications', component: NotificationList, meta: { requiresAuth: true } },
    ],
  },
  { path: '/:pathMatch(.*)*', name: 'not-found', component: NotFound },
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
  const requiresAuth = to.matched.some((record) => record.meta?.requiresAuth)
  const guestOnly = to.matched.some((record) => record.meta?.guestOnly)

  if (requiresAuth && !hasToken()) {
    const toast = useToastStore()
    toast.error('请先登录后访问')
    if (from?.matched?.length) {
      next(false)
    } else {
      next('/')
    }
    return
  }
  if (guestOnly && hasToken()) {
    next(to.query.redirect || '/')
    return
  }
  next()
})

export default router
