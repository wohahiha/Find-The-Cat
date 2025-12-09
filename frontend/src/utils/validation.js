// 表单与输入校验工具

export const isEmail = (value) => {
  if (!value) return false
  const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
  return re.test(String(value).toLowerCase())
}

export const isUsername = (value) => {
  if (!value) return false
  const re = /^[A-Za-z0-9_]{3,32}$/
  return re.test(String(value))
}

export const isUrl = (value) => {
  if (!value) return false
  try {
    new URL(value)
    return true
  } catch {
    return false
  }
}

export const validatePassword = (pwd) => {
  if (!pwd || pwd.length < 8 || pwd.length > 64) return '密码长度需在 8-64 位之间'
  const hasLetter = /[A-Za-z]/.test(pwd)
  const hasDigit = /\d/.test(pwd)
  if (!(hasLetter && hasDigit)) return '密码需同时包含字母和数字'
  return ''
}

// basic HTML injection guard to mirror backend forbid_dangerous_html
const DANGEROUS_HTML_PATTERN = /<\s*script\b|<\s*iframe\b|javascript\s*:|\sonerror\s*=/i

export const containsDangerousHtml = (value) => {
  if (!value) return false
  return DANGEROUS_HTML_PATTERN.test(String(value))
}

// remove obvious dangerous nodes/attrs; keep lightweight to avoid extra deps
export const sanitizeHtml = (value) => {
  if (!value) return ''
  const str = String(value)

  if (typeof window === 'undefined' || typeof DOMParser === 'undefined') {
    return str
      .replace(/<\s*script\b[^>]*>.*?<\/\s*script\s*>/gis, '')
      .replace(/<\s*iframe\b[^>]*>.*?<\/\s*iframe\s*>/gis, '')
      .replace(/javascript\s*:/gi, '')
      .replace(/\son\w+\s*=\s*(['"]).*?\1/gi, '')
  }

  const parser = new DOMParser()
  const doc = parser.parseFromString(str, 'text/html')
  doc.querySelectorAll('script, iframe').forEach((el) => el.remove())
  doc.querySelectorAll('*').forEach((el) => {
    Array.from(el.attributes).forEach((attr) => {
      const name = attr.name.toLowerCase()
      const val = (attr.value || '').toLowerCase()
      if (name.startsWith('on') || val.includes('javascript:')) {
        el.removeAttribute(attr.name)
      }
    })
  })
  return doc.body.innerHTML
}
