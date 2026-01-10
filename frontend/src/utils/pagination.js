import { DEFAULT_PAGE_META } from '@/constants/enums'

export const normalizePagination = (meta = {}) => ({
  page: meta.page ?? DEFAULT_PAGE_META.page,
  page_size: meta.page_size ?? DEFAULT_PAGE_META.page_size,
  total: meta.total ?? DEFAULT_PAGE_META.total,
  has_next: !!meta.has_next,
  has_previous: !!meta.has_previous,
  next_page: meta.next_page ?? null,
  previous_page: meta.previous_page ?? null,
})

export const buildPageParams = (page = 1, page_size = 10, extra = {}) => ({
  page,
  page_size,
  ...extra,
})
