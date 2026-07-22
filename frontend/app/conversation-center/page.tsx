import { ConversationCenter } from "@/components/conversation-center";
import { DashboardShell } from "@/components/dashboard-shell";
import { getDashboardConversations } from "@/lib/dashboard-api";

export default async function ConversationCenterPage() {
  const conversations = await getDashboardConversations();
  return (
    <DashboardShell
      title="Conversation Center"
      description="Review WhatsApp conversations handled by your AI receptionist."
    >
      <ConversationCenter conversations={conversations} />
    </DashboardShell>
  );
}
