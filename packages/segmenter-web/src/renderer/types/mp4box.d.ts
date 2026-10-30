declare module 'mp4box' {
  interface MP4BoxTrack {
    id: number;
    codec: string;
    type: string;
    nb_samples: number;
    timescale: number;
    duration: number;
    video?: {
      width: number;
      height: number;
    };
    audio?: {
      sample_rate: number;
      channel_count: number;
    };
  }

  interface MP4BoxInfo {
    duration: number;
    timescale: number;
    videoTracks: MP4BoxTrack[];
    audioTracks: MP4BoxTrack[];
  }

  interface MP4BoxFile {
    onReady: (info: MP4BoxInfo) => void;
    onError: (error: Error) => void;
    appendBuffer(buffer: ArrayBuffer): void;
    flush(): void;
  }

  interface MP4BoxStatic {
    createFile(): MP4BoxFile;
  }

  const MP4Box: MP4BoxStatic;
  export default MP4Box;
}
