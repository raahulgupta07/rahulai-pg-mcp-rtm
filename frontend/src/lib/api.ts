import type { ClassifyResponse, Job, OutletResult, HealthResponse } from './types';
import { auth } from '$lib/stores/auth.svelte';

const BASE = '/api';

async function fetchJSON<T>(url: string, init?: RequestInit): Promise<T> {
  const headers = { ...auth.getHeaders(), ...(init?.headers || {}) };
  const res = await fetch(`${BASE}${url}`, { ...init, headers });
  if (res.status === 401) {
    auth.logout();
    throw new Error('Session expired');
  }
  if (!res.ok) {
    const err = await res.text();
    throw new Error(err || res.statusText);
  }
  return res.json();
}

export async function classify(file: File, thresholdA: number = 80, thresholdB: number = 95): Promise<ClassifyResponse> {
  const form = new FormData();
  form.append('file', file);
  form.append('threshold_a', String(thresholdA));
  form.append('threshold_b', String(thresholdB));
  return fetchJSON<ClassifyResponse>('/classify', { method: 'POST', body: form });
}

export async function getJobs(): Promise<Job[]> {
  return fetchJSON<Job[]>('/jobs');
}

export async function getJob(jobId: string): Promise<{ job: Job; results: OutletResult[] }> {
  return fetchJSON('/jobs/' + jobId);
}

export async function exportExcel(jobId: string): Promise<void> {
  const res = await fetch(`${BASE}/jobs/${jobId}/export`, {
    headers: auth.getHeaders(),
  });
  if (!res.ok) throw new Error('Export failed');
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `RTM_${jobId}.xlsx`;
  a.click();
  URL.revokeObjectURL(url);
}

export async function getHealth(): Promise<HealthResponse> {
  return fetchJSON<HealthResponse>('/health');
}

export async function login(username: string, password: string): Promise<{access_token: string, user: any}> {
  const res = await fetch(`${BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) throw new Error('INVALID_CREDENTIALS');
  return res.json();
}

export async function getUsers(): Promise<any[]> {
  return fetchJSON('/users');
}

export async function createUser(username: string, password: string, role: string, display_name: string, email: string = '', groups: string[] = []): Promise<any> {
  return fetchJSON('/users', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password, role, display_name, email, groups }),
  });
}

export async function deleteUser(userId: number): Promise<void> {
  return fetchJSON(`/users/${userId}`, { method: 'DELETE' });
}

export async function linkUserLdap(userId: number, payload: { email?: string; ldap_username?: string }): Promise<any> {
  return fetchJSON(`/users/${userId}/ldap-link`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export async function changePassword(old_password: string, new_password: string): Promise<any> {
  return fetchJSON('/auth/change-password', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ old_password, new_password }),
  });
}

export async function resetPassword(userId: number, new_password: string): Promise<any> {
  return fetchJSON(`/users/${userId}/password`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ new_password }),
  });
}

export async function getGroups(): Promise<any> {
  return fetchJSON('/groups');
}

export async function createGroup(data: any): Promise<any> {
  return fetchJSON('/groups', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
}

export async function updateGroup(groupId: string, data: any): Promise<any> {
  return fetchJSON(`/groups/${groupId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
}

export async function deleteGroup(groupId: string): Promise<any> {
  return fetchJSON(`/groups/${groupId}`, { method: 'DELETE' });
}

export async function setUserGroups(userId: number, groups: string[]): Promise<any> {
  return fetchJSON(`/users/${userId}/groups`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ groups }),
  });
}

export async function getRtmData(jobId?: string): Promise<any> {
  const params = jobId ? `?job_id=${jobId}` : '';
  return fetchJSON(`/rtm-data${params}`);
}

export async function compareJobs(job1: string, job2: string): Promise<any> {
  return fetchJSON(`/compare?job1=${job1}&job2=${job2}`);
}

export async function getCoverage(jobId?: string): Promise<any> {
  const params = jobId ? `?job_id=${jobId}` : '';
  return fetchJSON(`/coverage${params}`);
}

export async function getSettings(): Promise<any> {
  return fetchJSON('/settings');
}

export async function getAuditLog(): Promise<any[]> {
  return fetchJSON('/audit');
}

export async function getAuditFiltered(params: Record<string, string>): Promise<any[]> {
  const clean = Object.fromEntries(Object.entries(params).filter(([, v]) => v));
  const qs = new URLSearchParams(clean).toString();
  return fetchJSON('/audit' + (qs ? '?' + qs : ''));
}

export async function getAnalytics(): Promise<any> {
  return fetchJSON('/analytics');
}

export async function setUserDisabled(userId: number, disabled: boolean): Promise<any> {
  return fetchJSON(`/users/${userId}/disabled`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ disabled }),
  });
}

export async function saveSettings(data: any): Promise<any> {
  return fetchJSON('/settings', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
}

export async function testLLM(model?: string, base_url?: string): Promise<any> {
  return fetchJSON('/llm-test', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ model: model || '', base_url: base_url || '' }),
  });
}

export async function getRuleHistory(): Promise<any[]> {
  return fetchJSON('/rule-config/history');
}

export async function rollbackRule(versionId: number): Promise<any> {
  return fetchJSON(`/rule-config/rollback/${versionId}`, { method: 'POST' });
}

export async function getJobComparison(jobId: string): Promise<any> {
  return fetchJSON(`/jobs/${jobId}/comparison`);
}

export async function getUsersBasic(): Promise<any[]> {
  return fetchJSON('/users/basic');
}

export async function getJobShares(jobId: string): Promise<{ user_ids: number[] }> {
  return fetchJSON(`/jobs/${jobId}/shares`);
}

export async function shareJob(jobId: string, user_ids: number[]): Promise<any> {
  return fetchJSON(`/jobs/${jobId}/share`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_ids }),
  });
}

export async function getLdapConfig(): Promise<any> {
  return fetchJSON('/ldap-config');
}

export async function saveLdapConfig(cfg: any): Promise<any> {
  return fetchJSON('/ldap-config', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(cfg),
  });
}

export async function testLdap(cfg: any): Promise<any> {
  return fetchJSON('/ldap-test', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(cfg),
  });
}
