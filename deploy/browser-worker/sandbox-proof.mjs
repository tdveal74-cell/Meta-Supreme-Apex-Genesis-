// Test evidence only: compare renderer namespace and seccomp to this container.
import { readdirSync, readFileSync } from 'node:fs';
export function rendererSandboxEvidence() {
  const baseStatus = readFileSync('/proc/self/status', 'utf8');
  const baseMap = readFileSync('/proc/self/uid_map', 'utf8').trim();
  const baseFilters = Number(baseStatus.match(/^Seccomp_filters:\s*(\d+)/m)?.[1] || 0);
  for (const pid of readdirSync('/proc').filter(name => /^\d+$/.test(name))) {
    try {
      if (!readFileSync(`/proc/${pid}/cmdline`, 'utf8').includes('--type=renderer')) continue;
      const status = readFileSync(`/proc/${pid}/status`, 'utf8');
      const mapping = readFileSync(`/proc/${pid}/uid_map`, 'utf8').trim();
      const filters = Number(status.match(/^Seccomp_filters:\s*(\d+)/m)?.[1] || 0);
      if (mapping !== baseMap && filters > baseFilters && /^Seccomp:\s*2$/m.test(status))
        return { renderer_user_namespace_differs: true, container_seccomp_filters: baseFilters, renderer_seccomp_filters: filters };
    } catch { /* exiting process or restricted proc entry is not proof */ }
  }
  throw new Error('renderer user namespace and additional sandbox seccomp not proven');
}
