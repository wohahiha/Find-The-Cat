import { ref } from 'vue'
import { parseApiError } from '@/api/errors'
import { useToastStore } from '@/stores/toast'

/**
 * 通用请求封装：管理 loading/error/data，支持立即执行与自动 toast
 * @param {Function} requestFn - 异步函数，返回 Promise
 * @param {Object} options
 * @param {boolean} options.immediate - 是否立即执行
 * @param {Array} options.immediateArgs - 立即执行时的参数
 * @param {boolean} options.toastOnError - 是否在错误时弹 toast（默认 true）
 * @param {boolean} options.toastOnSuccess - 是否在成功时弹 toast
 * @param {Function} options.transform - 对成功结果进行转换的函数
 */
export const useFetch = (requestFn, options = {}) => {
  const {
    immediate = false,
    immediateArgs = [],
    toastOnError = true,
    toastOnSuccess = false,
    transform,
  } = options

  const data = ref(null)
  const loading = ref(false)
  const error = ref('')
  const toast = useToastStore()

  const execute = async (...args) => {
    loading.value = true
    error.value = ''
    try {
      const res = await requestFn(...args)
      data.value = transform ? transform(res) : res
      if (toastOnSuccess) {
        const msg = res?.message || res?.data?.message
        if (msg) toast.success(msg)
      }
      return res
    } catch (err) {
      const msg = parseApiError(err)
      error.value = msg
      if (toastOnError) toast.error(msg)
      return Promise.reject(err)
    } finally {
      loading.value = false
    }
  }

  if (immediate) {
    execute(...immediateArgs).catch(() => null)
  }

  return {
    data,
    loading,
    error,
    execute,
    refresh: () => execute(...immediateArgs),
  }
}
