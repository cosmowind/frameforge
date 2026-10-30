// Smoke test fixture: write a minimal stereo MCAP that should pass
// tools/verify_mcap_matches_frontend.py against the frameforge upstream reference.
// Uses the same FDS base64 strings the frameforge browser converter embeds.

import fs from 'node:fs';
import path from 'node:path';
import { McapWriter, TempBuffer } from '@mcap/core';
import protobuf from 'protobufjs';

const OUT_DIR = path.resolve('tools/.smoke');
const OUT_MCAP = path.join(OUT_DIR, 'fixture.mcap');

fs.mkdirSync(OUT_DIR, { recursive: true });

const COMPRESSED_VIDEO_FDS_B64 =
  'Cv8BCh9nb29nbGUvcHJvdG9idWYvdGltZXN0YW1wLnByb3RvEg9nb29nbGUucHJvdG9idWYiOwoJVGltZXN0YW1wEhgKB3NlY29uZHMYASABKANSB3NlY29uZHMSFAoFbmFub3MYAiABKAVSBW5hbm9zQoUBChNjb20uZ29vZ2xlLnByb3RvYnVmQg5UaW1lc3RhbXBQcm90b1ABWjJnb29nbGUuZ29sYW5nLm9yZy9wcm90b2J1Zi90eXBlcy9rbm93bi90aW1lc3RhbXBwYvgBAaICA0dQQqoCHkdvb2dsZS5Qcm90b2J1Zi5XZWxsS25vd25UeXBlc2IGcHJvdG8zCsUBCh5mb3hnbG92ZS9Db21wcmVzc2VkVmlkZW8ucHJvdG8SCGZveGdsb3ZlGh9nb29nbGUvcHJvdG9idWYvdGltZXN0YW1wLnByb3RvInAKD0NvbXByZXNzZWRWaWRlbxItCgl0aW1lc3RhbXAYASABKAsyGi5nb29nbGUucHJvdG9idWYuVGltZXN0YW1wEhAKCGZyYW1lX2lkGAIgASgJEgwKBGRhdGEYAyABKAwSDgoGZm9ybWF0GAQgASgJYgZwcm90bzM=';
const STRING_VALUE_FDS_B64 =
  'CoYECh5nb29nbGUvcHJvdG9idWYvd3JhcHBlcnMucHJvdG8SD2dvb2dsZS5wcm90b2J1ZiIjCgtEb3VibGVWYWx1ZRIUCgV2YWx1ZRgBIAEoAVIFdmFsdWUiIgoKRmxvYXRWYWx1ZRIUCgV2YWx1ZRgBIAEoAlIFdmFsdWUiIgoKSW50NjRWYWx1ZRIUCgV2YWx1ZRgBIAEoA1IFdmFsdWUiIwoLVUludDY0VmFsdWUSFAoFdmFsdWUYASABKARSBXZhbHVlIiIKCkludDMyVmFsdWUSFAoFdmFsdWUYASABKAVSBXZhbHVlIiMKC1VJbnQzMlZhbHVlEhQKBXZhbHVlGAEgASgNUgV2YWx1ZSIhCglCb29sVmFsdWUSFAoFdmFsdWUYASABKAhSBXZhbHVlIiMKC1N0cmluZ1ZhbHVlEhQKBXZhbHVlGAEgASgJUgV2YWx1ZSIiCgpCeXRlc1ZhbHVlEhQKBXZhbHVlGAEgASgMUgV2YWx1ZUKDAQoTY29tLmdvb2dsZS5wcm90b2J1ZkINV3JhcHBlcnNQcm90b1ABWjFnb29nbGUuZ29sYW5nLm9yZy9wcm90b2J1Zi90eXBlcy9rbm93bi93cmFwcGVyc3Bi+AEBogIDR1BCqgIeR29vZ2xlLlByb3RvYnVmLldlbGxLbm93blR5cGVzYgZwcm90bzM=';
const COMPRESSED_VIDEO_FDS = new Uint8Array(Buffer.from(COMPRESSED_VIDEO_FDS_B64, 'base64'));
const STRING_VALUE_FDS = new Uint8Array(Buffer.from(STRING_VALUE_FDS_B64, 'base64'));

const messageRoot = protobuf.parse(
  `syntax = "proto3";
   package umiconv;
   message Timestamp { int64 seconds = 1; int32 nanos = 2; }
   message CompressedVideo {
     Timestamp timestamp = 1;
     string frame_id = 2;
     bytes data = 3;
     string format = 4;
   }
   message StringValue { string value = 1; }`,
  { keepCase: true },
).root;
messageRoot.resolveAll();
const CompressedVideoType = messageRoot.lookupType('umiconv.CompressedVideo');
const StringValueType = messageRoot.lookupType('umiconv.StringValue');

const buf = new TempBuffer();
const writer = new McapWriter({ writable: buf, useChunks: true });
await writer.start({ profile: '', library: 'smoke-test' });

const cvSchema = await writer.registerSchema({
  name: 'foxglove.CompressedVideo',
  encoding: 'protobuf',
  data: COMPRESSED_VIDEO_FDS,
});
const svSchema = await writer.registerSchema({
  name: 'google.protobuf.StringValue',
  encoding: 'protobuf',
  data: STRING_VALUE_FDS,
});
const leftCh = await writer.registerChannel({
  schemaId: cvSchema, topic: '/top-left-camera/image-raw',
  messageEncoding: 'protobuf', metadata: new Map(),
});
const rightCh = await writer.registerChannel({
  schemaId: cvSchema, topic: '/top-right-camera/image-raw',
  messageEncoding: 'protobuf', metadata: new Map(),
});
const imuCh = await writer.registerChannel({
  schemaId: svSchema, topic: '/head-imu',
  messageEncoding: 'protobuf', metadata: new Map(),
});

// 30 frames per eye at 30 fps over 1 second; IMU at 200 Hz = 200 samples.
const fps = 30;
const totalFrames = 30;
const totalImu = 200;
let seq = 0;
for (let i = 0; i < totalFrames; i++) {
  const tsUs = i * Math.floor(1e6 / fps);
  const tsNs = BigInt(tsUs) * 1000n;
  const cv = CompressedVideoType.encode(CompressedVideoType.create({
    timestamp: { seconds: Math.floor(tsUs / 1e6), nanos: (tsUs % 1e6) * 1000 },
    frame_id: 'top_left_camera',
    data: Buffer.from([0, 0, 0, 1, 0x40]),   // minimal NAL stub
    format: 'h265',
  })).finish();
  await writer.addMessage({
    channelId: leftCh, sequence: seq++, logTime: tsNs, publishTime: tsNs, data: cv,
  });
  await writer.addMessage({
    channelId: rightCh, sequence: seq++, logTime: tsNs, publishTime: tsNs,
    data: CompressedVideoType.encode(CompressedVideoType.create({
      timestamp: { seconds: Math.floor(tsUs / 1e6), nanos: (tsUs % 1e6) * 1000 },
      frame_id: 'top_right_camera',
      data: Buffer.from([0, 0, 0, 1, 0x40]),
      format: 'h265',
    })).finish(),
  });
}
for (let i = 0; i < totalImu; i++) {
  const tsUs = i * 5000;  // 200 Hz
  const tsNs = BigInt(tsUs) * 1000n;
  const sv = StringValueType.encode(StringValueType.create({
    value: JSON.stringify({ seq: i, t_us: tsUs }),
  })).finish();
  await writer.addMessage({
    channelId: imuCh, sequence: seq++, logTime: tsNs, publishTime: tsNs, data: sv,
  });
}
await writer.end();
fs.writeFileSync(OUT_MCAP, buf.get());
console.log(`wrote ${OUT_MCAP} (${fs.statSync(OUT_MCAP).size} bytes)`);
