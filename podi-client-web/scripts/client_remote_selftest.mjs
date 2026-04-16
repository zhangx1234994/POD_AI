import fs from 'fs';
import path from 'path';
import OSS from 'ali-oss';
import { fileURLToPath } from 'url';

const BASE = process.env.CLIENT_SELFTEST_BASE_URL || 'http://117.50.80.158:8099';
const USERNAME = process.env.CLIENT_SELFTEST_USERNAME || 'admin';
const PASSWORD = process.env.CLIENT_SELFTEST_PASSWORD || 'admin123';
const ASYNC_MAX_ATTEMPTS = Number(process.env.CLIENT_SELFTEST_MAX_ATTEMPTS || 40);
const ASYNC_INTERVAL_MS = Number(process.env.CLIENT_SELFTEST_INTERVAL_MS || 3000);
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const REPO_ROOT = path.resolve(__dirname, '..', '..');
const REPORT_PATH = path.join(REPO_ROOT, 'podi-client-web', 'reports', 'client-remote-selftest-latest.json');
const SAMPLE_IMAGE =
  process.env.CLIENT_SELFTEST_IMAGE ||
  path.join(
    REPO_ROOT,
    '测试图',
    'Extra Large Beach Bag Waterproof Beach Totes Bags for Women, Lightweight Foldable Pool Bag with Zipper Wet Compartment-1.png',
  );

function encodeObjectKey(key) {
  return key.split('/').map(encodeURIComponent).join('/');
}

async function login() {
  const resp = await fetch(`${BASE}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: USERNAME, password: PASSWORD }),
  });
  const data = await resp.json();
  if (!resp.ok || !data.accessToken) throw new Error(`login failed: ${resp.status} ${JSON.stringify(data)}`);
  return data.accessToken;
}

async function uploadSample() {
  const stat = fs.statSync(SAMPLE_IMAGE);
  const uploadKeyResp = await fetch(`${BASE}/api/media/v1/upload-key`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ userId: USERNAME }),
  });
  const uploadKeyData = await uploadKeyResp.json();
  if (!uploadKeyResp.ok || !uploadKeyData.uploadKey) throw new Error(`upload-key failed: ${uploadKeyResp.status}`);

  const stsResp = await fetch(`${BASE}/api/media/v1/sts`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      uploadKey: uploadKeyData.uploadKey,
      taskId: `client-selftest-${Date.now()}`,
      action: 'client-selftest',
      fileName: path.basename(SAMPLE_IMAGE),
      mimeType: SAMPLE_IMAGE.toLowerCase().endsWith('.png') ? 'image/png' : 'image/jpeg',
      fileSize: stat.size,
      channel: 'client-web',
    }),
  });
  const sts = await stsResp.json();
  if (!stsResp.ok || !sts.objectKey) throw new Error(`sts failed: ${stsResp.status}`);

  const creds = sts.ossCredentials;
  const client = new OSS({
    region: creds.region,
    accessKeyId: creds.accessKeyId,
    accessKeySecret: creds.accessKeySecret,
    bucket: creds.bucket,
    endpoint: creds.endpoint.startsWith('http') ? creds.endpoint : `https://${creds.endpoint}`,
    secure: true,
    stsToken: creds.securityToken || undefined,
  });
  await client.put(sts.objectKey, SAMPLE_IMAGE);
  const publicUrl = `${(creds.publicDomain || sts.host).replace(/\/$/, '')}/${encodeObjectKey(sts.objectKey)}`;
  return publicUrl;
}

async function getAbilityMap(token) {
  const resp = await fetch(`${BASE}/api/abilities`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  const data = await resp.json();
  if (!resp.ok) throw new Error(`abilities failed: ${resp.status}`);
  return Object.fromEntries((data.items || []).map((item) => [item.capabilityKey, item.id]));
}

async function invokeSync(token, abilityId, payload) {
  const resp = await fetch(`${BASE}/api/abilities/${abilityId}/invoke`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(payload),
  });
  const data = await resp.json();
  return { status: resp.status, data };
}

async function invokeTask(token, abilityId, payload) {
  const resp = await fetch(`${BASE}/api/ability-tasks`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ ...payload, abilityId }),
  });
  const data = await resp.json();
  return { status: resp.status, data };
}

async function pollTask(token, taskId, maxAttempts = 16, intervalMs = 3000) {
  for (let i = 0; i < maxAttempts; i += 1) {
    const resp = await fetch(`${BASE}/api/ability-tasks/${taskId}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    const data = await resp.json();
    console.log(`poll[${i + 1}/${maxAttempts}] status=${data.status}`);
    if (['succeeded', 'failed', 'cancelled'].includes(data.status)) return data;
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }
  return null;
}

async function main() {
  const report = {
    executedAt: new Date().toISOString(),
    baseUrl: BASE,
    sampleImage: SAMPLE_IMAGE,
  };

  console.log('[1/5] login');
  const token = await login();

  console.log('[2/5] upload sample');
  const sampleUrl = await uploadSample();
  console.log('sampleUrl:', sampleUrl);
  report.sampleUrl = sampleUrl;

  console.log('[3/5] load abilities');
  const abilities = await getAbilityMap(token);
  console.log('ability keys:', Object.keys(abilities).slice(0, 12).join(', '));
  report.abilityKeys = Object.keys(abilities);

  console.log('[4/6] sync smoke (baidu)');
  const sync = await invokeSync(token, abilities['quality_upgrade'], {
    imageUrl: sampleUrl,
    inputs: { resolution: '2k', type: 'auto' },
  });
  report.syncBaidu = {
    syncHttpStatus: sync.status,
    syncStatus: sync.data.status,
    syncImage: sync.data.images?.[0]?.ossUrl || sync.data.images?.[0]?.sourceUrl || null,
  };
  console.log(JSON.stringify(report.syncBaidu, null, 2));

  console.log('[5/6] sync smoke (volcengine)');
  const volc = await invokeSync(token, abilities['doubao_seedream_4_5'], {
    inputs: {
      prompt: '一款简洁高级的春夏包袋产品图，米白色主调，柔和棚拍光影，电商主图风格',
      size: '2K',
    },
  });
  report.syncVolcengine = {
    syncHttpStatus: volc.status,
    syncStatus: volc.data.status,
    syncImage: volc.data.images?.[0]?.ossUrl || volc.data.images?.[0]?.sourceUrl || null,
  };
  console.log(JSON.stringify(report.syncVolcengine, null, 2));

  console.log('[6/6] async smoke (kie)');
  const task = await invokeTask(token, abilities['nano_banana_2_image_to_image'], {
    imageUrl: sampleUrl,
    inputs: {
      prompt: '保持主体结构不变，替换成更干净的棚拍配色与商业主图风格',
      resolution: '1K',
      aspect_ratio: '1:1',
    },
  });
  report.async = { taskHttpStatus: task.status, taskId: task.data.id, taskStatus: task.data.status };
  console.log(JSON.stringify(report.async, null, 2));
  if (task.data.id) {
    const finalTask = await pollTask(token, task.data.id, ASYNC_MAX_ATTEMPTS, ASYNC_INTERVAL_MS);
    report.async = {
      ...report.async,
      finalTaskStatus: finalTask?.status || 'timeout',
      finalTaskLogId: finalTask?.log_id || null,
      finalTaskImage:
        finalTask?.resultPayload?.images?.[0]?.ossUrl ||
        finalTask?.resultPayload?.images?.[0]?.sourceUrl ||
        finalTask?.resultPayload?.assets?.[0]?.ossUrl ||
        finalTask?.resultPayload?.assets?.[0]?.sourceUrl ||
        null,
    };
    console.log(JSON.stringify(report.async, null, 2));
  }

  console.log('[6+/6] async smoke (comfyui fast)');
  const comfyTask = await invokeTask(token, abilities['jisu_chuli'], {
    imageUrl: sampleUrl,
    inputs: {
      prompt: '保留包袋主体结构，做更干净的商业产品图质感增强',
      batch: 1,
    },
  });
  report.asyncComfyui = {
    taskHttpStatus: comfyTask.status,
    taskId: comfyTask.data.id,
    taskStatus: comfyTask.data.status,
  };
  console.log(JSON.stringify(report.asyncComfyui, null, 2));
  if (comfyTask.data.id) {
    const finalComfy = await pollTask(token, comfyTask.data.id, ASYNC_MAX_ATTEMPTS, ASYNC_INTERVAL_MS);
    report.asyncComfyui = {
      ...report.asyncComfyui,
      finalTaskStatus: finalComfy?.status || 'timeout',
      finalTaskLogId: finalComfy?.log_id || null,
      finalTaskImage:
        finalComfy?.resultPayload?.images?.[0]?.ossUrl ||
        finalComfy?.resultPayload?.images?.[0]?.sourceUrl ||
        finalComfy?.resultPayload?.assets?.[0]?.ossUrl ||
        finalComfy?.resultPayload?.assets?.[0]?.sourceUrl ||
        null,
    };
    console.log(JSON.stringify(report.asyncComfyui, null, 2));
  }

  fs.writeFileSync(REPORT_PATH, JSON.stringify(report, null, 2));
  console.log(`report saved: ${REPORT_PATH}`);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
