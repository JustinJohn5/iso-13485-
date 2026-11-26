import { expect, test } from '@playwright/test';
import { login, watchPage } from './Helpers';

test('账户入口搜索本人文件并持久化分组成员变更', async ({ page }) => {
  const assertNoErrors = watchPage(page);
  await login(page);
  await expect(page.getByTestId('account-menu-button')).toBeVisible();
  await page.getByTestId('account-menu-button').click();
  await page.getByTestId('account-files').click();
  await expect(page.getByTestId('file-search')).toBeVisible();

  const api = process.env.E2E_API_BASE_URL!;
  const name = `个人文件-${Date.now()}.txt`;
  const uploaded = await page.request.post(`${api}/api/v1/documents`, {
    multipart: { file: { name, mimeType: 'text/plain', buffer: Buffer.from('文件编号：QP-SELF\n版本：01') }, document_type: 'procedure' },
  });
  expect(uploaded.status()).toBe(200);
  const uploadBody = await uploaded.json();
  expect(uploadBody.code).toBe(0);
  const fileUid = uploadBody.data.file_uid as string;

  await page.getByTestId('file-search').fill(name);
  const row = page.getByTestId(`file-row-${fileUid}`);
  await expect(row).toBeVisible();
  await expect(page.getByTestId('file-row-no-such-personal-file')).toHaveCount(0);

  await page.getByTestId('account-menu-button').click();
  await page.getByTestId('account-groups').click();
  const groupName = `临时分组-${Date.now()}`;
  await page.getByTestId('group-name').fill(groupName);
  const creating = page.waitForResponse(response => response.url().endsWith('/api/v1/my/file-groups') && response.request().method() === 'POST');
  await page.getByTestId('group-create').click();
  const created = await creating;
  expect(created.status()).toBe(200);
  const createdGroup = (await created.json()).data as { group_uid: string; name: string };
  expect(createdGroup.name).toBe(groupName);
  await expect(page.getByTestId(`group-row-${createdGroup.group_uid}`)).toBeVisible();
  const groupResponse = await page.request.get(`${api}/api/v1/my/file-groups?page_size=100`);
  expect(groupResponse.status()).toBe(200);
  const groupBody = await groupResponse.json();
  const group = groupBody.data.items.find((item: { name: string }) => item.name === groupName);
  expect(group).toBeTruthy();

  await page.getByTestId('group-members-toggle').click();
  await page.getByTestId(`group-file-${fileUid}`).check();
  const adding = page.waitForResponse(response => response.url().endsWith(`/api/v1/my/file-groups/${group.group_uid}/members`) && response.request().method() === 'POST');
  await page.getByTestId('group-add-members').click();
  expect((await adding).status()).toBe(200);
  await expect(page.getByTestId(`group-row-${group.group_uid}`)).toContainText('1 份文件');
  const filesResponse = await page.request.get(`${api}/api/v1/my/files?keyword=${encodeURIComponent(name)}`);
  expect(filesResponse.status()).toBe(200);
  const filesBody = await filesResponse.json();
  expect(filesBody.data.total).toBe(1);
  expect(filesBody.data.items[0].groups).toContainEqual({ group_uid: group.group_uid, name: groupName });

  await page.getByTestId('group-members-toggle').click();
  await page.getByTestId(`group-file-${fileUid}`).check();
  const removing = page.waitForResponse(response => response.url().endsWith(`/api/v1/my/file-groups/${group.group_uid}/members`) && response.request().method() === 'DELETE');
  await page.getByTestId('group-remove-members').click();
  expect((await removing).status()).toBe(200);
  await expect(page.getByTestId(`group-row-${group.group_uid}`)).toContainText('0 份文件');
  const afterRemoval = await page.request.get(`${api}/api/v1/my/files?keyword=${encodeURIComponent(name)}`);
  expect((await afterRemoval.json()).data.items[0].groups).not.toContainEqual({ group_uid: group.group_uid, name: groupName });

  const deletion = await page.request.delete(`${api}/api/v1/my/file-groups/${group.group_uid}`);
  expect(deletion.status()).toBe(200);
  const retained = await page.request.get(`${api}/api/v1/my/files?keyword=${encodeURIComponent(name)}`);
  expect((await retained.json()).data.total).toBe(1);
  await assertNoErrors();
});

test('个人文件页和分组页都能通过账户菜单退出登录', async ({ page }) => {
  await login(page);
  await page.getByTestId('account-menu-button').click();
  await page.getByTestId('account-files').click();
  await expect(page.getByTestId('personal-files-page')).toBeVisible();
  await page.getByTestId('account-menu-button').click();
  await page.getByTestId('account-logout').click();
  await expect(page.getByTestId('login-email')).toBeVisible();

  await login(page);
  await page.getByTestId('account-menu-button').click();
  await page.getByTestId('account-groups').click();
  await expect(page.getByTestId('file-groups-page')).toBeVisible();
  await page.getByTestId('account-menu-button').click();
  await page.getByTestId('account-logout').click();
  await expect(page.getByTestId('login-email')).toBeVisible();
});
