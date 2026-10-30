// DeviceAdapter 注册表（plan2 §5.3）
// 前端 worker 启动时构建；新设备加一行 + 注册即可

import type { AdapterRegistry, DeviceAdapter } from '@ff/shared/adapters'
import { DjiGoproDcimAdapter } from './device/dji-gopro-dcim'
import { HeadMountedHmdAdapter } from './device/head-mounted-hmd'
import { GoproSessionMcapAdapter } from './device/gopro-session-mcap'
import { Generic AVIRecordingAdapter } from './device/generic-avi-recording'

export function buildAdapterRegistry(): AdapterRegistry {
  const reg: AdapterRegistry = new Map()
  reg.set(DjiGoproDcimAdapter.code, new DjiGoproDcimAdapter())
  reg.set(HeadMountedHmdAdapter.code, new HeadMountedHmdAdapter())
  reg.set(GoproSessionMcapAdapter.code, new GoproSessionMcapAdapter())
  reg.set(Generic AVIRecordingAdapter.code, new Generic AVIRecordingAdapter())
  return reg
}

export function getAdapter(code: string): DeviceAdapter | undefined {
  return buildAdapterRegistry().get(code)
}

export { DjiGoproDcimAdapter, HeadMountedHmdAdapter, GoproSessionMcapAdapter, Generic AVIRecordingAdapter }
