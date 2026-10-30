// Public type-only barrel for consumers that import from `@ff/shared/types`.
export type {
  DeviceType,
  UploadFileRef,
  VideoUnit,
  VideoRecord,
  RecorderCreate,
  EnvironmentCreate,
  ProductCreate,
  ProcessCreate,
  OperatorCreate,
  OperatorRow,
  LocationCreate,
  LocationRow,
  SceneCreate,
  SceneApplicationCreate,
  VideoUploadPreview,
  VideoUploadCommit,
  DryRunResult,
  CommitResult,
} from './schemas'

export type {
  AdapterRegistry,
  AnyDeviceCode,
  DeviceAdapter,
  DeviceMetadata,
  PreviewHandle,
} from './adapters'
