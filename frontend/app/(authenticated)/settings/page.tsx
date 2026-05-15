import type { Metadata } from "next";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { UsersSettingsPanel } from "@/components/settings/users-settings-panel";
import { RolesSettingsPanel } from "@/components/settings/roles-settings-panel";
import { WorkflowSettingsPanel } from "@/components/settings/workflow-settings-panel";
import { NotificationSettingsPanel } from "@/components/settings/notification-settings-panel";
import { IntegrationsSettingsPanel } from "@/components/settings/integrations-settings-panel";
import { OrganizationSettingsPanel } from "@/components/settings/organization-settings-panel";

export const metadata: Metadata = {
  title: "管理設定",
  description: "ユーザ・ロール・ワークフロー・連携・通知の管理",
};

interface SearchParams {
  tab?: string;
}

interface SettingsPageProps {
  searchParams?: Promise<SearchParams>;
}

const VALID_TABS = [
  "organization",
  "users",
  "roles",
  "workflow",
  "notifications",
  "integrations",
] as const;

type SettingsTab = (typeof VALID_TABS)[number];

function normalizeTab(input: string | undefined): SettingsTab {
  return (VALID_TABS as readonly string[]).includes(input ?? "")
    ? (input as SettingsTab)
    : "organization";
}

export default async function SettingsPage({ searchParams }: SettingsPageProps) {
  const params = (await searchParams) ?? {};
  const activeTab = normalizeTab(params.tab);

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold text-foreground">管理設定</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          システム管理者向けの設定画面です。操作は監査ログに記録されます。
        </p>
      </header>

      <Tabs defaultValue={activeTab}>
        <TabsList>
          <TabsTrigger value="organization">組織</TabsTrigger>
          <TabsTrigger value="users">ユーザ</TabsTrigger>
          <TabsTrigger value="roles">ロール / 権限</TabsTrigger>
          <TabsTrigger value="workflow">承認ワークフロー</TabsTrigger>
          <TabsTrigger value="notifications">通知</TabsTrigger>
          <TabsTrigger value="integrations">外部連携</TabsTrigger>
        </TabsList>

        <TabsContent value="organization">
          <Card>
            <CardHeader>
              <CardTitle>組織情報</CardTitle>
            </CardHeader>
            <CardContent>
              <OrganizationSettingsPanel />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="users">
          <Card>
            <CardHeader>
              <CardTitle>ユーザ管理</CardTitle>
            </CardHeader>
            <CardContent>
              <UsersSettingsPanel />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="roles">
          <Card>
            <CardHeader>
              <CardTitle>ロールと権限</CardTitle>
            </CardHeader>
            <CardContent>
              <RolesSettingsPanel />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="workflow">
          <Card>
            <CardHeader>
              <CardTitle>承認ワークフロー設定</CardTitle>
            </CardHeader>
            <CardContent>
              <WorkflowSettingsPanel />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="notifications">
          <Card>
            <CardHeader>
              <CardTitle>通知設定</CardTitle>
            </CardHeader>
            <CardContent>
              <NotificationSettingsPanel />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="integrations">
          <Card>
            <CardHeader>
              <CardTitle>外部連携</CardTitle>
            </CardHeader>
            <CardContent>
              <IntegrationsSettingsPanel />
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
