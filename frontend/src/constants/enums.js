// 业务枚举常量，避免散落的魔法字符串

export const CAPTCHA_SCENES = {
  REGISTER: 'register',
  RESET_PASSWORD: 'reset_password',
  BIND_EMAIL: 'bind_email',
  CHANGE_PASSWORD: 'change_password',
  LOGIN: 'login',
}

export const CONTEST_STATUS = {
  UPCOMING: 'upcoming',
  RUNNING: 'running',
  ENDED: 'ended',
  FROZEN: 'frozen',
}

export const TEAM_ROLES = {
  CAPTAIN: 'captain',
  MEMBER: 'member',
}

export const SUBMISSION_STATUS = {
  PENDING: 'pending',
  ACCEPTED: 'accepted',
  REJECTED: 'rejected',
  ERROR: 'error',
}

export const FLAG_ERRORS = {
  FORMAT: 48011,
  WRONG: 48012,
}

export const DEFAULT_PAGE_META = {
  page: 1,
  page_size: 12,
  total: 0,
  has_next: false,
  has_previous: false,
  next_page: null,
  previous_page: null,
}
