import { execFile as execFileCallback } from 'node:child_process';
import { readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { basename, dirname, join, resolve } from 'node:path';
import { promisify } from 'node:util';

const execFile = promisify(execFileCallback);

function errorCode(error: unknown): string | undefined {
  if (typeof error !== 'object' || error === null || !('code' in error)) return undefined;
  return String(error.code);
}

async function stopOwnedBackend(target: string, runId: string): Promise<void> {
  const rawPid = await readFile(join(target, 'server.pid'), 'utf8').catch(() => '');
  if (!/^\d+$/.test(rawPid)) return;
  const pid = Number(rawPid);
  const backendPort = process.env.E2E_BACKEND_PORT;
  if (!Number.isSafeInteger(pid) || pid <= 0 || !backendPort) return;

  const command = [
    `$target = Get-CimInstance Win32_Process -Filter "ProcessId = ${pid}"`,
    'if ($null -ne $target) { $target.CommandLine }',
  ].join('; ');
  const { stdout } = await execFile('powershell.exe', [
    '-NoProfile',
    '-NonInteractive',
    '-Command',
    command,
  ]);
  if (
    !stdout.includes('start_e2e_backend.ps1')
    || !stdout.includes(`-Port ${backendPort}`)
    || !stdout.includes(`-RunId ${runId}`)
  ) return;

  await execFile('taskkill.exe', ['/PID', String(pid), '/T', '/F']).catch((error: unknown) => {
    const code = errorCode(error);
    if (code !== '128') throw error;
  });
}

async function removeRunDirectory(target: string): Promise<void> {
  for (let attempt = 0; attempt < 20; attempt += 1) {
    try {
      await rm(target, { recursive: true, force: true });
      return;
    } catch (error: unknown) {
      const code = errorCode(error);
      if (code !== 'EBUSY' && code !== 'EPERM') throw error;
      await new Promise((resolveDelay) => setTimeout(resolveDelay, 50));
    }
  }
  await rm(target, { recursive: true, force: true });
}

export default async function globalTeardown() {
  const runId = process.env.CLEANING_OPS_E2E_RUN_ID;
  if (!runId || !/^[A-Za-z0-9_-]+$/.test(runId)) return;
  const root = resolve(join(tmpdir(), 'cleaning-ops-e2e'));
  const target = resolve(join(root, runId));
  if (dirname(target) !== root || basename(target) !== runId) return;
  await stopOwnedBackend(target, runId);
  await removeRunDirectory(target);
}
