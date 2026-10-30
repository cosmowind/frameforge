// Negative smoke test: write an MCAP with an INTENTIONALLY different
// FileDescriptorSet for the video schema. verify_mcap_matches_frontend.py
// should report an fds_mismatch error.

import fs from 'node:fs';
import path from 'node:path';
import { McapWriter, TempBuffer } from '@mcap/core';
import protobuf from 'protobufjs';

const OUT_DIR = path.resolve('tools/.smoke');
const OUT_MCAP = path.join(OUT_DIR, 'fixture_bad.mcap');

fs.mkdirSync(OUT_DIR, { recursive: true });

// Reuse the StringValue FDS (correct), but use a SLIGHTLY DIFFERENT
// (hand-rolled, just for the test) CompressedVideo FDS — encodes the same
// shape but with one field tag flipped. verify_mcap_matches_frontend.py
// should catch the FDS byte diff.
const STRING_VALUE_FDS_B64 =
  'CoYECh5nb29nbGUvcHJvdG9idWYvd3JhcHBlcnMucHJvdG8SD2dvb2dsZS5wcm90b2J1ZiIjCgtEb3VibGVWYWx1ZRIUCgV2YWx1ZRgBIAEoAVIFdmFsdWUiIgoKRmxvYXRWYWx1ZRIUCgV2YWx1ZRgBIAEoAlIFdmFsdWUiIgoKSW50NjRWYWx1ZRIUCgV2YWx1ZRgBIAEoA1IFdmFsdWUiIwoLVUludDY0VmFsdWUSFAoFdmFsdWUYASABKARSBXZhbHVlIiIKCkludDMyVmFsdWUSFAoFdmFsdWUYASABKAVSBXZhbHVlIiMKC1VJbnQzMlZhbHVlEhQKBXZhbHVlGAEgASgNUgV2YWx1ZSIhCglCb29sVmFsdWUSFAoFdmFsdWUYASABKAhSBXZhbHVlIiMKC1N0cmluZ1ZhbHVlEhQKBXZhbHVlGAEgASgJUgV2YWx1ZSIiCgpCeXRlc1ZhbHVlEhQKBXZhbHVlGAEgASgMUgV2YWx1ZUKDAQoTY29tLmdvb2dsZS5wcm90b2J1ZkINV3JhcHBlcnNQcm90b1ABWjFnb29nbGUuZ29sYW5nLm9yZy9wcm90b2J1Zi90eXBlcy9rbm93bi93cmFwcGVyc3Bi+AEBogIDR1BCqgIeR29vZ2xlLlByb3RvYnVmLldlbGxLbm93blR5cGVzYgZwcm90bzM=';

// WRONG on purpose: omit the 'data' field from CompressedVideo's schema, so
// FDS bytes will differ.
const BAD_COMPRESSED_VIDEO_FDS_B64 = (
  // same as canonical but with one byte flipped near the end → different sha
  'Cv8BCh9nb29nbGUvcHJvdG9idWYvdGltZXN0YW1wLnByb3RvEg9nb29nbGUucHJvdG9idWYiOwoJ' +
  'VGltZXN0YW1wEhgKB3NlY29uZHMYASABKANSB3NlY29uZHMSFAoFbmFub3MYAiABKAVSBW5hbm9z' +
  'QoUBChNjb20uZ29vZ2xlLnByb3RvYnVmQg5UaW1lc3RhbXBQcm90b1ABWjJnb29nbGUuZ29sYW5n' +
  'Lm9yZy9wcm90b2J1Zi90eXBlcy9rbm93bi90aW1lc3RhbXBwYvgBAaICA0dQQqoCHkdvb2dsZS5Q' +
  'cm90b2J1Zi5XZWxsS25vd25UeXBlc2IGcHJvdG8zCsUBCh5mb3hnbG92ZS9Db21wcmVzc2VkVmlk' +
  'ZW8ucHJvdG8SCGZveGdsb3ZlGh9nb29nbGUvcHJvdG9idWYvdGltZXN0YW1wLnByb3RvInAKD0Nv' +
  'bXByZXNzZWRWaWRlbxItCgl0aW1lc3RhbXAYASABKAsyGi5nb29nbGUucHJvdG9idWYuVGltZXN0' +
  'YW1wEhAKCGZyYW1lX2lkGAIgASgJEgwKBGRhdGEYAyABKAwSDgoGZm9ybWF0GAQgASgJYgZwcm90' +
  'bzE=' // last char flipped from "M" to "E"
);
const BAD_CV_FDS = new Uint8Array(Buffer.from(BAD_COMPRESSED_VIDEO_FDS_B64, 'base64'));
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
await writer.start({ profile: '', library: 'smoke-test-bad' });
const cvSchema = await writer.registerSchema({
  name: 'foxglove.CompressedVideo', encoding: 'protobuf', data: BAD_CV_FDS,
});
const svSchema = await writer.registerSchema({
  name: 'google.protobuf.StringValue', encoding: 'protobuf', data: STRING_VALUE_FDS,
});
const leftCh = await writer.registerChannel({
  schemaId: cvSchema, topic: '/top-left-camera/image-raw',
  messageEncoding: 'protobuf', metadata: new Map(),
});
const imuCh = await writer.registerChannel({
  schemaId: svSchema, topic: '/head-imu',
  messageEncoding: 'protobuf', metadata: new Map(),
});
const cv = CompressedVideoType.encode(CompressedVideoType.create({
  timestamp: { seconds: 0, nanos: 0 },
  frame_id: 'top_left_camera', data: Buffer.from([0]), format: 'h265',
})).finish();
const sv = StringValueType.encode(StringValueType.create({ value: '{}' })).finish();
await writer.addMessage({ channelId: leftCh, sequence: 0, logTime: 0n, publishTime: 0n, data: cv });
await writer.addMessage({ channelId: imuCh, sequence: 1, logTime: 0n, publishTime: 0n, data: sv });
await writer.end();
fs.writeFileSync(OUT_MCAP, buf.get());
console.log(`wrote ${OUT_MCAP} (intentionally wrong FDS)`);
