// localStorage 预填表单（plan2 §2.5 核心 UX）
'use client'

import { LOCALSTORAGE_KEYS } from '@ff/shared/constants'

export interface LastFormFields {
  recorderKey?: string
  environmentKey?: string
  processId?: string
  deviceTypeCode?: string
}

export function readLastForm(): LastFormFields {
  if (typeof window === 'undefined') return {}
  try {
    const raw = window.localStorage.getItem(LOCALSTORAGE_KEYS.LAST_FORM)
    return raw ? (JSON.parse(raw) as LastFormFields) : {}
  } catch {
    return {}
  }
}

export function writeLastForm(fields: LastFormFields) {
  if (typeof window === 'undefined') return
  window.localStorage.setItem(LOCALSTORAGE_KEYS.LAST_FORM, JSON.stringify(fields))
}

export function clearLastForm() {
  if (typeof window === 'undefined') return
  window.localStorage.removeItem(LOCALSTORAGE_KEYS.LAST_FORM)
}
