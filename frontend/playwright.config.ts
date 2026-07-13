import { defineConfig, devices } from '@playwright/test';

const runSlot = process.pid % 1_000;
const frontendPort = Number(process.env.E2E_FRONTEND_PORT ?? 21_000 + runSlot);
const backendPort = Number(process.env.E2E_BACKEND_PORT ?? 31_000 + runSlot);
process.env.E2E_FRONTEND_PORT = String(frontendPort);
process.env.E2E_BACKEND_PORT = String(backendPort);
const frontendUrl = `http://127.0.0.1:${frontendPort}`;
const backendUrl = `http://127.0.0.1:${backendPort}`;

export default defineConfig({
  testDir: './e2e',
  timeout: 60_000,
  expect: {
    timeout: 10_000,
  },
  fullyParallel: false,
  workers: 1,
  // 단일 워커로 전 스펙을 길게 순차 실행하면 누적 부하로 간헐 타임아웃(플레이크)이 난다.
  // 실패한 테스트만 재시도해 부하성 플레이크를 걸러낸다.
  retries: 2,
  reporter: 'list',
  use: {
    baseURL: frontendUrl,
    trace: 'retain-on-failure',
  },
  webServer: [
    {
      command: `powershell -NoProfile -ExecutionPolicy Bypass -File .\\scripts\\start_e2e_backend.ps1 -Port ${backendPort} -FrontendUrl ${frontendUrl}`,
      cwd: '../backend',
      url: `${backendUrl}/health`,
      timeout: 120_000,
      reuseExistingServer: false,
    },
    {
      command: `npm run dev -- --host 127.0.0.1 --port ${frontendPort}`,
      url: frontendUrl,
      timeout: 120_000,
      reuseExistingServer: false,
      env: {
        VITE_API_BASE_URL: `${backendUrl}/api`,
      },
    },
  ],
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});
